import asyncio
import collections
from datetime import datetime
import logging

from discord import errors
from discord.ext import commands

from gumo import api
from gumo.api import twitch
from gumo.check import is_admin
from gumo.cogs.stream import models
from gumo import db
from gumo import emoji

LOG = logging.getLogger(__name__)

RECENT_NOTIFICATION_AGE = 300
OLD_NOTIFICATION_LIFESPAN = 60 * 60 * 24


class MissingStreamName(commands.MissingRequiredArgument):

    def __init__(self):
        self.message = "At least one stream name is required"


class StreamCommands(commands.Cog):

    def __init__(self, bot):
        self.display_name = "Twitch"
        self.bot = bot
        self.client = twitch.TwitchAPIClient(self.bot.loop)
        self.webhook_server = twitch.TwitchWebhookServer(self.bot.loop, self.on_webhook_event)
        self.user_db_driver = db.UserDBDriver(self.bot)
        self.channel_db_driver = db.ChannelDBDriver(self.bot)
        self.user_channel_db_driver = db.UserChannelDBDriver(self.bot)
        self.stream_db_driver = db.StreamDBDriver(self.bot)
        self.notification_db_driver = db.NotificationDBDriver(self.bot)
        self.tasks = []

        self.bot.loop.create_task(self.init())

    def cog_unload(self):
        self.webhook_server.stop()
        for task in self.tasks:
            task.cancel()

    async def init(self):
        """Initialize all the manager attributes and load the database data."""
        await self.user_db_driver.init()
        await self.channel_db_driver.init()
        await self.user_channel_db_driver.init()
        await self.stream_db_driver.init()
        await self.notification_db_driver.init()

        await self.webhook_server.start()
        await self.bot.wait_until_ready()

        self.tasks.append(self.bot.loop.create_task(self.update_subscriptions()))
        self.tasks.append(self.bot.loop.create_task(self.delete_old_notifications()))

        def task_done_callback(fut):
            if fut.cancelled():
                LOG.debug(f"The task has been cancelled: {fut}")
                return
            error = fut.exception()
            if error:
                LOG.error(f"A task ended unexpectedly: {fut}", exc_info=(type(error), error, error.__traceback__))

        for task in self.tasks:
            task.add_done_callback(task_done_callback)

    async def on_webhook_event(self, topic, timestamp, body):
        """Method called when a webhook event is received"""

        stream_data = body.get('data')
        user_id = topic.params['user_id']

        # Enrich user data
        user_data = (await self.client.get_users(user_ids=[user_id]))[0]

        if stream_data:

            stream_data = stream_data[0]

            await self._on_stream_update(timestamp, user_data, stream_data)

            # Make sure that any previous stream entry is has an end date
            await self.stream_db_driver.update('ended_at', timestamp, user_id=user_id, ended_at=None)

            data = {
                'id': stream_data['id'],
                'type': stream_data['type'],
                'user_id': stream_data['user_id'],
                'game_id': stream_data['game_id'],
                'started_at': timestamp
            }
            await self.stream_db_driver.create(data.values(), columns=data.keys())

        else:
            await self._on_stream_offline(timestamp, user_data)

    async def _on_stream_update(self, timestamp, user_data, stream_data):

        # Enrich game data
        game_data = (await self.client.get_games(stream_data['game_id']))[0]

        # New message
        if stream_data['type'] == "live":
            message_content = f"{user_data['display_name']} is live!"
        else:
            message_content = f"{user_data['display_name']} started a vodcast!"

        # New embed
        new_embed = models.NotificationEmbed(broadcast_type=stream_data['type'], login=user_data['login'],
                                             display_name=user_data['display_name'], title=stream_data['title'],
                                             game=game_data['name'], logo=user_data['profile_image_url'])

        last_stream = await self.stream_db_driver.get(user_id=user_data['id'], order_by='started_at', desc=True)

        # Get the last stream to distinguish 3 cases:
        # - If the stream id didn't change, then the broadcaster is already live and has updated their stream
        # - If the stream id changed but the last stream was recent then we re use the same notifications
        # - Else, the broadcaster went online after some time offline
        if last_stream and last_stream.id == stream_data['id']:
            stream_id = last_stream.id
        elif last_stream and last_stream.ended_at and \
                (datetime.utcnow() - last_stream.ended_at).total_seconds() < RECENT_NOTIFICATION_AGE:
            stream_id = last_stream.id
        else:
            stream_id = stream_data['id']

            if last_stream:
                # Edit old notifications in case a "stream offline" notification has been missed
                old_notifications = await self.notification_db_driver.list(stream_id=last_stream.id, edited_at=None,
                                                                           deleted_at=None)
                await self._edit_notifications(timestamp, user_data, old_notifications)

        user_channels = await self.user_channel_db_driver.list(user_id=user_data['id'])
        notifications = await self.notification_db_driver.list(stream_id=stream_id, deleted_at=None)

        tags_by_channel_id = {user_channel.channel_id: user_channel.tags for user_channel in user_channels}
        channels_by_id = {user_channel.channel_id: self.bot.get_channel(user_channel.channel_id)
                          for user_channel in user_channels}
        notifications_by_channel_id = {notification.channel_id: notification for notification in notifications}

        channels_edit = [channels_by_id[notification.channel_id] for notification in notifications]
        channels_send = [channel for channel in channels_by_id.values() if channel not in channels_edit]

        # use a copy of the list because it might be edited as we iterate through it
        for channel in channels_edit[:]:

            notification = notifications_by_channel_id[channel.id]

            try:
                message = await self.bot.get_channel(notification.channel_id).fetch_message(notification.message_id)
            except errors.NotFound:
                LOG.warning(f"Notification for {user_data['display_name']} in channel "
                            f"{channel.guild.name}#{channel.name} has most likely been manually deleted, updating the "
                            f"database")
                await self.notification_db_driver.update('deleted_at', timestamp, message_id=notification.message_id)
                channels_edit.remove(channel)
            else:
                # Edit the notification and the related stream_id
                await message.edit(content=f"{tags_by_channel_id[channel.id] or ''} {message_content}", embed=new_embed)
                await self.notification_db_driver.update('stream_id', stream_data['id'],
                                                         message_id=notification.message_id)
            await self.notification_db_driver.update('edited_at', None, message_id=notification.message_id)

        if channels_edit:
            channel_str = [f"{channel.guild.name}#{channel.name}" for channel in channels_edit]
            LOG.debug(f"{user_data['display_name']} is already online or was live recently (less than "
                      f"{RECENT_NOTIFICATION_AGE}s), recent notification have been edited: {', '.join(channel_str)}")

        notifications_to_create = []
        for channel in channels_send[:]:

            # Discard notifications if the extension is not enabled in this guild
            enabled_extensions = await self.bot.extension_db_driver.list(guild_id=channel.guild.id)
            enabled_extension_names = {ext.name for ext in enabled_extensions}
            if 'stream' not in enabled_extension_names:
                LOG.debug(f"The stream extension is not enabled on the server '{channel.guild.name}', "
                          f"the notifications are not sent")
                continue

            message = await channel.send(content=f"{tags_by_channel_id[channel.id] or ''} {message_content}",
                                         embed=new_embed)

            values = (user_data['id'], channel.id, stream_data['id'], message.id, timestamp)
            notifications_to_create.append(values)

        if channels_send:
            columns = ['user_id', 'channel_id', 'stream_id', 'message_id', 'created_at']
            await self.notification_db_driver.create(*notifications_to_create, columns=columns)
            channel_str = [f"{channel.guild.name}#{channel.name}" for channel in channels_send]
            LOG.debug(f"Notifications for {user_data['display_name']} sent: {', '.join(channel_str)}")

    async def _on_stream_offline(self, timestamp, user_data):
        """Method called if the twitch stream is going offline"""

        active_streams = await self.stream_db_driver.list(user_id=user_data['id'], ended_at=None)

        for active_stream in active_streams:
            await self.stream_db_driver.update('ended_at', timestamp, id=active_stream.id, ended_at=None)

        active_notifications = await self.notification_db_driver.list(user_id=user_data['id'], edited_at=None,
                                                                      deleted_at=None)
        await self._edit_notifications(timestamp, user_data, active_notifications)

    async def _edit_notifications(self, timestamp, user_data, notifications):

        for notification in notifications:

            channel = self.bot.get_channel(notification.channel_id)
            try:
                message = await channel.fetch_message(notification.message_id)
            except errors.NotFound:
                LOG.warning(f"Notification for {user_data['display_name']} in channel "
                            f"{channel.guild.name}#{channel.name} has most likely been manually deleted, updating the "
                            f"database)")
                await self.notification_db_driver.update('deleted_at', timestamp, message_id=notification.message_id)
            else:
                new_embed = message.embeds[0]
                new_embed.color = models.OFFLINE_COLOR

                await message.edit(content="", embed=new_embed)

                await self.notification_db_driver.update('edited_at', timestamp, message_id=message.id)

    async def update_subscriptions(self):
        """Renew subscriptions"""
        LOG.debug("Subscriptions refresh task running...")
        while True:
            try:
                subscriptions = await self.webhook_server.list_subscriptions()
                subscribed_users_by_id = {sub.topic.params['user_id']: sub for sub in subscriptions}

                missing_subscriptions = set()
                outdated_subscriptions = set()

                for user_id in [user.id for user in await self.user_db_driver.list()]:

                    # If the subscription is missing
                    if user_id not in subscribed_users_by_id:
                        missing_subscriptions.add(twitch.StreamChanged(user_id=user_id))

                    # If the subscription expires in less than 1 hour
                    elif subscribed_users_by_id[user_id].expires_in < 3600:
                        outdated_subscriptions.add(twitch.StreamChanged(user_id=user_id))

                if missing_subscriptions:
                    LOG.info(f"No subscription for topics: {missing_subscriptions}")

                if outdated_subscriptions:
                    LOG.info(f"Outdated subscriptions for topics: {outdated_subscriptions}")

                await self.webhook_server.unsubscribe(*outdated_subscriptions)
                await self.webhook_server.subscribe(*missing_subscriptions | outdated_subscriptions)
                await asyncio.sleep(600)
            except api.APIError:
                await asyncio.sleep(10)

    async def delete_old_notifications(self):
        """Delete the old offline stream notifications"""
        LOG.debug("Old notifications deletion task running...")
        while True:

            timestamp = datetime.utcnow()
            notifications = await self.notification_db_driver.list(deleted_at=None)

            for notification in notifications:

                if not notification.edited_at:
                    continue

                if (datetime.utcnow() - notification.edited_at).total_seconds() > OLD_NOTIFICATION_LIFESPAN:
                    try:
                        channel = self.bot.get_channel(notification.channel_id)
                        message = await channel.fetch_message(notification.message_id)
                        await message.delete()
                    except errors.NotFound:
                        LOG.warning(f"Notification for user '{notification.user_id}' in channel "
                                    f"{notification.channel_id} has most likely been manually deleted")
                    await self.notification_db_driver.update('deleted_at', timestamp,
                                                             message_id=notification.message_id)
            await asyncio.sleep(600)

    @commands.group()
    @commands.guild_only()
    async def stream(self, ctx):
        """Manage tracked streams"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), command_name=ctx.command.name)

    @stream.command()
    @commands.guild_only()
    async def list(self, ctx):
        """Show the list of the current tracked streams"""

        user_channels = await self.user_channel_db_driver.list()

        users = await self.user_db_driver.list()
        users_by_id = {user.id: user for user in users}

        channels = [self.bot.get_channel(channel.id) for channel in await self.channel_db_driver.list()]
        channels_by_id = {channel.id: channel for channel in channels}

        users_by_channel = collections.defaultdict(list)
        for user_channel in user_channels:

            user = users_by_id[user_channel.user_id]
            channel = channels_by_id[user_channel.channel_id]

            if not channel.guild.id == ctx.guild.id:
                continue

            users_by_channel[channel].append(user)

        # Build an embed displaying the output data.
        # - The discord channels are sorted in the same order as on the server
        # - The user logins are sorted in alphabetical order
        message = ""

        for channel, users in sorted(users_by_channel.items(), key=lambda x: x[0].position):
            channel_name = f"**#{channel.name}**"
            user_logins = sorted([f"`{user.login}`" for user in users])

            message += channel_name + "\n"
            message += ", ".join(user_logins) + "\n\n"

        await ctx.send(message)

    async def _add_streams(self, ctx, *user_logins, tags=None):
        """Track stream """

        users = await self.client.get_users(user_logins=user_logins)

        # Create missing channel
        values = [(ctx.channel.id, ctx.channel.name, ctx.guild.id, ctx.guild.name)]
        created_channels = await self.channel_db_driver.create(*values, ensure=True)
        LOG.info(f"Created channels: {created_channels}")

        # Create missing users
        values = [(user['id'], user['login']) for user in users]
        created_users = await self.user_db_driver.create(*values, ensure=True)
        LOG.info(f"Created users: {created_users}")
        await self.webhook_server.subscribe(*[twitch.StreamChanged(user_id=user.id) for user in created_users])

        # Create missing channel_streams
        values = [(ctx.channel.id, user['id'], tags) for user in users]
        created_user_channels = await self.user_channel_db_driver.create(*values, ensure=True)
        LOG.info(f"Created user_channels: {created_user_channels}")

    @stream.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def add(self, ctx, *user_logins):
        """Track a list of streams in a channel"""
        if not user_logins:
            raise MissingStreamName
        await self._add_streams(ctx, *user_logins)
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def here(self, ctx, *user_logins):
        """Track a list of streams in a channel (with `@here`)."""
        if not user_logins:
            raise MissingStreamName
        await self._add_streams(ctx, *user_logins, tags="@here")
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def everyone(self, ctx, *user_logins):
        """Track a list of streams in a channel (with `@everyone`)."""
        if not user_logins:
            raise MissingStreamName
        await self._add_streams(ctx, *user_logins, tags="@everyone")
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    async def _remove_streams(self, ctx, *user_logins):
        """Stop tracking a list of streams in a channel"""

        users = await self.client.get_users(user_logins=user_logins)
        user_ids = [user['id'] for user in users]

        deleted_user_channels = await self.user_channel_db_driver.bulk_delete(ctx.channel.id, *user_ids)
        LOG.info(f"Deleted user_channels: {deleted_user_channels}")

        deleted_channels = await self.channel_db_driver.delete_old_channels()
        LOG.info(f"Deleted channels: {deleted_channels}")

        deleted_users = await self.user_db_driver.delete_old_users()
        LOG.info(f"Deleted users: {deleted_users}")
        await self.webhook_server.unsubscribe(*[twitch.StreamChanged(user_id=user.id) for user in deleted_users])

    @stream.command(aliases=['rm', 'delete', 'del'])
    @commands.guild_only()
    @commands.check(is_admin)
    async def remove(self, ctx, *user_logins):
        """Stop tracking a list of streams in a channel"""
        if not user_logins:
            raise MissingStreamName
        await self._remove_streams(ctx, *user_logins)
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)
