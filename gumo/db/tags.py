import logging

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

    async def increment_usage(self, code, guild_id=None):
        query = f"UPDATE {self.table_name} SET usage = usage + 1 " \
            f"WHERE code = '{code}' and guild_id = {guild_id} RETURNING *"
        result = await self.bot.pool.fetchrow(query)
        if result:
            result = self._get_obj(result)
        return result
