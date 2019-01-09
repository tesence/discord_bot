import asyncio
import collections
from datetime import datetime
import logging

from discord import errors
from discord.ext import commands

from gumo import api
from gumo import check
from gumo import config
from gumo.cogs.stream import models
from gumo import db
from gumo import emoji
from gumo import utils

LOG = logging.getLogger('bot')

DEFAULT_WEBHOOK_PORT = 8888


class MissingStreamName(commands.MissingRequiredArgument):

    def __init__(self):
        self.message = "At least one stream name is required"


class StreamCommands:

    def __init__(self, bot):
        self.__module__ = "cogs.stream"
        self.display_name = "Twitch"
        self.bot = bot
        self.client = api.TwitchAPIClient(self.bot.loop)
        self.webhook_server = api.TwitchWebhookServer(self.bot.loop, self.on_webhook_event)
        self.stream_db_driver = db.StreamDBDriver(self.bot)
        self.channel_db_driver = db.ChannelDBDriver(self.bot)
        self.channel_stream_db_driver = db.ChannelStreamDBDriver(self.bot)
        self.tasks = []

        self.bot.loop.create_task(self.init())

    def __unload(self):
        self.webhook_server.stop()
        for task in self.tasks:
            task.cancel()

    async def init(self):
        """Initialize all the manager attributes and load the database data."""
        await self.stream_db_driver.init()
        await self.channel_db_driver.init()
        await self.channel_stream_db_driver.init()

        previous_streams = getattr(self.bot, 'streams', None)
        self.bot.streams = previous_streams or {stream.id: stream for stream in await self.stream_db_driver.list()}

        await self.webhook_server.start("0.0.0.0", config.glob.get('WEBHOOK_PORT', DEFAULT_WEBHOOK_PORT))
        await self.webhook_server.subscribe_missing_streams(self.bot.streams.values())

        await self.bot.wait_until_ready()

        self.tasks.append(self.bot.loop.create_task(self.refresh_outdated_subscriptions()))
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

    async def on_webhook_event(self, user_id, body):
        LOG.debug(f"Webhook data received for '{user_id}': {body}")

        user_data = (await self.client.get_users_by_id(user_id))[user_id]
        LOG.debug(f"Related user data found for '{user_id}': {user_data}")

        stream = self.bot.streams[user_id]
        channel_streams = await self.channel_stream_db_driver.list(stream_id=user_id)

        data = body.get('data')

        if data:
            stream_data = data[0]

            current_name = user_data['login']

            if not current_name == stream.name:
                await self.stream_db_driver.update('name', current_name, id=user_id)
                LOG.info(f"'{stream.name}' has changed his name to '{current_name}', the database has been updated")

            game_id = stream_data['game_id']
            game_data = (await self.client.get_games_by_id(game_id)).get(game_id)
            game = game_data['name'].strip() if game_data else None

            # Update old values
            stream.name = current_name
            stream.display_name = user_data['display_name']
            stream.logo = user_data['profile_image_url']
            stream.game = game or "No Game"
            stream.title = stream_data['title'].strip() or "No Title"
            stream.type = stream_data['type']

            if not stream.online:
                LOG.info(f"{stream.name} is online")
                await self._on_stream_online(stream, channel_streams)
            else:
                LOG.debug(f"{stream.name}'s stream has been updated")
                await self._on_stream_update(stream)
        else:
            LOG.info(f"{stream.name} is offline")
            await self._on_stream_offline(stream, channel_streams)

    async def _on_stream_online(self, stream, channel_streams):
        """Method called if twitch stream goes online.

        :param stream: The data of the stream going online
        :param channel_streams: The discord channels in which the stream is tracked
        """
        stream.online = True
        stream.last_offline_date = None
        for channel_stream in channel_streams:
            channel = self.bot.get_channel(channel_stream.channel_id)
            if 'stream' not in config.get('EXTENSIONS', guild_id=channel.guild.id):
                LOG.debug(f"The stream extensions is not enable on the server '{channel.guild}', the notifications "
                          f"are not sent")
                continue
            tags = channel_stream.tags
            channel_repr = utils.get_channel_repr(channel)
            message, embed = models.NotificationHandler.get_info(stream, tags)
            recent_notification = stream.get_recent_notification(channel.id)
            if recent_notification:
                await recent_notification.edit(content=message, embed=embed)
                LOG.debug(f"[{channel_repr}] '{stream.name}' was live recently, recent notification edited")
            else:
                notification = await self.bot.send(channel, message, embed=embed)
                stream.notifications_by_channel_id[channel.id].append(notification)
                LOG.debug(f"[{channel_repr}] Notification for '{stream.name}' sent")

    async def _on_stream_offline(self, stream, channel_streams):
        """Method called if the twitch stream is going offline.

        :param stream: The data of the stream going offline
        :param channel_streams: The discord channels in which the stream is tracked
        """
        stream.online = False
        stream.last_offline_date = datetime.utcnow()
        online_notifications = [notification for notification in stream.notifications
                                if models.NotificationHandler.is_online(notification)]
        for notification in online_notifications:
            channel = notification.channel
            channel_repr = utils.get_channel_repr(channel)
            message, embed = models.NotificationHandler.get_info(stream)
            try:
                await notification.edit(content=message, embed=embed)
                LOG.debug(f"[{channel_repr}] Notification for '{stream.name}' edited")
            except errors.NotFound:
                LOG.warning(f"[{channel_repr}] The notification for '{stream.name}' sent at "
                            f"'{notification.created_at}' does not exist or has been deleted")
                stream.notifications_by_channel_id[channel.id].remove(notification)

    async def _on_stream_update(self, stream):
        """Method called if the twitch stream is update.

        :param stream: The data of the stream being update
        """
        online_notifications = [notification for notification in stream.notifications
                                if models.NotificationHandler.is_online(notification)]
        for notification in online_notifications:
            channel = notification.channel
            channel_repr = utils.get_channel_repr(channel)
            _, embed = models.NotificationHandler.extract_info(notification)
            fields = embed.fields
            embed.set_field_at(index=0, name=fields[0].name, value=stream.title, inline=fields[0].inline)
            embed.set_field_at(index=1, name=fields[1].name, value=stream.game, inline=fields[1].inline)
            try:
                await notification.edit(embed=embed)
                LOG.info(f"[{channel_repr}] Notifications for '{stream.name}' updated (title='{stream.title}', "
                         f"game='{stream.game}')")
            except errors.NotFound:
                LOG.warning(f"[{channel_repr}] The notification for '{stream.name}' sent at "
                            f"'{notification.created_at}' does not exist or has been deleted")
                stream.notifications_by_channel_id[channel.id].remove(notification)

    async def refresh_outdated_subscriptions(self):
        LOG.debug("Subscriptions refresh task running...")
        while True:
            await self.webhook_server.refresh_outdated_subscriptions()
            await asyncio.sleep(3600)

    async def delete_old_notifications(self):
        """Delete the old offline stream notifications."""
        LOG.debug("Old notifications deletion task running...")
        while True:
            for stream in self.bot.streams.values():
                old_notifications = [notification for notification in stream.notifications
                                     if models.NotificationHandler.is_deprecated(notification)]
                for notification in old_notifications:
                    channel = notification.channel
                    channel_repr = utils.get_channel_repr(channel)
                    try:
                        await notification.delete()
                        stream.notifications_by_channel_id[channel.id].remove(notification)
                        LOG.debug(f"[{channel_repr}] Offline notification for '{stream.name}', sent the "
                                  f"'{notification.created_at}', offline since '{stream.last_offline_date}' has "
                                  f"been deleted")
                        if not stream.notifications_by_channel_id[channel.id]:
                            del stream.notifications_by_channel_id[channel.id]
                    except errors.NotFound:
                        LOG.warning(f"[{channel_repr}] The notification for '{stream.name}' sent at "
                                    f"'{notification.created_at}' does not exist or has been deleted")
                        stream.notifications_by_channel_id[channel.id].remove(notification)
            await asyncio.sleep(60)
    # COMMANDS

    @commands.group()
    @commands.guild_only()
    async def stream(self, ctx):
        """Manage tracked streams."""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), command_name=ctx.command.name)

    @stream.command()
    @commands.guild_only()
    async def list(self, ctx):
        """Show the list of the current tracked streams."""
        channel_repr = utils.get_channel_repr(ctx.channel)
        records = await self.channel_stream_db_driver.get_stream_list(ctx.guild.id)

        if records:

            # Build the output data by storing every stream names notified for each discord channel
            # {
            #   <discord_channel_1>: ["stream_name_1", "stream_name_2", ...]
            #   <discord_channel_2>: ["stream_name_2", "stream_name_3", ...]
            #   <discord_channel_3>: ["stream_name_1", "stream_name_3", ...]
            # }
            streams_by_channel = collections.defaultdict(list)
            for record in records:
                channel_id, stream_name = record.values()
                channel = self.bot.get_channel(channel_id)
                streams_by_channel[channel].append(stream_name)

            # Build an embed displaying the output data.
            # - The discord channels are sorted in the same order as on the server
            # - The stream names are sorted in alphabetical order
            message = "Tracked channels"
            embed = models.StreamListEmbed(streams_by_channel)

            await self.bot.send(ctx.channel, message, embed=embed, reaction=True)
            LOG.debug(f"[{channel_repr}] Database: {streams_by_channel}")

    async def _add_streams(self, channel, *user_logins, tags=None):
        users_by_login = await self.client.get_users_by_login(*user_logins)
        channel_repr = utils.get_channel_repr(channel)
        if users_by_login:
            if not await self.channel_db_driver.exists(id=channel.id):
                # Store the discord channel in the database if nothing was tracked in it before
                await self.channel_db_driver.create(id=channel.id, name=channel.name, guild_id=channel.guild.id,
                                                    guild_name=channel.guild.name)
            else:
                LOG.debug(f"[{channel_repr}] The channel has already been stored in the database")
            tasks = [self._add_stream(channel, user['login'], user['id'], tags) for user in users_by_login.values()]
            return await asyncio.gather(*tasks, loop=self.bot.loop)

    async def _add_stream(self, channel, user_login, user_id, tags=None):
        """Add a stream in a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param user_login: The stream name to notify
        :param user_login: The stream id to notify
        :param tags: List of tags to add to the notification
        """
        channel_stream = await self.channel_stream_db_driver.get(stream_id=user_id, channel_id=channel.id)
        channel_repr = utils.get_channel_repr(channel)
        if not channel_stream:
            if not await self.stream_db_driver.exists(id=user_id):
                # Store the twitch stream in the database if it wasn't tracked anywhere before
                stream = await self.stream_db_driver.create(id=user_id, name=user_login)
                self.bot.streams[user_id] = stream
                await self.webhook_server.subscribe(user_id)
            else:
                LOG.debug(f"[{channel_repr}] The stream '{user_login}' has already been stored in the database")
            LOG.info(f"[{channel_repr}] '{user_login}' is now tracked in the channel")

            # Create a new relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.create(channel_id=channel.id, stream_id=user_id, tags=tags)
        elif not channel_stream.tags == tags:
            await self.channel_stream_db_driver.update('tags', tags, channel_id=channel.id, stream_id=user_id)
            LOG.info(f"[{channel_repr}] The notification tags for '{user_login}' has been changed from "
                     f"'{channel_stream.tags}' to '{tags}'")
        else:
            LOG.warning(f"[{channel_repr}] '{user_login}' is already track in the channel")
        return True

    @stream.command()
    @commands.guild_only()
    @check.is_admin()
    async def add(self, ctx, *user_logins):
        """Track a list of streams in a channel."""
        if not user_logins:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *user_logins)
        if result and all(result):
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.guild_only()
    @check.is_admin()
    async def everyone(self, ctx, *user_logins):
        """Track a list of streams in a channel (with @everyone)."""
        if not user_logins:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *user_logins, tags="@everyone")
        if result and all(result):
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.guild_only()
    @check.is_admin()
    async def here(self, ctx, *user_logins):
        """Track a list of streams in a channel (with `@here`)."""
        if not user_logins:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *user_logins, tags="@here")
        if result and all(result):
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    async def _remove_streams(self, channel, *user_logins):
        users_by_login = await self.client.get_users_by_login(*user_logins)
        channel_repr = utils.get_channel_repr(channel)
        if users_by_login:
            tasks = [self._remove_stream(channel, user['login'], user['id']) for user in users_by_login.values()]
            result = await asyncio.gather(*tasks, loop=self.bot.loop)

            # Remove the discord channel from the database if there no streams notified in it anymore
            if not await self.channel_stream_db_driver.exists(channel_id=channel.id):
                LOG.debug(f"[{channel_repr}] There is no stream tracked in the channel anymore, the channel is "
                          f"deleted from the database")
                await self.channel_db_driver.delete(id=channel.id)
            return result

    async def _remove_stream(self, channel, user_login, user_id):
        channel_stream = await self.channel_stream_db_driver.get(stream_id=user_id, channel_id=channel.id)
        channel_repr = utils.get_channel_repr(channel)
        if channel_stream:
            # Remove the relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.delete(channel_id=channel.id, stream_id=user_id)
            LOG.info(f"[{channel_repr}] '{user_login}' is no longer tracked in the channel")

            # Remove the twitch stream from the database of it's not notified anymore
            if not await self.channel_stream_db_driver.exists(stream_id=user_id):
                LOG.debug(f"[{channel_repr}] The stream '{user_login}' is no longer tracked in any channel, the "
                          f"stream is deleted from the database")
                await self.stream_db_driver.delete(id=user_id)
                await self.webhook_server.unsubscribe(user_id)
                self.bot.streams.pop(user_id)
        else:
            LOG.debug(f"[{channel_repr}] '{user_login}' is not tracked in the channel")
        return True

    @stream.command()
    @commands.guild_only()
    @check.is_admin()
    async def remove(self, ctx, *stream_names):
        """Stop tracking a list of streams in a channel."""
        if not stream_names:
            raise MissingStreamName
        result = await self._remove_streams(ctx.channel, *stream_names)
        if result and all(result):
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)
