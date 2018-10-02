from datetime import datetime
import logging

from asyncpg import exceptions

from discord_bot.db import base
from discord_bot.db.base import transaction


LOG = logging.getLogger('bot')


class Channel(base.BaseModel):

    __tablename__ = "channels"

    id = base.Column('bigint', primary_key=True)
    name = base.Column('varchar(255)', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    guild_name = base.Column('varchar(255)', nullable=False)

    def __repr__(self):
        return f"<{type(self).__name__} name={self.name} guild_name={self.guild_name}>"


class Stream(base.BaseModel):

    __tablename__ = "streams"

    id = base.Column('bigint', primary_key=True)
    name = base.Column('varchar(255)', nullable=False)

    def __repr__(self):
        return f"<{type(self).__name__} name={self.name}>"

    @property
    def offline_duration(self):
        now = datetime.now()
        if not self.last_offline_date:
            self.last_offline_date = now
        return (now - self.last_offline_date).seconds

    def __init__(self, **kwargs):
        super(Stream, self).__init__(**kwargs)
        self.online = False
        self.last_offline_date = None
        self.notifications = []
        self.display_name = None
        self.title = None
        self.game = None
        self.logo = None
        self.type = None


class ChannelStream(base.BaseModel):

    __tablename__ = "channel_streams"
    __table_args__ = base.UniqueConstraint("stream_id", "channel_id"),

    channel_id = base.Column('bigint', base.ForeignKey("channels", "id"))
    stream_id = base.Column('bigint', base.ForeignKey("streams", "id"))
    tags = base.Column('varchar(255)', nullable=True)

    def __repr__(self):
        return f"<{type(self).__name__} stream_id={self.stream_id} channel_id={self.channel_id}>"


class ChannelDBDriver(base.DBDriver):

    def __init__(self, pool, loop):
        super(ChannelDBDriver, self).__init__(pool, loop, Channel)


class StreamDBDriver(base.DBDriver):

    def __init__(self, pool, loop):
        super(StreamDBDriver, self).__init__(pool, loop, Stream)

    @transaction()
    async def delete_deprecated_streams(self):
        try:
            deprecated_streams = await self.join(join_type="LEFT", joined_table_name=ChannelStream.__tablename__,
                                                 column_name="id", joined_column_name="stream_id", intersection=False)
            for deprecated_stream in deprecated_streams:
                await self.delete(id=deprecated_stream.id)
        except exceptions.PostgresError:
            LOG.exception("Cannot delete deprecated streams")


class ChannelStreamDBDriver(base.DBDriver):

    def __init__(self, pool, loop):
        super(ChannelStreamDBDriver, self).__init__(pool, loop, ChannelStream)
