import logging

from gumo.db import base


LOG = logging.getLogger(__name__)


class Channel(base.BaseModel):

    __tablename__ = "channels"

    id = base.Column('bigint', primary_key=True)
    name = base.Column('varchar(255)', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    guild_name = base.Column('varchar(255)', nullable=False)


class User(base.BaseModel):

    __tablename__ = "users"

    id = base.Column('varchar(255)', primary_key=True)
    login = base.Column('varchar(255)', nullable=False)


class UserChannel(base.BaseModel):

    __tablename__ = "user_channels"
    __table_args__ = base.UniqueConstraint("user_id", "channel_id"),

    channel_id = base.Column('bigint', base.ForeignKey("channels", "id"), nullable=False)
    user_id = base.Column('varchar(255)', base.ForeignKey("users", "id"), nullable=False)
    tags = base.Column('varchar(255)')


class Stream(base.BaseModel):

    __tablename__ = "streams"
    __table_args__ = base.UniqueConstraint("id", "started_at"),

    id = base.Column('varchar(255)', nullable=False)
    type = base.Column('varchar(255)', nullable=False)  # 'live' or 'vodcast'
    user_id = base.Column('varchar(255)', nullable=False)
    game_id = base.Column('varchar(255)')
    started_at = base.Column('timestamp')
    ended_at = base.Column('timestamp')


class Notification(base.BaseModel):

    __tablename__ = "notifications"
    __table_args__ = base.UniqueConstraint("stream_id", "message_id"),

    message_id = base.Column('bigint', primary_key=True)
    user_id = base.Column('varchar(255)', nullable=False)
    channel_id = base.Column('bigint', nullable=False)
    stream_id = base.Column('varchar(255)', nullable=False)
    created_at = base.Column('timestamp', nullable=False)
    edited_at = base.Column('timestamp')
    deleted_at = base.Column('timestamp')


class ChannelDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, Channel)

    async def delete_old_channels(self):
        query = f"DELETE FROM {self.table_name} WHERE id NOT IN (SELECT channel_id FROM {UserChannel.__tablename__})"
        query += " RETURNING *"
        records = await self.bot.pool.fetch(query)
        return [self._get_obj(r) for r in records]


class UserDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, User)

    async def delete_old_users(self):
        query = f"DELETE FROM {self.table_name} WHERE id NOT IN (SELECT user_id FROM {UserChannel.__tablename__})"
        query += " RETURNING *"
        records = await self.bot.pool.fetch(query)
        return [self._get_obj(r) for r in records]


class UserChannelDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, UserChannel)

    async def bulk_delete(self, channel_id, *user_ids):
        query = f"DELETE FROM {self.table_name} WHERE channel_id = $1 AND "
        query += f"({' OR '.join([f'user_id = ${index}' for index in range(2, len(user_ids) + 2)])})"
        query += " RETURNING *"
        records = await self.bot.pool.fetch(query, channel_id, *user_ids)
        return [self._get_obj(r) for r in records]


class StreamDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, Stream)


class NotificationDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, Notification)
