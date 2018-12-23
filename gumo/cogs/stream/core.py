import asyncio
import collections
from datetime import datetime
import itertools
import logging

import asyncpg
from discord import errors
from discord.ext import commands

from gumo import api
from gumo import check
from gumo import config
from gumo.cogs.stream.models import NotificationHandler, StreamListEmbed
from gumo import db
from gumo import emoji
from gumo import utils

LOG = logging.getLogger('bot')

MIN_OFFLINE_DURATION = 30
POLL_RATE = 5


class MissingStreamName(commands.MissingRequiredArgument):

    def __init__(self):
        self.message = "At least one stream name is required"


class StreamManager:

    def __init__(self, bot):
        type(self).__name__ = "Stream commands"
        self.__module__ = "cogs.stream"
        self.bot = bot
        self.client = api.TwitchAPIClient(self.bot.loop)
        self.stream_db_driver = db.StreamDBDriver(self.bot)
        self.channel_db_driver = db.ChannelDBDriver(self.bot)
        self.channel_stream_db_driver = db.ChannelStreamDBDriver(self.bot)
        self._cancel_tasks()
        self.bot.loop.create_task(self.init())

    def _cancel_tasks(self):
        """Reload all the tasks"""
        tasks = getattr(self.bot, 'stream_tasks', [])
        for task in tasks:
            task.cancel()
        self.bot.stream_tasks = []

    async def init(self):
        """Initialize all the manager attributes and load the database data."""
        await self.stream_db_driver.ready.wait()
        await self.channel_db_driver.ready.wait()
        await self.channel_stream_db_driver.ready.wait()

        previous_streams = getattr(self.bot, 'streams', None)
        self.bot.streams = previous_streams or {stream.id: stream for stream in await self.stream_db_driver.list()}

        await self.bot.wait_until_ready()

        self.bot.stream_tasks.append(self.bot.loop.create_task(self.poll_streams()))
        self.bot.stream_tasks.append(self.bot.loop.create_task(self.delete_old_notifications()))

        def task_done_callback(fut):
            if fut.cancelled():
                LOG.debug(f"The task has been cancelled: {fut}")
                return
            error = fut.exception()
            exc_info = (type(error), error, error.__traceback__) if error else None
            LOG.error(f"A task ended unexpectedly: {fut} ", exc_info=exc_info)

        for task in self.bot.stream_tasks:
            task.add_done_callback(task_done_callback)

    async def delete_old_notifications(self):
        """Delete the old offline stream notifications."""
        while True:
            for stream in self.bot.streams.values():
                old_notifications = [notification for notification in stream.notifications
                                     if NotificationHandler.is_deprecated(notification)]
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

    async def on_stream_online(self, stream, channel_streams):
        """Method called if twitch stream goes online.

        :param stream: The data of the stream going online
        :param channel_streams: The discord channels in which the stream is tracked
        """
        for channel_stream in channel_streams:
            channel = self.bot.get_channel(channel_stream.channel_id)
            if 'stream' not in config.get('EXTENSIONS', guild_id=channel.guild.id):
                LOG.debug(f"The stream extensions is not enable on the server '{channel.guild}', the notifications "
                          f"are not sent")
                continue
            tags = channel_stream.tags
            channel_repr = utils.get_channel_repr(channel)
            message, embed = NotificationHandler.get_info(stream, tags)
            recent_notification = stream.get_recent_notification(channel.id)
            if recent_notification:
                await recent_notification.edit(content=message, embed=embed)
                LOG.debug(f"[{channel_repr}] '{stream.name}' was live recently, recent notification edited")
            else:
                notification = await self.bot.send(channel, message, embed=embed)
                stream.notifications_by_channel_id[channel.id].append(notification)
                LOG.debug(f"[{channel_repr}] Notification for '{stream.name}' sent")

    async def on_stream_offline(self, stream, channel_streams):
        """Method called if the twitch stream is going offline.

        :param stream: The data of the stream going offline
        :param channel_streams: The discord channels in which the stream is tracked
        """
        stream.last_offline_date = datetime.utcnow()
        online_notifications = [notification for notification in stream.notifications
                                if NotificationHandler.is_online(notification)]
        for notification in online_notifications:
            channel = notification.channel
            channel_repr = utils.get_channel_repr(channel)
            try:
                message, embed = NotificationHandler.get_info(stream)
                await notification.edit(content=message, embed=embed)
                LOG.debug(f"[{channel_repr}] Notification for '{stream.name}' edited")
            except errors.NotFound:
                LOG.warning(f"[{channel_repr}] The notification for '{stream.name}' sent at "
                            f"'{notification.created_at}' does not exist or has been deleted")
                stream.notifications_by_channel_id[channel.id].remove(notification)
        stream.title = None
        stream.game = None

    async def on_stream_update(self, stream, title=None, game=None):
        """Method called if the twitch stream is update.

        :param stream: The data of the stream being update
        :param title: New title
        :param game: New game
        """
        for notifications in stream.notifications_by_channel_id.values():
            notification = next((notification for notification in notifications
                                 if NotificationHandler.is_online(notification)), None)
            channel = notification.channel
            channel_repr = utils.get_channel_repr(channel)
            try:
                _, embed = NotificationHandler.extract_info(notification)
                fields = embed.fields
                if not stream.title == title:
                    LOG.info(f"[{channel_repr}] '{stream.name}' has changed the stream title from "
                             f"'{stream.title}' to '{title}'")
                    embed.set_field_at(index=0, name=fields[0].name, value=title, inline=fields[0].inline)
                if not stream.game == game:
                    LOG.info(f"[{channel_repr}] '{stream.name}' has changed the stream game from "
                             f"'{stream.game}' to '{game}'")
                    embed.set_field_at(index=1, name=fields[1].name, value=game, inline=fields[1].inline)
                await notification.edit(embed=embed)
            except errors.NotFound:
                LOG.warning(f"[{channel_repr}] The notification for '{stream.name}' sent at "
                            f"'{notification.created_at}' does not exist or has been deleted")
                stream.notifications_by_channel_id[channel.id].remove(notification)

    async def poll_streams(self):
        """Poll twitch every X seconds."""
        LOG.debug("The polling has started")

        while True:

            try:
                channel_streams_db = await self.channel_stream_db_driver.list()
            except asyncpg.PostgresError:
                LOG.exception(f"Cannot retrieve the channel streams, iteration skipped")
                await asyncio.sleep(POLL_RATE)
                continue

            channel_streams_by_stream_id = {
                stream_id: list(channel_streams)
                for stream_id, channel_streams in itertools.groupby(channel_streams_db, key=lambda x: x.stream_id)
            }

            # Get the status of all tracked streams
            status = await self.client.get_status(*self.bot.streams)

            # Check the response:
            # - If a stream is online, status is a dictionary {"stream_id" : <stream data dict>, ...}
            # - If all the streams are offline, status is an empty dict
            # - If there is no answer from the API, status is None
            if status is None:
                continue

            for stream in self.bot.streams.values():

                channel_streams = channel_streams_by_stream_id[stream.id]

                # If the current stream id is in the API response, the stream is currently online
                if stream.id in status:

                    stream_status = status[stream.id]

                    # Store new values in variables to compare with the previous ones
                    current_name = stream_status['channel']['name']
                    current_game = stream_status['game'].strip() or "No Game"
                    current_title = stream_status['channel']['status'].strip() or "No Title"

                    if (stream.title and not current_title == stream.title) or \
                       (stream.game and not current_game == stream.game):
                        await self.on_stream_update(stream, title=current_title, game=current_game)

                    # Update streamer's name in the database if it has changed
                    if not stream.name == current_name:
                        await self.stream_db_driver.update('name', current_name, id=stream.id)
                        LOG.info(f"{stream.name} has changed her/his name to '{current_name}'. The value has been "
                                 f"updated in the database")

                    # Update old values
                    stream.name = current_name
                    stream.display_name = stream_status['channel']['display_name']
                    stream.logo = stream_status['channel']['logo']
                    stream.game = current_game
                    stream.title = current_title
                    stream.type = stream_status['stream_type']

                    # If the stream was not online during the previous iteration, the stream just went online
                    if not stream.online:
                        stream.online = True
                        stream.last_offline_date = None
                        LOG.info(f"'{stream.name}' is online")
                        await self.on_stream_online(stream, channel_streams)

                # If the stream is offline, but was online during the previous iteration, the stream just went
                # offline.
                # To avoid spam if a stream keeps going online/offline because of Twitch or bad connections,
                # we consider a stream as offline if it was offline for at least MIN_OFFLINE_DURATION
                elif stream.online:
                    stream.last_offline_date = stream.last_offline_date or datetime.utcnow()
                    if stream.offline_duration > MIN_OFFLINE_DURATION:
                        stream.online = False
                        LOG.info(f"'{stream.name}' is offline")
                        await self.on_stream_offline(stream, channel_streams)
            await asyncio.sleep(POLL_RATE)

    # COMMANDS

    @commands.group()
    @commands.guild_only()
    async def stream(self, ctx):
        """Manage tracked streams."""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)

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
            embed = StreamListEmbed(streams_by_channel)

            await self.bot.send(ctx.channel, message, embed=embed, reaction=True)
            LOG.debug(f"[{channel_repr}] Database: {streams_by_channel}")

    async def _add_streams(self, channel, *stream_names, tags=None):
        """Add a stream in a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_names: The streams to notify
        :param tags: List of tags to add to the notification
        """
        stream_ids_by_name = await self.client.get_ids(*stream_names)
        channel_repr = utils.get_channel_repr(channel)
        if stream_ids_by_name:
            if not await self.channel_db_driver.exists(id=channel.id):
                # Store the discord channel in the database if nothing was tracked in it before
                await self.channel_db_driver.create(id=channel.id, name=channel.name, guild_id=channel.guild.id,
                                                    guild_name=channel.guild.name)
            else:
                LOG.debug(f"[{channel_repr}] The channel has already been stored in the database")
            tasks = [self._add_stream(channel, name, id, tags) for name, id in stream_ids_by_name.items()]
            return await asyncio.gather(*tasks, loop=self.bot.loop)

    async def _add_stream(self, channel, stream_name, stream_id, tags=None):
        """Add a stream in a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_name: The stream name to notify
        :param stream_name: The stream id to notify
        :param tags: List of tags to add to the notification
        """
        channel_stream = await self.channel_stream_db_driver.get(stream_id=stream_id, channel_id=channel.id)
        channel_repr = utils.get_channel_repr(channel)
        if not channel_stream:
            if not await self.stream_db_driver.exists(id=stream_id):
                # Store the twitch stream in the database if it wasn't tracked anywhere before
                stream = await self.stream_db_driver.create(id=stream_id, name=stream_name)
                self.bot.streams[stream_id] = stream
            else:
                LOG.debug(f"[{channel_repr}] The stream '{stream_name}' has already been stored in the database")
            LOG.info(f"[{channel_repr}] '{stream_name}' is now tracked in the channel")

            # Create a new relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.create(channel_id=channel.id, stream_id=stream_id, tags=tags)
        elif not channel_stream.tags == tags:
            await self.channel_stream_db_driver.update('tags', tags, channel_id=channel.id, stream_id=stream_id)
            LOG.info(f"[{channel_repr}] The notification tags for '{stream_name}' has been changed from "
                     f"'{channel_stream.tags}' to '{tags}'")
        else:
            LOG.warning(f"[{channel_repr}] '{stream_name}' is already track in the channel")
        return True

    @stream.command()
    @commands.guild_only()
    @check.is_admin()
    async def add(self, ctx, *stream_names):
        """Track a list of streams in a channel."""
        if not stream_names:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *stream_names)
        if result and all(result):
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.guild_only()
    @check.is_admin()
    async def everyone(self, ctx, *stream_names):
        """Track a list of streams in a channel (with @everyone)."""
        if not stream_names:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *stream_names, tags="@everyone")
        if result and all(result):
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.guild_only()
    @check.is_admin()
    async def here(self, ctx, *stream_names):
        """Track a list of streams in a channel (with @here)."""
        if not stream_names:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *stream_names, tags="@here")
        if result and all(result):
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    async def _remove_streams(self, channel, *stream_names):
        """Remove a list streams from a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_names: The streams to stop tracking
        """
        stream_ids_by_name = await self.client.get_ids(*stream_names)
        channel_repr = utils.get_channel_repr(channel)
        if stream_ids_by_name:
            tasks = [self._remove_stream(channel, name, id) for name, id in stream_ids_by_name.items()]
            result = await asyncio.gather(*tasks, loop=self.bot.loop)

            # Remove the discord channel from the database if there no streams notified in it anymore
            if not await self.channel_stream_db_driver.exists(channel_id=channel.id):
                LOG.debug(f"[{channel_repr}] There is no stream tracked in the channel anymore, the channel is "
                          f"deleted from the database")
                await self.channel_db_driver.delete(id=channel.id)
            return result

    async def _remove_stream(self, channel, stream_name, stream_id):
        """Remove a stream from a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_name: The stream_name to stop tracking
        :param stream_id: The stream_id to stop tracking
        """
        channel_stream = await self.channel_stream_db_driver.get(stream_id=stream_id, channel_id=channel.id)
        channel_repr = utils.get_channel_repr(channel)
        if channel_stream:
            # Remove the relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.delete(channel_id=channel.id, stream_id=stream_id)
            LOG.info(f"[{channel_repr}] '{stream_name}' is no longer tracked in the channel")

            # Remove the twitch stream from the database of it's not notified anymore
            if not await self.channel_stream_db_driver.exists(stream_id=stream_id):
                LOG.debug(f"[{channel_repr}] The stream '{stream_name}' is no longer tracked in any channel, the "
                          f"stream is deleted from the database")
                await self.stream_db_driver.delete(id=stream_id)
                self.bot.streams.pop(stream_id)
        else:
            LOG.debug(f"[{channel_repr}] '{stream_name}' is not tracked in the channel")
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
