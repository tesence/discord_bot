import collections
from datetime import datetime
import logging

from gumo.db import base
from gumo.cogs.stream.models import NotificationHandler


LOG = logging.getLogger('bot')

DEFAULT_RECENT_NOTIFICATION_AGE = 300


class Channel(base.BaseModel):

    __tablename__ = "channels"

    id = base.Column('bigint', primary_key=True)
    name = base.Column('varchar(255)', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    guild_name = base.Column('varchar(255)', nullable=False)

    def __init__(self, **kwargs):
        self.id = kwargs.pop('id')
        self.name = kwargs.pop('name')
        self.guild_id = kwargs.pop('guild_id')
        self.guild_name = kwargs.pop('guild_name')

    def __repr__(self):
        return f"<{type(self).__name__} name={self.name} guild_name={self.guild_name}>"


class Stream(base.BaseModel):

    __tablename__ = "streams"

    id = base.Column('varchar(255)', primary_key=True)
    name = base.Column('varchar(255)', nullable=False)

    def __init__(self, **kwargs):
        self.id = kwargs.pop('id')
        self.name = kwargs.pop('name')
        self.online = False
        self.last_offline_date = None
        self.notifications_by_channel_id = collections.defaultdict(list)
        self.display_name = None
        self.title = None
        self.game = None
        self.logo = None
        self.type = None

    def __repr__(self):
        return f"<{type(self).__name__} name={self.name}>"

    @property
    def notifications(self):
        notifications = []
        for channel_notifications in self.notifications_by_channel_id.values():
            notifications += list(channel_notifications)
        return notifications

    @property
    def offline_duration(self):
        if not self.last_offline_date:
            return -1
        return (datetime.utcnow() - self.last_offline_date).total_seconds()

    def get_recent_notification(self, channel_id):
        return next((notification for notification in self.notifications_by_channel_id[channel_id]
                     if NotificationHandler.is_recent(notification)), None)


class ChannelStream(base.BaseModel):

    __tablename__ = "channel_streams"
    __table_args__ = base.UniqueConstraint("stream_id", "channel_id"),

    channel_id = base.Column('bigint', base.ForeignKey("channels", "id"))
    stream_id = base.Column('bigint', base.ForeignKey("streams", "id"))
    tags = base.Column('varchar(255)', nullable=True)

    def __init__(self, **kwargs):
        self.channel_id = kwargs.pop('channel_id')
        self.stream_id = kwargs.pop('stream_id')
        self.tags = kwargs.pop('tags')

    def __repr__(self):
        return f"<{type(self).__name__} stream_id={self.stream_id} channel_id={self.channel_id}>"


class ChannelDBDriver(base.DBDriver):

    def __init__(self, bot):
        super(ChannelDBDriver, self).__init__(bot, Channel)


class StreamDBDriver(base.DBDriver):

    def __init__(self, bot):
        super(StreamDBDriver, self).__init__(bot, Stream)


class ChannelStreamDBDriver(base.DBDriver):

    def __init__(self, bot):
        super(ChannelStreamDBDriver, self).__init__(bot, ChannelStream)

    async def get_stream_list(self, guild_id, guild_only=True):
        c_table = Channel.__tablename__
        s_table = Stream.__tablename__
        cs_table = ChannelStream.__tablename__

        query = \
            f"SELECT {c_table}.channel_id, {s_table}.stream_name FROM {cs_table} " \
            f"JOIN (SELECT id as channel_id, name as channel_name, guild_id FROM {c_table}) {c_table} " \
            f"ON {cs_table}.channel_id = {c_table}.channel_id " \
            f"JOIN (SELECT id, name as stream_name FROM {s_table}) {s_table} " \
            f"ON {cs_table}.stream_id = {s_table}.id "
        if guild_only:
            query += f"WHERE {c_table}.guild_id = {guild_id}"
        return await self.bot.pool.fetch(query)
