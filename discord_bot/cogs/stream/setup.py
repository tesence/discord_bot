import asyncio
import collections
import logging

from discord import errors
from discord.ext import commands

from discord_bot import cfg
from discord_bot.db import stream
from discord_bot.emoji import Emoji
from discord_bot import utils

from discord_bot.api import twitch
from discord_bot.cogs import base

from discord_bot.cogs.stream import embeds

CONF = cfg.CONF
LOG = logging.getLogger('bot')

CONF_VARIABLES = ['TWITCH_API_URL', 'TWITCH_API_ACCEPT', 'TWITCH_API_CLIENT_ID',
                  'MIN_OFFLINE_DURATION']


class StreamManager(base.DBCogMixin):

    def __init__(self, bot):
        type(self).__name__ = "Stream commands"
        super(StreamManager, self).__init__(bot, *CONF_VARIABLES)
        self.client = twitch.TwitchAPIClient(self.bot.loop)
        self.stream_db_driver = stream.StreamDBDriver(self.bot.loop)
        self.channel_db_driver = stream.ChannelDBDriver(self.bot.loop)
        self.channel_stream_db_driver = stream.ChannelStreamDBDriver(self.bot.loop)

        asyncio.ensure_future(self.load_database_data(), loop=self.bot.loop)

    async def load_database_data(self):

        streams = await self.stream_db_driver.list()
        LOG.debug(f"Streams={streams}")

        channels = await self.channel_db_driver.list()
        LOG.debug(f"Channels={channels}")

        channel_streams = await self.channel_stream_db_driver.list()
        LOG.debug(f"ChannelStreams={channel_streams}")

        self.streams_by_id = {stream.id: stream for stream in streams}

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
            embed = stream.notifications[0].embeds[0]
            offline_embed = embeds.get_offline_embed(embed)
            for notification in stream.notifications:
                try:
                    await notification.edit(content="", embed=offline_embed)
                    stream.notifications.remove(notification)
                    LOG.debug(f"The notification for {stream.name} sent at {notification.created_at} has been edited at"
                              f" {notification.edited_at}")
                except errors.NotFound:
                    LOG.warning(f"The notification for {stream.name} sent at {notification.created_at} does not exist "
                                f"or has already been deleted")

        async def on_stream_update(stream, title=None, game=None):
            for notification in stream.notifications:
                embed = notification.embeds[0]
                fields = embed.fields
                if not stream.title == title:
                    embed.set_field_at(index=0, name=fields[0].name, value=title, inline=fields[0].inline)
                    LOG.debug(f"{stream.display_name} has changed the title of the stream from '{stream.title}' "
                              f"to '{title}'")
                if not stream.game == game:
                    embed.set_field_at(index=1, name=fields[1].name, value=game, inline=fields[1].inline)
                    LOG.debug(f"{stream.display_name} has changed the game of the stream from '{stream.game}' "
                              f"to '{game}'")
                await notification.edit(embed=embed)

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

                        # If the stream title or game has changed, the notifications are updated
                        if (stream.title and not stream_status['channel']['status'] == stream.title) or \
                                (stream.game and not stream_status['game'] == stream.game):
                            await on_stream_update(stream, title=stream_status['channel']['status'],
                                                   game=stream_status['game'])

                        # Update streamer's name in the database if it has changed
                        if not stream.name == stream_status['channel']['name']:
                            await self.stream_db_driver.update('name', stream_status['channel']['name'], id=stream.id)
                            LOG.debug(f"'{stream.name} has changed his name to '{stream_status['channel']['name']}'"
                                      f"The value has been updated in the database")

                        stream.name = stream_status['channel']['name']
                        stream.display_name = stream_status['channel']['display_name']
                        stream.title = stream_status['channel']['status']
                        stream.game = stream_status['game']
                        stream.logo = stream_status['channel']['logo']
                        stream.type = stream_status['stream_type']

                        # If the stream was not online during the previous iteration, the stream just went online
                        if not stream.online:
                            await on_stream_online(stream, notified_channels)
                            channels_str = [f"{nc.channel.name}#{nc.channel.id}" for nc in notified_channels]
                            LOG.debug(f"{stream.name} is live and notified in the channels: {', '.join(channels_str)}")
                            stream.online = True

                    # If the stream is offline, but was online during the previous iteration, the stream just went
                    # offline.
                    # To avoid spam if a stream keeps going online/offline because of Twitch or bad connections,
                    # we consider a stream as offline if it was offline for at least MIN_OFFLINE_DURATION
                    elif stream.online and stream.offline_duration > CONF.MIN_OFFLINE_DURATION:
                        await on_stream_offline(stream, notified_channels)
                        stream.online = False
                        LOG.debug(f"{stream.name} just went offline")
            else:
                LOG.warning("Cannot retrieve status, the polling iteration has been skipped.")
            await asyncio.sleep(10)

    # COMMANDS

    @commands.group(pass_context=True)
    async def stream(self, ctx):
        """Manage tracked streams."""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)

    @stream.command()
    async def list(self, ctx):
        """List current tracked streams."""

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

    async def _add_stream(self, channel, stream_name, *tags):
        """ Add a stream in a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_name: The stream to notify
        :param tags: List of tags to add to the notification
        """
        stream_name = stream_name.lower()
        stream_id = int((await self.client.get_ids(stream_name))[stream_name])
        tags = " ".join(tags) if tags else None

        channel_stream = await self.channel_stream_db_driver.get(channel_id=channel.id, stream_id=stream_id)
        if not channel_stream:
            if not await self.stream_db_driver.get(id=stream_id):
                # Store the twitch stream in the database if it wasn't tracked anywhere before
                stream = await self.stream_db_driver.create(id=stream_id, name=stream_name)
                self.streams_by_id[stream_id] = stream
            else:
                LOG.debug(f"The stream {stream_name}#{stream_id} has already been stored in the database")

            if not await self.channel_db_driver.get(id=channel.id):
                # Store the discord channel in the database if nothing was tracked in it before
                await self.channel_db_driver.create(id=channel.id, name=channel.name, guild_id=channel.guild.id,
                                                    guild_name=channel.guild.name)
            else:
                LOG.debug(f"The channel {channel.name}#{channel.id} has already been stored in the database")

            # Create a new relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.create(channel_id=channel.id, stream_id=stream_id, tags=tags)
            return True
        elif not channel_stream.tags == tags:
            await self.channel_stream_db_driver.update('tags', tags, channel_id=channel.id, stream_id=stream_id)
            LOG.debug(f"The notification tag for {stream_name} has been changed from '{channel_stream.tags}' to "
                      f"'{tags if tags else ''}'")
            return True
        else:
            LOG.warning(f"{stream_name}#{stream_id} is already track in the channel {channel.name}#{channel.id}")
            return False

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def add(self, ctx, stream_name):
        """ Add a stream to the tracked list

        :param ctx: command context
        :param stream_name: The stream to notify
        """
        if await self._add_stream(ctx.channel, stream_name.lower()):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def everyone(self, ctx, stream_name):
        """ Add a stream to the tracked list (with @everyone)

        :param ctx: command context
        :param stream_name: The stream to notify
        """
        if await self._add_stream(ctx.channel, stream_name.lower(), "@everyone"):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def here(self, ctx, stream_name):
        """ Add a stream to the tracked list (with @here)

        :param ctx: command context
        :param stream_name: The stream to notify
        """
        if await self._add_stream(ctx.channel, stream_name.lower(), "@here"):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    async def _remove_stream(self, channel, stream_name):
        stream_id = int((await self.client.get_ids(stream_name))[stream_name])

        if await self.channel_stream_db_driver.get(channel_id=channel.id, stream_id=stream_id):

            # Remove the relation between the twitch stream and the discord channel
            await self.channel_stream_db_driver.delete(channel_id=channel.id, stream_id=stream_id)
            LOG.debug(f"{stream_name} is no longer tracked in '{channel.guild.name}:{channel.name}'")

            # Remove the discord channel from the database if there no streams notified in it anymore
            if not await self.channel_stream_db_driver.get(channel_id=channel.id):
                LOG.debug(f"There is no stream tracked in the channel {channel.name}#{channel.id}, the channel is "
                          "deleted from the database")
                await self.channel_db_driver.delete(id=channel.id)

            # Remove the twitch stream from the database of it's not notified anymore
            if not await self.channel_stream_db_driver.get(stream_id=stream_id):
                LOG.debug(f"The stream {stream_name}#{stream_id} is no longer tracked in any channel, the stream "
                          "is deleted from the database")
                del self.streams_by_id[stream_id]
                await self.stream_db_driver.delete(id=stream_id)
            return True
        return False

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def remove(self, ctx, stream_name):
        """ Disable bot notification for a stream in a specific channel

        :param ctx: command context
        :param stream_name: The stream to notify
        """
        if await self._remove_stream(ctx.channel, stream_name.lower()):
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    # EVENTS
    async def on_guild_channel_delete(self, channel):
        """Event called when a discord channel is deleted.

        :param channel: the deleted discord channel
        """
        LOG.debug(f"The channel '{channel.guild.name}:{channel.name}' has been deleted")
        await self.channel_stream_db_driver.delete(channel_id=channel.id)
        await self.channel_db_driver.delete(id=channel.id)
        await self.stream_db_driver.delete_deprecated_streams()


def setup(bot):
    bot.add_cog(StreamManager(bot))
