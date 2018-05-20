from datetime import datetime
import logging

from asyncpg import exceptions as db_exc
from gino import Gino

from discord_bot import cfg
from discord_bot import log


CONF = cfg.CONF

LOG = logging.getLogger('debug')

db = Gino()


class BaseModel:

    def __repr__(self):
        attrs = [k + "=" + str(v) for k, v in self.to_dict().items()]
        return "<{class_name} {attrs}>".format(class_name=self.__class__.__name__, attrs=" ".join(attrs))


class Channel(BaseModel, db.Model):

    __tablename__ = 'channels'

    id = db.Column(db.BigInteger(), primary_key=True)
    name = db.Column(db.Unicode(), nullable=False)
    guild_id = db.Column(db.BigInteger(), nullable=False)
    guild_name = db.Column(db.Unicode(), nullable=False)


class Stream(BaseModel, db.Model):

    __tablename__ = 'streams'

    id = db.Column(db.BigInteger(), primary_key=True)
    name = db.Column(db.Unicode(), nullable=False)

    @property
    def offline_duration(self):
        now = datetime.now()
        if not self.last_offline_date:
            self.last_offline_date = now
        return (now - self.last_offline_date).seconds

    def __init__(self, **kwargs):
        super(Stream, self).__init__(**kwargs)
        self.is_online = False
        self.last_offline_date = None


class ChannelStream(BaseModel, db.Model):

    __tablename__ = "channels_streams"
    __table_args__ = (db.UniqueConstraint("stream_id", "channel_id"),)

    channel_id = db.Column(db.BigInteger(), db.ForeignKey('channels.id'), primary_key=True)
    stream_id = db.Column(db.BigInteger(), db.ForeignKey('streams.id'), primary_key=True)
    everyone = db.Column(db.Boolean(), default=False)


class DBDriver:

    def __init__(self):
        self.engine = None

    async def setup(self):
        bind = "postgresql://{user}:{password}@{host}:{port}/{database}"\
               .format(user=CONF.DB_USER, password=CONF.DB_PASSWORD, host=CONF.DB_HOST,
                       port=CONF.DB_PORT, database=CONF.DB_NAME)
        await db.set_bind(bind)
        await db.gino.create_all()

    async def _create(self, model, **kwargs):
        try:
            return await model.create(**kwargs)
        except (KeyError, db_exc.UniqueViolationError) as e:
            message = "Cannot create {class_name}".format(class_name=model.__name__)
            LOG.error(log.get_log_exception_message(message, e))

    # CREATE

    async def create_channel(self, id, name, guild_id, guild_name):
        params = {'id': id, 'name': name, 'guild_id': guild_id, 'guild_name': guild_name}
        return await self._create(Channel, **params)

    async def create_stream(self, id, name):
        params = {'id': id, 'name': name}
        return await self._create(Stream, **params)

    async def create_channel_stream(self, channel_id, stream_id, everyone=False):
        params = {'channel_id': channel_id, 'stream_id': stream_id, 'everyone': everyone}
        return await self._create(ChannelStream, **params)

    # READ

    async def get_channel(self, id=None, name=None, guild_id=None, guild_name=None):
        query = Channel.query
        if id:
            query = query.where(Channel.id == id)
        if name:
            query = query.where(Channel.name == name)
        if guild_id:
            query = query.where(Channel.guild_id == guild_id)
        if guild_name:
            query = query.where(Channel.guild_name == guild_name)
        return await query.gino.all()

    async def get_stream(self, id=None, name=None):
        query = Stream.query
        if id:
            query = query.where(Stream.id == id)
        if name:
            query = query.where(Stream.name == name)
        return await query.gino.all()

    async def get_channel_stream(self, channel_id=None, stream_id=None):
        channel_streams = await ChannelStream.query.gino.all()
        if channel_id:
            channel_streams = [cs for cs in channel_streams if cs.channel_id == channel_id]
        if stream_id:
            channel_streams = [cs for cs in channel_streams if cs.stream_id == stream_id]
        return channel_streams
