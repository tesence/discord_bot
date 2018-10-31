from datetime import datetime
import logging

from discord_bot.db import base


LOG = logging.getLogger('bot')


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
        self.notifications = []
        self.display_name = None
        self.title = None
        self.game = None
        self.logo = None
        self.type = None

    def __repr__(self):
        return f"<{type(self).__name__} name={self.name}>"

    @property
    def offline_duration(self):
        now = datetime.now()
        if not self.last_offline_date:
            self.last_offline_date = now
        return (now - self.last_offline_date).seconds


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

    def __init__(self, pool, loop):
        super(ChannelDBDriver, self).__init__(pool, loop, Channel)


class StreamDBDriver(base.DBDriver):

    def __init__(self, pool, loop):
        super(StreamDBDriver, self).__init__(pool, loop, Stream)


class ChannelStreamDBDriver(base.DBDriver):

    def __init__(self, pool, loop):
        super(ChannelStreamDBDriver, self).__init__(pool, loop, ChannelStream)

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
        return await self.pool.fetch(query)
