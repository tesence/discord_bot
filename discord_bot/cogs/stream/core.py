import asyncio
import collections
import logging

from discord import errors
from discord.ext import commands

from discord_bot import api
from discord_bot import cfg
from discord_bot import cogs
from discord_bot.cogs.stream import embeds
from discord_bot import db
from discord_bot.emoji import Emoji
from discord_bot import utils

CONF = cfg.CONF
LOG = logging.getLogger('bot')

CONF_VARIABLES = ['TWITCH_API_URL', 'TWITCH_API_ACCEPT', 'TWITCH_API_CLIENT_ID',
                  'MIN_OFFLINE_DURATION']


class MissingStreamName(commands.MissingRequiredArgument):

    def __init__(self):
        self.message = "At least one stream name is required"


class StreamManager(cogs.DBCogMixin):

    def __init__(self, bot):
        type(self).__name__ = "Stream commands"
        super(StreamManager, self).__init__(bot, *CONF_VARIABLES)
        self.client = api.TwitchAPIClient(self.bot.loop)
        asyncio.ensure_future(self.configure_database(), loop=self.bot.loop)

    async def configure_database(self):
        await self.connection_ready.wait()

        self.stream_db_driver = db.StreamDBDriver(self.pool, self.bot.loop)
        self.channel_db_driver = db.ChannelDBDriver(self.pool, self.bot.loop)
        self.channel_stream_db_driver = db.ChannelStreamDBDriver(self.pool, self.bot.loop)

        streams = await self.stream_db_driver.list()
        LOG.debug(f"Streams={streams}")

        channels = await self.channel_db_driver.list()
        LOG.debug(f"Channels={channels}")

        channel_streams = await self.channel_stream_db_driver.list()
        LOG.debug(f"ChannelStreams={channel_streams}")

        self.streams_by_id = {s.id: s for s in streams}

    async def on_ready(self):
        try:
            asyncio.ensure_future(self.poll_streams(), loop=self.bot.loop)
        except:
            LOG.exception("The polling unexpectedly stopped")

    async def poll_streams(self):
        """Poll twitch every X seconds."""

        LOG.debug("The polling has started")

        async def on_stream_online(stream, notified_channels):
            """ Method called if twitch stream goes online.

            :param stream: The stream going online
            :param notified_channels: The discord channels in which the stream is tracked
            """
            # Send the notifications in every discord channel the stream has been tracked
            for notified_channel in notified_channels:
                message, embed = embeds.get_notification(stream, notified_channel.tags)
                notification = await self.bot.send(notified_channel.channel, message, embed=embed, reaction=True)
                stream.notifications.append(notification)

        async def on_stream_offline(stream, notified_channels):
            """Method called if the twitch stream is going offline.

            :param stream: The stream going offline
            :param notified_channels: The discord channels in which the stream is tracked
            """
            for notification in stream.notifications:
                try:
                    if getattr(CONF, 'AUTO_DELETE_OFFLINE_STREAMS', True):
                        await notification.delete()
                        LOG.debug(f"The notification for '{stream.name}' sent at '{notification.created_at}' has been "
                                  f"deleted")
                    else:
                        embed = stream.notifications[0].embeds[0]
                        offline_embed = embeds.get_offline_embed(embed)
                        await notification.edit(content="", embed=offline_embed)
                        LOG.debug(f"The notification for '{stream.name}' sent at '{notification.created_at}' has been "
                                  f"edited at '{notification.edited_at}'")
                    stream.notifications.remove(notification)
                except errors.NotFound:
                    LOG.warning(f"The notification for '{stream.name}' sent at '{notification.created_at}' does not "
                                f"exist or has already been deleted")

        async def on_stream_update(stream, title=None, game=None):
            for notification in stream.notifications:
                try:
                    embed = notification.embeds[0]
                    fields = embed.fields
                    if not stream.title == title:
                        LOG.debug(f"{stream.display_name} has changed the title of the stream from '{stream.title}' "
                                  f"to '{title}'")
                        embed.set_field_at(index=0, name=fields[0].name, value=title, inline=fields[0].inline)
                    if not stream.game == game:
                        LOG.debug(f"{stream.display_name} has changed the game of the stream from '{stream.game}' "
                                  f"to '{game}'")
                        embed.set_field_at(index=1, name=fields[1].name, value=game, inline=fields[1].inline)
                    await notification.edit(embed=embed)
                except errors.NotFound:
                    LOG.warning(f"The notification for '{stream.name}' sent at '{notification.created_at}' does not "
                                f"exist or has already been deleted")

        while True:
            # Build a dictionary to easily iterate through the tracked streams
            # {
            #   "stream_id_1": [(<discord_channel_1>, everyone=True), (<discord_channel_2>, everyone=False|True), ...]
            #   "stream_id_2": [(<discord_channel_2>, everyone=True), (<discord_channel_3>, everyone=False|True), ...]
            #   "stream_id_3": [(<discord_channel_1>, everyone=True), (<discord_channel_3>, everyone=False|True), ...]
            # }
            channels_by_stream_id = collections.defaultdict(list)
            for cs in await self.channel_stream_db_driver.list():
                channel = self.bot.get_channel(cs.channel_id)
                NotifiedChannel = collections.namedtuple('NotifiedChannel', ['channel', 'tags'])
                channels_by_stream_id[cs.stream_id].append(NotifiedChannel(channel, cs.tags))

            # Get the status of all tracked streams
            status = await self.client.get_status(*[stream_id for stream_id in self.streams_by_id])

            # Check the response:
            # - If a stream is online, status is a dictionary {"stream_id" : <stream data dict>, ...}
            # - If all the streams are offline, status is an empty dict
            # - If there is no answer from the API, status is None
            if status is not None:
                for stream_id, notified_channels in channels_by_stream_id.items():
                    stream = self.streams_by_id[stream_id]

                    # If the current stream id is in the API response, the stream is currently online
                    if stream.id in status:

                        stream_status = status[stream.id]
                        stream.last_offline_date = None

                        # Store new values in variables to compare with the previous ones
                        current_name = stream_status['channel']['name']
                        current_game = stream_status['game'].strip() or "No Game"
                        current_title = stream_status['channel']['status'].strip() or "No Title"

                        if (current_title and not current_title == stream.title) or \
                           (current_game and not current_game == stream.game):
                            await on_stream_update(stream, title=current_title, game=current_game)

                        # Update streamer's name in the database if it has changed
                        if not stream.name == current_name:
                            await self.stream_db_driver.update('name', current_name, id=stream.id)
                            LOG.debug(f"'{stream.name} has changed his name to '{current_name}'"
                                      f"The value has been updated in the database")

                        # Update old values
                        stream.name = current_name
                        stream.display_name = stream_status['channel']['display_name']
                        stream.logo = stream_status['channel']['logo']
                        stream.game = current_game
                        stream.title = current_title
                        stream.type = stream_status['stream_type']

                        # If the stream was not online during the previous iteration, the stream just went online
                        if not stream.online:
                            channels_str = [f"{nc.channel.name}#{nc.channel.id}" for nc in notified_channels]
                            LOG.debug(f"{stream.name} is live (title='{stream.title}', game='{stream.game}') "
                                      f"and notified in the channels: {', '.join(channels_str)}")
                            await on_stream_online(stream, notified_channels)
                            stream.online = True

                    # If the stream is offline, but was online during the previous iteration, the stream just went
                    # offline.
                    # To avoid spam if a stream keeps going online/offline because of Twitch or bad connections,
                    # we consider a stream as offline if it was offline for at least MIN_OFFLINE_DURATION
                    elif stream.online and stream.offline_duration > CONF.MIN_OFFLINE_DURATION:
                        LOG.debug(f"{stream.name} just went offline")
                        await on_stream_offline(stream, notified_channels)
                        stream.online = False
            else:
                LOG.warning("Cannot retrieve status, the polling iteration has been skipped.")
            await asyncio.sleep(10)

    # COMMANDS

    @commands.group(pass_context=True)
    async def stream(self, ctx):
        """ Manage tracked streams """
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)

    @stream.command()
    async def list(self, ctx):
        """ Show the list of the current tracked streams """

        channel_streams = await self.channel_stream_db_driver.list()

        if channel_streams:

            streams = {stream.id: stream for stream in await self.stream_db_driver.list()}

            # Build the output data by storing every stream names notified for each discord channel
            # {
            #   <discord_channel_1>: ["stream_name_1", "stream_name_2", ...]
            #   <discord_channel_2>: ["stream_name_2", "stream_name_3", ...]
            #   <discord_channel_3>: ["stream_name_1", "stream_name_3", ...]
            # }
            streams_by_channel = collections.defaultdict(list)
            for cs in await self.channel_stream_db_driver.list():
                channel = self.bot.get_channel(cs.channel_id)
                stream = streams[cs.stream_id]
                streams_by_channel[channel].append(stream.name)

            # Build an embed displaying the output data.
            # - The discord channels are sorted in the same order as on the server
            # - The stream names are sorted in alphabetical order
            message = "Tracked channels"
            embed = embeds.get_stream_list_embed(streams_by_channel)

            await self.bot.send(ctx.channel, message, embed=embed, reaction=True)

    async def _add_streams(self, channel, *stream_names, tags=None):
        """ Add a stream in a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_names: The streams to notify
        :param tags: List of tags to add to the notification
        """
        stream_ids_by_name = await self.client.get_ids(*stream_names)
        if stream_ids_by_name:
            if not await self.channel_db_driver.get(id=channel.id):
                # Store the discord channel in the database if nothing was tracked in it before
                await self.channel_db_driver.create(id=channel.id, name=channel.name, guild_id=channel.guild.id,
                                                    guild_name=channel.guild.name)
            else:
                LOG.debug(f"The channel {channel.name}#{channel.id} has already been stored in the database")
            tasks = [self._add_stream(channel, name, id, tags) for name, id in stream_ids_by_name.items()]
            return await asyncio.gather(*tasks, loop=self.bot.loop)

    async def _add_stream(self, channel, stream_name, stream_id, tags=None):
        """ Add a stream in a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_name: The stream name to notify
        :param stream_name: The stream id to notify
        :param tags: List of tags to add to the notification
        """
        channel_stream = await self.channel_stream_db_driver.get(channel_id=channel.id, stream_id=stream_id)
        if not channel_stream:
            if not await self.stream_db_driver.get(id=stream_id):
                # Store the twitch stream in the database if it wasn't tracked anywhere before
                stream = await self.stream_db_driver.create(id=stream_id, name=stream_name)
                self.streams_by_id[stream_id] = stream
                LOG.warning(f"{stream_name}#{stream_id} is now tracked in the channel {channel.name}#{channel.id}")
            else:
                LOG.debug(f"The stream {stream_name}#{stream_id} has already been stored in the database")

            # Create a new relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.create(channel_id=channel.id, stream_id=stream_id, tags=tags)
        elif not channel_stream.tags == tags:
            await self.channel_stream_db_driver.update('tags', tags, channel_id=channel.id, stream_id=stream_id)
            LOG.debug(f"The notification tag for {stream_name} has been changed from '{channel_stream.tags}' "
                      f"to '{tags}'")
        else:
            LOG.warning(f"{stream_name}#{stream_id} is already track in the channel "
                        f"{channel.name}#{channel.id}")
        return True

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def add(self, ctx, *stream_names):
        """ Track a list of streams in a channel """
        if not stream_names:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *stream_names)
        if result and all(result):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def everyone(self, ctx, *stream_names):
        """ Track a list of streams in a channel (with @everyone) """
        if not stream_names:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *stream_names, tags="@everyone")
        if result and all(result):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def here(self, ctx, *stream_names):
        """ Track a list of streams in a channel (with @here) """
        if not stream_names:
            raise MissingStreamName
        result = await self._add_streams(ctx.channel, *stream_names, tags="@here")
        if result and all(result):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    async def _remove_streams(self, channel, *stream_names):
        """ Remove a list streams from a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_names: The streams to stop tracking
        """
        stream_ids_by_name = await self.client.get_ids(*stream_names)
        if stream_ids_by_name:
            tasks = [self._remove_stream(channel, name, id) for name, id in stream_ids_by_name.items()]
            result = await asyncio.gather(*tasks, loop=self.bot.loop)

            # Remove the discord channel from the database if there no streams notified in it anymore
            if not await self.channel_stream_db_driver.get(channel_id=channel.id) and \
                    await self.channel_db_driver.get(id=channel.id):
                LOG.debug(f"There is no stream tracked in the channel {channel.name}#{channel.id}, the channel "
                          f"is deleted from the database")
                asyncio.ensure_future(self.channel_db_driver.delete(id=channel.id), loop=self.bot.loop)
            return result

    async def _remove_stream(self, channel, stream_name, stream_id):
        """ Remove a stream from a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_name: The stream_name to stop tracking
        :param stream_id: The stream_id to stop tracking
        """
        channel_stream = await self.channel_stream_db_driver.get(channel_id=channel.id, stream_id=stream_id)
        if channel_stream:
            # Remove the relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.delete(channel_id=channel.id, stream_id=stream_id)
            LOG.debug(f"{stream_name} is no longer tracked in '{channel.guild.name}:{channel.name}'")

            # Remove the twitch stream from the database of it's not notified anymore
            if not await self.channel_stream_db_driver.get(stream_id=stream_id):
                LOG.debug(f"The stream {stream_name}#{stream_id} is no longer tracked in any channel, the "
                          f"stream is deleted from the database")
                del self.streams_by_id[stream_id]
                asyncio.ensure_future(self.stream_db_driver.delete(id=stream_id), loop=self.bot.loop)
        else:
            LOG.debug(f"The stream {stream_name}#{stream_id} is not tracked in the channel "
                      f"{channel.name}#{channel.id}")
        return True

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def remove(self, ctx, *stream_names):
        """ Stop tracking a list of streams in a channel """
        if not stream_names:
            raise MissingStreamName
        result = await self._remove_streams(ctx.channel, *stream_names)
        if result and all(result):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)


def setup(bot):
    bot.add_cog(StreamManager(bot))
