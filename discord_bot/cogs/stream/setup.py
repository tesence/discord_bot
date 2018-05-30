import asyncio
import collections
import logging

from discord.ext import commands
from discord import colour, embeds

from discord_bot import cfg
from discord_bot import log
from discord_bot import utils

from discord_bot.api import twitch as api

from discord_bot.cogs.stream import db


CONF = cfg.CONF
LOG = logging.getLogger('debug')


TWITCH_ICON_URL = "https://www.shareicon.net/download/2015/09/08/98061_twitch_512x512.png"
CLOCK_ICON_URL = "https://cdn2.iconfinder.com/data/icons/metro-uinvert-dock/256/Clock.png"


class StreamManager:

    def __init__(self, bot):
        type(self).__name__ = "Stream commands"
        self.bot = bot
        self.db_driver = db.DBDriver()
        self.streams_by_id = {}

    async def start(self):
        """Initialization."""

        await self.db_driver.setup()

        streams = await self.db_driver.get_stream()
        LOG.debug(f"Streams={streams}")

        channels = await self.db_driver.get_channel()
        LOG.debug(f"Channels={channels}")

        channel_streams = await self.db_driver.get_channel_stream()
        LOG.debug(f"ChannelStreams={channel_streams}")

        self.streams_by_id = {stream.id: stream for stream in streams}

        try:
            await self.poll_streams()
        except asyncio.TimeoutError as e:
            message = "The polling unexpectedly stopped"
            LOG.exception(log.get_log_exception_message(message, e))

    @staticmethod
    def _get_notification(status, everyone=False):
        """Send a message in discord chat to notify that a stream went online.

        :param status: status object
        :param everyone: True if the stream is notified with @everyone, False otherwise
        """

        display_name = status['channel']['display_name']
        game = status['game']
        title = status['channel']['status']
        logo_url = status['channel']['logo']
        url = status['channel']['url']

        message = ""
        message = message + "@everyone " if everyone else message

        message += f"{display_name} is streaming!"

        embed = embeds.Embed()
        embed.colour = colour.Color.dark_blue()
        embed.description = f"[{url}]({url})"

        embed.set_author(name=display_name, url=url, icon_url=TWITCH_ICON_URL)
        embed.add_field(name="Playing", value=game + (50 - len(game)) * " ** **", inline=False)
        embed.add_field(name="Stream Title", value=title, inline=False)
        embed.set_footer(text="Stream live time", icon_url=CLOCK_ICON_URL)

        if logo_url:
            embed.set_thumbnail(url=logo_url)

        return message, embed

    async def poll_streams(self):
        """Poll twitch every X seconds."""

        LOG.debug("The polling has started")

        async def on_stream_online(stream, notified_channels, status):
            """ Method called if twitch stream goes online.

            :param stream: The stream going online
            :param notified_channels: The discord channels in which the stream is tracked
            :param status: the API data for the stream going line
            """
            # Send the notifications in every discord channel the stream has been tracked
            for notified_channel in notified_channels:
                channel = notified_channel[0]
                everyone = notified_channel[1]
                message, embed = self._get_notification(status[stream.id], everyone)
                await self.bot._send(channel, message, embed=embed)

        async def on_stream_offline(stream):
            """Method called if the twitch stream is going offline.

            :param stream: The stream going offline
            """
            pass

        while True:

            # Build a dictionary to easily iterate through the tracked streams
            # {
            #   "stream_id_1": [(<discord_channel_1>, everyone=True), (<discord_channel_2>, everyone=False|True), ...]
            #   "stream_id_2": [(<discord_channel_2>, everyone=True), (<discord_channel_3>, everyone=False|True), ...]
            #   "stream_id_3": [(<discord_channel_1>, everyone=True), (<discord_channel_3>, everyone=False|True), ...]
            # }
            channels_by_stream_id = collections.defaultdict(list)
            for cs in await self.db_driver.get_channel_stream():
                channel = self.bot.get_channel(cs.channel_id)
                channels_by_stream_id[cs.stream_id].append((channel, cs.everyone))

            # Get the status of all tracked streams
            status = await api.get_status(*[stream_id for stream_id in self.streams_by_id])

            # Check the response:
            # - If a stream is online, status is a dictionary {"stream_id" : <stream data dict>, ...}
            # - If all the streams are offline, status is an empty dict
            # - If there is no answer from the API, status is None
            if status is not None:
                for stream_id, notified_channels in channels_by_stream_id.items():
                    stream = self.streams_by_id[stream_id]

                    # If the current stream id is in the API response, the stream is currently online
                    if stream.id in status:
                        stream.last_offline_date = None

                        # Update streamer's name in the database if it has changed
                        if not stream.name == status[stream.id]['channel']['name']:
                            stream.update(name=status[stream.id]['channel']['name']).apply()

                        # If the stream was not online during the previous iteration, the stream just went online
                        if not stream.is_online:
                            await on_stream_online(stream, notified_channels, status)
                            channels_str = [f"{nc[0].name}#{nc[0].id}" for nc in notified_channels]
                            LOG.debug(f"{stream.name} is live and notified in the channels: {', '.join(channels_str)}")
                            stream.is_online = True

                    # If the stream is offline, but was online during the previous iteration, the stream just went
                    # offline.
                    # To avoid spam if a stream keeps going online/offline because of Twitch or bad connections,
                    # we consider a stream as offline if it was offline for at least MIN_OFFLINE_DURATION
                    elif stream.is_online and stream.offline_duration > CONF.MIN_OFFLINE_DURATION:
                            await on_stream_offline(stream)
                            stream.is_online = False
                            LOG.debug(f"{stream.name} just went offline")
            else:
                LOG.warning("Cannot retrieve status, the polling iteration has been skipped.")
            await asyncio.sleep(10)

    # COMMANDS

    @commands.group(pass_context=True)
    async def stream(self, ctx):
        """Manage tracked streams."""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), "stream")

    @stream.command()
    async def list(self, ctx):
        """List current tracked streams."""

        channel_streams = await self.db_driver.get_channel_stream()

        if channel_streams:

            streams = {stream.id: stream for stream in await self.db_driver.get_stream()}

            # Build the output data by storing every stream names notified for each discord channel
            # {
            #   <discord_channel_1>: ["stream_name_1", "stream_name_2", ...]
            #   <discord_channel_2>: ["stream_name_2", "stream_name_3", ...]
            #   <discord_channel_3>: ["stream_name_1", "stream_name_3", ...]
            # }
            streams_by_channel = collections.defaultdict(list)
            for cs in await self.db_driver.get_channel_stream():
                channel = self.bot.get_channel(cs.channel_id)
                stream = streams[cs.stream_id]
                streams_by_channel[channel].append(stream.name)

            # Build an embed displaying the output data.
            # - The discord channels are sorted in the same order as on the server
            # - The stream names are sorted in alphabetical order
            message = "Tracked channels"
            embed = embeds.Embed()
            embed.set_author(name="Streams", icon_url=TWITCH_ICON_URL)
            for channel, streams in sorted(streams_by_channel.items(), key=lambda x: x[0].position):
                stream_links = [f"[{stream}](https://twitch.tv/{stream})" for stream in sorted(streams)]
                embed.add_field(name=channel.name, value=", ".join(stream_links), inline=False)

            await self.bot._send(ctx.message.channel, message, embed=embed)

    async def _add_stream(self, channel, stream_name, everyone=False):
        """ Add a stream in a discord channel tracklist

        :param channel: The discord channel in which the stream notifications are enabled
        :param stream_name: The stream to notify
        :param everyone: If True, add the tag @everyone to the bot notification
        """
        stream_name = stream_name.lower()
        stream_id = int((await api.get_ids(stream_name))[stream_name])
        if not await self.db_driver.get_channel_stream(channel_id=channel.id, stream_id=stream_id):

            # Store the twitch stream in the database if it wasn't tracked anywhere before
            if not await self.db_driver.get_stream(name=stream_name):
                stream = await self.db_driver.create_stream(id=stream_id, name=stream_name)
                self.streams_by_id[stream_id] = stream
            else:
                LOG.debug(f"The stream {stream_name}#{stream_id} has already been stored in the database")

            # Store the discord channel in the database if it wasn't tracked anywhere before
            if not await self.db_driver.get_channel(id=channel.id):
                await self.db_driver.create_channel(id=channel.id, name=channel.name, guild_id=channel.guild.id,
                                                    guild_name=channel.guild.name)
            else:
                LOG.debug(f"The channel {channel.name}#{channel.id} has already been stored in the database")

            # Create a new relation between the twitch stream and the discord channel
            await self.db_driver.create_channel_stream(channel_id=channel.id, stream_id=stream_id, everyone=everyone)
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
        channel = ctx.message.channel
        if await self._add_stream(channel, stream_name.lower()):
            await self.bot._send(channel, f"{stream_name} is now tracked in '{channel.guild.name}:{channel.name}'",
                                 code_block=True)

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def everyone(self, ctx, stream_name):
        """ Add a stream to the tracked list (with @everyone)

        :param ctx: command context
        :param stream_name: The stream to notify
        """
        channel = ctx.message.channel
        if await self._add_stream(channel, stream_name.lower(), everyone=True):
            await self.bot._send(channel, f"{stream_name} is now tracked in '{channel.guild.name}:{channel.name}'",
                                 code_block=True)

    async def _remove_stream(self, channel, stream_name):
        stream_id = int((await api.get_ids(stream_name))[stream_name])
        channel_streams = await self.db_driver.get_channel_stream(channel_id=channel.id, stream_id=stream_id)
        if channel_streams:
            channel_stream = channel_streams[0]
            channel_db = (await self.db_driver.get_channel(id=channel_stream.channel_id))[0]
            stream_db = (await self.db_driver.get_stream(id=channel_stream.stream_id))[0]

            # Remove the relation between the twitch stream and the discord channel
            await channel_stream.delete()
            LOG.debug(f"{stream_db.name} is no longer tracked in '{channel.guild.name}:{channel.name}'")

            # Remove the discord channel from the database if there no streams notified in it
            if not await self.db_driver.get_channel_stream(channel_id=channel.id):
                LOG.debug(f"There is no stream tracked in the channel {channel.name}#{channel.id}, the channel is "
                          "deleted from the database")
                await channel_db.delete()

            # Remove the twitch stream from the database of it's not notified anymore
            if not await self.db_driver.get_channel_stream(stream_id=stream_id):
                LOG.debug(f"The stream {stream_db.name}#{stream_db.id} is no longer tracked in any channel, the stream "
                          "is deleted from the database")
                del self.streams_by_id[stream_db.id]
                await stream_db.delete()
            return True

    @stream.command()
    @commands.check(utils.check_is_admin)
    async def remove(self, ctx, stream_name):
        """ Disable bot notification for a stream in a specific channel

        :param ctx: command context
        :param stream_name: The stream to notify
        """
        channel = ctx.message.channel
        if await self._remove_stream(channel, stream_name.lower()):
            await self.bot._send(channel, f"{stream_name} is no longer tracked in '{channel.guild.name}:{channel.name}'",
                                 code_block=True)

    # EVENTS
    async def on_guild_channel_delete(self, channel):
        """Event called when a discord channel is deleted.

        :param channel: the deleted discord channel
        """
        LOG.debug(f"The channel '{channel.guild.name}:{channel.name}' has been deleted")

        for channel_stream in await self.db_driver.get_channel_stream(channel_id=channel.id):

            stream = (await self.db_driver.get_stream(id=channel_stream.stream_id))[0]
            await channel_stream.delete()
            LOG.debug(f"{stream.name} is no longer tracked in '{channel.guild.name}:{channel.name}'")

            # Remove the twitch stream from the database of it's not notified anymore
            if not await self.db_driver.get_channel_stream(stream_id=stream.id):
                LOG.debug(f"The stream {stream.name}#{stream.id} is no longer tracked in any channel, the stream is "
                          "deleted from the database")
                await stream.delete()


def setup(bot):
    stream_manager = StreamManager(bot)
    bot.add_cog(stream_manager)

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(stream_manager.start(), loop=loop)
