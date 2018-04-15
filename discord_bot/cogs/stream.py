from aiohttp import client_exceptions
import asyncio
from datetime import datetime
import logging
import os

from discord.ext import commands
from discord import colour, embeds

from discord_bot import cfg
from discord_bot import utils

CONF = cfg.CONF
LOG = logging.getLogger('debug')

HEADERS = {
    "Client-ID": CONF.TWITCH_API_CLIENT_ID,
    "accept": CONF.TWITCH_API_ACCEPT
}


class Stream(object):

    def __init__(self, username, everyone=False):
        self.username = username
        self.id = None
        self.is_online = False
        self.everyone = everyone
        self.last_offline_date = None

    def __eq__(self, other):
        return self.username == other

    def __hash__(self):
        return hash(self.username)

    def __str__(self):
        return str(self.username)

    def update_last_offline_date(self):
        """ Update the last offline date """
        self.last_offline_date = datetime.now()

    def goes_offline(self):
        """ Check if the user has been offline for a long time """
        if not self.last_offline_date:
            return False
        else:
            now = datetime.now()
            offline_duration = now - self.last_offline_date
            return offline_duration.seconds > CONF.MIN_OFFLINE_DURATION


class StreamManager:

    def __init__(self, bot, filename=CONF.CONF_NAME + "_channels"):
        type(self).__name__ = "Stream commands"
        self.bot = bot
        self.streams = None
        self.filepath = utils.get_file_path("etc/" + filename + ".json")
        self._load()

    async def start(self, loop):
        """ Start the whole process

        :param loop: event loop
        """
        if self.streams:
            await asyncio.ensure_future(self._enrich_data(), loop=loop)
        await asyncio.ensure_future(self._poll_streams(), loop=loop)

    def _get_discord_channels_by_stream(self):
        """ Build a dictionary with the stream as key and a list of discord channel ids in which the stream is notified

        :return: a dictionary {<Stream> : ["discord_channel_id", "discord_channel_id"], <Stream> : ... }
        """
        channels_by_stream = {}
        for channel_id, channel_info in self.streams.items():
            for stream in channel_info['twitch_channels']:
                if stream not in channels_by_stream.keys():
                    channels_by_stream[stream] = []
                channels_by_stream[stream].append(channel_id)
        return channels_by_stream

    @staticmethod
    async def _get_ids(*usernames):
        """  Retrieve all user ids "
         
        :param usernames: usernames whose we want the id
        """""
        url = "{twitch_api_url}/users?login={usernames}".format(twitch_api_url=CONF.TWITCH_API_URL,
                                                                usernames=",".join(usernames))
        try:
            body = await utils.request(url, headers=HEADERS)
            users = body['users']
        except (KeyError, TypeError) as e:
            LOG.error("Cannot parse retrieved ids for {usernames} ({message})".format(usernames=usernames,
                                                                                      message=e.args))
        else:
            result = {user['name']: user['_id'] for user in users}
            LOG.debug("API data for {usernames}: {data} ({url})".format(usernames=usernames, data=result, url=url))
            return result

    @staticmethod
    async def _get_status(*twitch_ids):
        """  Retrieve all stream status

        :param twitch_ids: twitch ids whose we want the status
        """
        url = "{twitch_api_url}/streams/?channel={twitch_ids}".format(
            twitch_api_url=CONF.TWITCH_API_URL,
            twitch_ids=",".join([str(twitch_id) for twitch_id in twitch_ids])
        )
        body = await utils.request(url, headers=HEADERS)
        try:
            streams = body['streams']
        except (KeyError, TypeError) as e:
            LOG.error("Cannot retrieve stream data for {twitch_ids} ({message})".format(twitch_ids=twitch_ids,
                                                                                        message=e.args))
        else:
            return {stream['channel']['_id']: stream for stream in streams}

    @staticmethod
    def _get_notification(status, everyone=False):
        """ Send a message in discord chat to notify that a stream went online

        :param status: status object
        :param everyone: True if the stream is notified with @everyone, False otherwise
        """
        twitch_icon_url = "https://www.shareicon.net/download/2015/09/08/98061_twitch_512x512.png"
        clock_icon_url = "https://cdn2.iconfinder.com/data/icons/metro-uinvert-dock/256/Clock.png"

        display_name = status.get('channel').get('display_name')
        game = status.get('game')
        title = status.get('channel').get('status')
        logo_url = status.get('channel').get('logo')
        url = status.get('channel').get('url')

        message = ""
        message = message + "@everyone " if everyone else message

        message += "{display_name} is streaming!".format(display_name=display_name)

        embed = embeds.Embed()
        embed.colour = colour.Color.dark_blue()
        embed.description = "[{}]({})".format(url, url)

        embed.set_author(name=display_name, url=url, icon_url=twitch_icon_url)
        embed.add_field(name="Playing", value=game + (50 - len(game)) * " ** **", inline=False)
        embed.add_field(name="Stream Title", value=title, inline=False)
        embed.set_footer(text="Stream live time", icon_url=clock_icon_url)

        if logo_url:
            embed.set_thumbnail(url=logo_url)

        return message, embed

    def _load(self):
        """ Initialize the stream file

        - Create it if it does not exist
        - Delete then create it if it's in a bad format
        - Load the content if there is one
        """
        etc_dirpath = utils.get_file_path("etc")
        if not os.path.isdir(etc_dirpath):
            LOG.debug("Missing 'etc/' directory, creating one...")
            os.makedirs(etc_dirpath)
            LOG.debug("{etc_dirpath}' directory successfully created".format(etc_dirpath=etc_dirpath))

        if os.path.exists(self.filepath):
            LOG.debug("Loading {filepath} to see if an init is needed".format(filepath=self.filepath))
            self.streams = utils.load_json_file(self.filepath)

        if not os.path.exists(self.filepath) or self.streams is None:
            self.streams = {}
            utils.save_file(self.filepath, u"{}")
            LOG.debug("data file is not found or corrupted, recreating an empty one...")

        for channel_id in self.streams:
            self.streams[channel_id]['twitch_channels'] = [
                Stream(twitch_username, everyone)
                for (twitch_username, everyone) in self.streams[channel_id]['twitch_channels']
            ]

    async def _enrich_data(self):
        """ Set all stream ids """
        discord_channels_by_stream = self._get_discord_channels_by_stream()
        id_by_username = await self._get_ids(*[stream.username for stream in discord_channels_by_stream])
        for stream, discord_channels in self._get_discord_channels_by_stream().items():
            try:
                stream.id = int(id_by_username[stream.username])
            except KeyError:
                LOG.error("Unable to enrich data for {username}. This username doesn't exist anymore and might have "
                          "been changed".format(username=stream.username))
                for discord_channel in discord_channels:
                    self.streams[discord_channel]['twitch_channels'].remove(stream)
                    LOG.debug("{username} is no longer tracked in {discord_channel}"
                              .format(username=stream.username, discord_channel=discord_channel))
        LOG.debug("The data has successfully been enriched: {data}".format(data=id_by_username))

    async def _save(self):
        """ Save data in the file """
        output = {}
        for channel_id, channel_info in self.streams.items():
            output[channel_id] = {
                'channel_name': channel_info['channel_name'],
                'position': channel_info['position'],
                'guild_id': channel_info['guild_id'],
                'guild_name': channel_info['guild_name'],
                'twitch_channels': [(stream.username.lower(), stream.everyone)
                                    for stream in channel_info['twitch_channels']]
            }
        utils.save_json_file(self.filepath, output)

    async def _poll_streams(self):
        """ Poll twitch every X seconds """
        LOG.debug("The polling has started")
        while True:
            discord_channels_by_stream = self._get_discord_channels_by_stream()
            if discord_channels_by_stream:
                status = await self._get_status(*[stream.id for stream in discord_channels_by_stream if stream.id])
                if status is not None:
                    for stream, discord_channel_ids in discord_channels_by_stream.items():
                        if int(stream.id) in status:
                            stream.last_offline_date = None
                            if not stream.is_online:
                                message, embed = self._get_notification(status[int(stream.id)],
                                                                        everyone=stream.everyone)
                                for channel_id in discord_channel_ids:
                                    channel = self.bot.get_channel(int(channel_id))
                                    await channel.send(message, embed=embed)
                                    LOG.debug(
                                        "Sending notification for {username}'s stream in "
                                        "'{guild_name}:{channel_name}'" .format(username=stream.username,
                                                                                guild_name=channel.guild.name,
                                                                                channel_name=channel.name))
                                stream.is_online = True
                        else:
                            if stream.is_online:
                                if not stream.last_offline_date:
                                    stream.update_last_offline_date()
                                if stream.goes_offline():
                                    stream.is_online = False
                                    LOG.debug("{username} just went offline".format(username=stream.username))
                else:
                    LOG.warning("Cannot retrieve status for {usernames}, the polling iteration has been skipped."
                                .format(usernames=[stream.username for stream in discord_channels_by_stream]))
            await asyncio.sleep(10)

    # COMMANDS

    @commands.group(pass_context=True)
    async def stream(self, ctx):
        """ Manage tracked streams """
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), "stream")

    @stream.command()
    async def list(self, ctx):
        """ Show current tracked streams

        :param ctx: command context
        """
        message = "♦ Tracked channels ♦ \n\n"
        for channel_data in sorted(self.streams.values(), key=lambda x: x['position']):
            if channel_data['guild_id'] == ctx.message.channel.guild.id:
                twitch_channels = []
                for stream in channel_data['twitch_channels']:
                    channel = stream.username
                    if stream.everyone:
                        channel += "*"
                    twitch_channels.append(channel)
                message += "- {channel_name}: {twitch_channels}\n\n".format(
                    channel_name=channel_data['channel_name'],
                    twitch_channels=", ".join(sorted(twitch_channels))
                )
        await self.bot.say(ctx, message)

    async def _add_stream(self, discord_channel, username, everyone=False):
        """ Add a stream in a discord channel tracklist

        :param discord_channel: The discord channel in which the stream notifications are enabled
        :param username: The stream to notify
        :param everyone: If True, add the tag @everyone to the bot notification
        """
        channel_id = str(discord_channel.id)
        if not channel_id in self.streams:
            self.streams[channel_id] = {
                'channel_name': discord_channel.name,
                'position': discord_channel.position,
                'guild_name': discord_channel.guild.name,
                'guild_id': discord_channel.guild.id,
                'twitch_channels': []
            }

        if username in self.streams[channel_id]['twitch_channels']:
            LOG.debug("{twitch_username}'s stream is already tracked in '{server_name}:{channel_name}'".format(
                twitch_username=username,
                server_name=discord_channel.guild.name,
                channel_name=discord_channel.name
            ))

        else:
            stream = Stream(username, everyone)
            stream_ids = await self._get_ids(stream.username)
            stream.id = stream_ids[stream.username]
            self.streams[channel_id]['twitch_channels'].append(stream)
            LOG.debug("{twitch_username}'s stream is now tracked in '{server_name}:{channel_name}'".format(
                twitch_username=username,
                server_name=discord_channel.guild.name,
                channel_name=discord_channel.name
            ))
            await self._save()

    @stream.command()
    async def add(self, ctx, username):
        """ Add a stream to the tracked list

        :param ctx: command context
        :param username: The stream to notify
        """
        await self._add_stream(ctx.message.channel, username.lower())
        await self.bot.say(ctx, "{username} is now tracked in '{server_name}:{channel_name}'".format(
            username=username, server_name=ctx.message.channel.guild.name, channel_name=ctx.message.channel.name
        ))

    @stream.command()
    async def everyone(self, ctx, username):
        """ Add a stream to the tracked list (with @everyone)

        :param ctx: command context
        :param username: The stream to notify
        """
        await self._add_stream(ctx.message.channel, username.lower(), everyone=True)
        await self.bot.say(ctx, "{username} is now tracked in '{server_name}:{channel_name}'".format(
            username=username, server_name=ctx.message.channel.guild.name, channel_name=ctx.message.channel.name
        ))

    @stream.command()
    async def remove(self, ctx, username):
        """ Disable bot notification for a stream in a specific channel

        :param ctx: command context
        :param username: The stream to notify
        """
        discord_channel = ctx.message.channel
        channel_id = str(discord_channel.id)
        if channel_id in self.streams:
            if username in self.streams[channel_id]['twitch_channels']:
                self.streams[channel_id]['twitch_channels'].remove(username)
                LOG.debug("{twitch_username}'s stream is no longer tracked in '{server_name}:{channel_name}'".format(
                    twitch_username=username,
                    server_name=discord_channel.guild.name,
                    channel_name=discord_channel.name
                ))

            if not self.streams[channel_id]['twitch_channels']:
                del self.streams[channel_id]
                LOG.debug("There is no tracked stream in '{server_name}:{channel_name}' anymore".format(
                    server_name=discord_channel.guild.name,
                    channel_name=discord_channel.name
                ))
            await self._save()
        else:
            LOG.debug("There is no tracked stream in '{server_name}:{channel_name}'".format(
                server_name=discord_channel.guild.name,
                channel_name=discord_channel.name
            ))
        await self.bot.say(ctx, "{username} is no longer tracked in '{server_name}:{channel_name}'".format(
            username=username, server_name=discord_channel.guild.name, channel_name=discord_channel.name
        ))

    # EVENTS
    async def on_guild_channel_delete(self, channel):
        LOG.debug("The channel '{guild_name}:{channel_name}' has been deleted".format(guild_name=channel.guild.name,
                                                                                      channel_name=channel.name))
        try:
            del self.streams[channel.id]
            self._save()
            LOG.debug("Every tracked stream have been removed from the deleted channel '{guild_name:channel_name}'"
                      .format(guild_name=channel.guild.name, channel_name=channel.name))
        except KeyError:
            LOG.warning("channel '{guild_name}:{channel_name}' had no tracked channel"
                        .format(guild_name=channel.guild.name, channel_name=channel.name))


def setup(bot):
    stream_manager = StreamManager(bot)
    bot.add_cog(stream_manager)

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(stream_manager.start(loop), loop=loop)
