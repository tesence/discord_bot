import logging

from gumo.db import base

LOG = logging.getLogger(__name__)


class Dab(base.BaseModel):

    __tablename__ = "dabs"

    guild_id = base.Column('bigint', nullable=False)
    author_id = base.Column('bigint', nullable=False)
    author_name = base.Column('varchar(255)', nullable=False)
    target_id = base.Column('bigint', nullable=False)
    target_name = base.Column('varchar(255)', nullable=False)
    amount = base.Column('bigint', nullable=False)
    created_at = base.Column('timestamp', nullable=False, default="(now() at time zone 'utc')")
    rerolled_amount = base.Column('bigint')
    rerolled_at = base.Column('timestamp')

    def __init(self, **kwargs):
        self.guild_id = kwargs.pop('guild_id')
        self.author_id = kwargs.pop('author_id')
        self.author_name = kwargs.pop('author_name')
        self.target_id = kwargs.pop('target_id')
        self.target_name = kwargs.pop('target_name')
        self.amount = kwargs.pop('amount')
        self.created_at = kwargs.pop('created_at')
        self.rerolled_amount = kwargs.pop('rerolled_amount')
        self.rerolled_at = kwargs.pop('rerolled_at')


class DabDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, Dab)

    async def insert_dabs(self, guild_id, author, amount, created_at, *targets):

        columns = ['guild_id', 'author_id', 'author_name', 'target_id', 'target_name', 'amount', 'created_at']

        values = []
        for target in targets:
            values.append((guild_id, author.id, str(author), target.id, str(target), amount, created_at))

        joined_columns = ", ".join(columns)
        joined_markers = ", ".join(f'${index}' for index in range(1, len(columns) + 1))
        q = f"INSERT INTO {self.table_name} ({joined_columns}) VALUES ({joined_markers}) RETURNING *"
        await self.bot.pool.executemany(q, values)

    async def reroll_dabs(self, guild_id, author, new_amount, created_at, rerolled_at):
        q = f"UPDATE {self.table_name} SET rerolled_amount = $1, rerolled_at = $2 " \
            f"WHERE guild_id = $3 AND author_id = $4 AND created_at = $5"
        await self.bot.pool.execute(q, new_amount, rerolled_at,  guild_id, author.id, created_at)

    async def get_user_data(self, guild_id, author_id):
        return await self.bot.pool.fetch("SELECT created_at, author_id, target_id, amount, rerolled_amount "
                                         "FROM dabs WHERE guild_id = $1 AND (author_id = $2 OR target_id = $2)",
                                         guild_id, author_id)
