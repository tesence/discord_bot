import logging

from asyncpg import exceptions

from gumo.db import base

LOG = logging.getLogger('bot')


class Tags(base.BaseModel):

    __tablename__ = "tags"

    code = base.Column('varchar(255)', primary_key=True)
    content = base.Column('text', nullable=False)
    author_id = base.Column('bigint', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    created_at = base.Column('varchar(255)', nullable=False)
    usage = base.Column('bigint', nullable=False)

    def __init__(self, **kwargs):
        self.code = kwargs.pop('code')
        self.content = kwargs.pop('content')
        self.author_id = kwargs.pop('author_id')
        self.guild_id = kwargs.pop('guild_id')
        self.created_at = kwargs.pop('created_at')
        self.usage = kwargs.pop('usage')


class TagDBDriver(base.DBDriver):

    def __init__(self, pool, loop):
        super(TagDBDriver, self).__init__(pool, loop, Tags)

    async def create(self, **fields):
        return await super(TagDBDriver, self).create(usage=0, **fields)

    async def increment_usage(self, code):
        try:
            await self.bot.pool.execute(f"UPDATE {self.table_name} SET usage = usage + 1 WHERE code = '{code}'")
        except exceptions.PostgresError:
            LOG.exception(f"Cannot update usage for tag {code}")
