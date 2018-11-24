import collections
from datetime import datetime

import discord

from gumo import config

TWITCH_ICON_URL = "https://www.shareicon.net/download/2015/09/08/98061_twitch_512x512.png"


class StreamCache:

    def __init__(self):
        self._s = {}
        self._c = {}
        self._cs_by_c = collections.defaultdict(set)
        self._cs_by_s = collections.defaultdict(set)

    @property
    def streams(self):
        return list(self._s.values())

    @property
    def channel_streams(self):
        return list(self._cs_by_c.values())

    def add_streams(self, *streams):
        for stream in streams:
            self._s[stream.id] = stream

    def get_stream(self, stream_id):
        return self._s.get(stream_id)

    def delete_stream(self, stream_id):
        return self._s.pop(stream_id, None)

    def add_channels(self, *channels):
        for channel in channels:
            self._c[channel.id] = channel

    def get_channel(self, channel_id):
        return self._c.get(channel_id)

    def delete_channel(self, channel_id):
        return self._c.pop(channel_id, None)

    def add_channel_streams(self, *channel_streams):
        for channel_stream in channel_streams:
            self._cs_by_c[channel_stream.channel_id].add(channel_stream)
            self._cs_by_s[channel_stream.stream_id].add(channel_stream)

    def get_channel_stream(self, stream_id, channel_id):
        assert stream_id and channel_id
        return next(iter(self._cs_by_s[stream_id] & self._cs_by_c[channel_id]), None)

    def get_channel_streams(self, stream_id=None, channel_id=None):
        assert not (stream_id and channel_id)
        return list(self._cs_by_s[stream_id] | self._cs_by_c[channel_id])

    def update_channel_stream(self, new_channel_stream):
        stream_id = new_channel_stream.stream_id
        channel_id = new_channel_stream.channel_id
        channel_stream = self.get_channel_stream(stream_id, channel_id)
        if channel_stream:
            self.delete_channel_streams(stream_id, channel_id)
            self.add_channel_streams(new_channel_stream)

    def delete_channel_streams(self, stream_id=None, channel_id=None):
        assert stream_id or channel_id

        if stream_id and not channel_id:
            channel_streams  = self._cs_by_s.pop(stream_id, set())
            for cs in channel_streams:
                self._cs_by_c[cs.channel_id].discard(cs)

        if not stream_id and channel_id:
            channel_streams = self._cs_by_c.pop(channel_id, set())
            for cs in channel_streams:
                self._cs_by_s[cs.stream_id].discard(cs)

        if stream_id and channel_id:
            channel_stream = self.get_channel_stream(stream_id, channel_id)
            if channel_stream:
                self._cs_by_c[channel_stream.channel_id].discard(channel_stream)
                self._cs_by_s[channel_stream.stream_id].discard(channel_stream)


class NotificationHandler:

    DEFAULT_RECENT_NOTIFICATION_AGE = 300
    DEFAULT_OLD_NOTIFICATION_LIFESPAN = 60 * 60 * 24

    @staticmethod
    def _get_message(stream, tags=None):
        if stream.type == "live":
            message = f"{stream.display_name} is live!"
        else:
            message = f"{stream.display_name} started a vodcast!"
        if tags:
            message = f"{tags} {message}"
        return message

    @staticmethod
    def extract_info(message):
        return message.content, message.embeds[0]

    @classmethod
    def _get_offline_duration(cls, message):
        if cls.is_online(message):
            return -1
        return (datetime.utcnow() - message.edited_at).total_seconds()

    @classmethod
    def is_online(cls, message):
        message, embed = cls.extract_info(message)
        return bool(message) and embed.color == NotificationEmbed.ONLINE_COLOR

    @classmethod
    def get_info(cls, stream, tags=None):
        message = cls._get_message(stream, tags) if stream.online else ""
        embed = NotificationEmbed(stream)

        return message, embed

    @classmethod
    def is_recent(cls, message):
        if cls.is_online(message):
            return False
        recent_notification_age = config.get('RECENT_NOTIFICATION_AGE', cls.DEFAULT_RECENT_NOTIFICATION_AGE,
                                             guild_id=message.guild.id)
        return cls._get_offline_duration(message) < recent_notification_age

    @classmethod
    def is_deprecated(cls, message):
        if cls.is_online(message):
            return False
        old_notification_lifespan = config.get('OLD_NOTIFICATION_LIFESPAN', cls.DEFAULT_OLD_NOTIFICATION_LIFESPAN,
                                               guild_id=message.guild.id)
        return cls._get_offline_duration(message) > old_notification_lifespan


class NotificationEmbed(discord.Embed):

    ONLINE_COLOR = discord.Color.dark_purple()
    VODCAST_COLOR = discord.Color.red()
    OFFLINE_COLOR = discord.Color.lighter_grey()

    def __init__(self, stream):
        super(NotificationEmbed, self).__init__()
        self.stream = stream

        channel_url = f"https://www.twitch.tv/{stream.name}"
        self.set_author(name=stream.display_name, url=channel_url, icon_url=TWITCH_ICON_URL)
        self.description = channel_url

        self.add_field(name="Title", value=stream.title, inline=False)
        self.add_field(name="Game", value=stream.game, inline=False)

        if stream.logo:
            self.set_thumbnail(url=stream.logo)

        if stream.online:
            self.color = self.ONLINE_COLOR if self.stream.type == "live" else self.VODCAST_COLOR
        else:
            self.color = self.OFFLINE_COLOR


class StreamListEmbed(discord.Embed):
    """Build the embed to return on !stream list call"""
    def __init__(self, streams_by_channel):
        super(StreamListEmbed, self).__init__()

        self.set_author(name="Streams", icon_url=TWITCH_ICON_URL)
        for channel, streams in sorted(streams_by_channel.items(), key=lambda x: x[0].position):
            self.add_field(name=channel.name, value=", ".join(sorted(streams)).replace('_', '\_'), inline=False)

