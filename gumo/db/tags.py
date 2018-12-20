import logging

from asyncpg import exceptions

from gumo.db import base

LOG = logging.getLogger('bot')


class Tags(base.BaseModel):

    __tablename__ = "tags"
    __table_args__ = base.UniqueConstraint('code', 'guild_id'),

    code = base.Column('citext', nullable=False)
    content = base.Column('text', nullable=False)
    author_id = base.Column('bigint', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    created_at = base.Column('varchar(255)', nullable=False)
    usage = base.Column('bigint', nullable=False, default=0)

    def __init__(self, **kwargs):
        self.code = kwargs.pop('code')
        self.content = kwargs.pop('content')
        self.author_id = kwargs.pop('author_id')
        self.guild_id = kwargs.pop('guild_id')
        self.created_at = kwargs.pop('created_at')
        self.usage = kwargs.pop('usage')


class TagDBDriver(base.DBDriver):

    def __init__(self, bot):
        super(TagDBDriver, self).__init__(bot, Tags)

    async def increment_usage(self, code):
        try:
            await self.bot.pool.execute(f"UPDATE {self.table_name} SET usage = usage + 1 WHERE code = '{code}'")
        except exceptions.PostgresError:
            LOG.exception(f"Cannot update usage for tag {code}")
