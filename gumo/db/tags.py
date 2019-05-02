import logging

from gumo.db import base

LOG = logging.getLogger(__name__)


class Tag(base.BaseModel):

    __tablename__ = "tags"
    __table_args__ = base.UniqueConstraint('code', 'guild_id'),

    code = base.Column('citext', nullable=False)
    content = base.Column('text', nullable=False)
    author_id = base.Column('bigint', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    created_at = base.Column('timestamp', nullable=False, default="(now() at time zone 'utc')")
    usage = base.Column('bigint', nullable=False, default=0)


class TagDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, Tag)

    async def increment_usage(self, code, guild_id=None):
        query = f"UPDATE {self.table_name} SET usage = usage + 1 " \
            f"WHERE code = '{code}' and guild_id = {guild_id} RETURNING *"
        result = await self.bot.pool.fetchrow(query)
        if result:
            result = self._get_obj(result)
        return result
