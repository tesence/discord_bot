import asyncio
import logging

import asyncpg
from asyncpg import exceptions

from gumo import config


LOG = logging.getLogger('bot')


class Column:

    def __init__(self, column_type, foreign_key=None, primary_key=False, nullable=True, default=None):
        self.type = column_type
        self.foreign_key = foreign_key
        self.primary_key = primary_key
        self.nullable = nullable
        self.default = default


class ForeignKey:

    def __init__(self, model_name, column_name):
        self.model_name = model_name
        self.column_name = column_name


class UniqueConstraint:

    def __init__(self, *column_names):
        self.column_names = column_names


class BaseModel:
    __tablename__ = None
    __table_args__ = ()


class DBDriver:

    def __init__(self, bot, model):
        self.bot = bot
        self.model = model
        self.table_name = self.model.__tablename__
        self.table_args = self.model.__table_args__
        self.table_columns = {attr: value for attr, value in vars(self.model).items() if isinstance(value, Column)}

    async def init(self):
        self.bot.pool = self.bot.pool or await asyncpg.create_pool(**config.glob['DATABASE_CREDENTIALS'],
                                                                   min_size=1, max_size=5)
        await self._create_table()
        size = await self.count()
        LOG.debug(f"Number of '{self.table_name}' found: {size}")

    async def _create_table(self):
        try:
            column_definitions = []
            for column_name, column in self.table_columns.items():
                column_definition = f"{column_name} {column.type}"
                column_definition += (not column.nullable) * " NOT NULL"
                column_definition += column.primary_key * " PRIMARY KEY"
                column_definition += (column.default is not None) * f" DEFAULT {column.default}"
                column_definitions.append(column_definition)
                if column.foreign_key:
                    foreign_key = f"FOREIGN KEY ({column_name}) REFERENCES {column.foreign_key.model_name}" \
                        f"({column.foreign_key.column_name})"
                    column_definitions.append(foreign_key)

            for arg in self.table_args:
                if isinstance(arg, UniqueConstraint):
                    constraint = f"CONSTRAINT {'_'.join(arg.column_names)} UNIQUE ({', '.join(arg.column_names)})"
                    column_definitions.append(constraint)

            query = f"CREATE TABLE IF NOT EXISTS {self.table_name} ({', '.join(column_definitions)});"
            await self.bot.pool.execute(query)
        except exceptions.PostgresError:
            LOG.exception(f"Cannot create table {self.table_name}")

    def _get_obj(self, record):
        return self.model(**dict(record.items())) if record else None

    async def count(self):
        q = f"SELECT COUNT(*) FROM {self.table_name}"
        record = await self.bot.pool.fetchrow(q)
        return record['count']

    async def exists(self, **filters):
        subq = f"SELECT 1 FROM {self.table_name} "
        subq += bool(filters) * f" WHERE {', '.join(f'{column} = ${index}' for index, column in enumerate(filters, 1))}"
        q = f"SELECT EXISTS({subq})"
        record = await self.bot.pool.fetchrow(q, *filters.values())
        return record['exists']

    async def get(self, **filters):
        q = f"SELECT * FROM {self.table_name}"
        q += bool(filters) * f" WHERE {', '.join(f'{column} = ${index}' for index, column in enumerate(filters, 1))}"
        record = await self.bot.pool.fetchrow(q, *filters.values())
        return self._get_obj(record)

    async def list(self, **filters):
        q = f"SELECT * FROM {self.table_name}"
        q += bool(filters) * f" WHERE {', '.join(f'{column} = ${index}' for index, column in enumerate(filters, 1))}"
        records = await self.bot.pool.fetch(q, *filters.values())
        return [self._get_obj(r) for r in records]

    async def create(self, **fields):
        fields = {column: value for column, value in fields.items() if value is not None}
        joined_columns = ", ".join(fields)
        joined_markers = ", ".join(f'${index}' for index in range(1, len(fields) + 1))
        q = f"INSERT INTO {self.table_name} ({joined_columns}) VALUES ({joined_markers}) RETURNING *"
        record = await self.bot.pool.fetchrow(q, *fields.values())
        return self._get_obj(record)

    async def delete(self, **filters):
        if not filters:
            raise RuntimeError("Cannot delete using empty filters")
        q = f"DELETE FROM {self.table_name}"
        q += bool(filters) * f" WHERE {', '.join(f'{column} = ${index}' for index, column in enumerate(filters, 1))}"
        await self.bot.pool.execute(q, *filters.values())

    async def update(self, column, value, **filters):
        if not filters:
            raise RuntimeError("Cannot update using empty filters")
        q = f"UPDATE {self.table_name} SET {column} = '{value}'  RETURNING *"
        q += bool(filters) * f" WHERE {', '.join(f'{column} = ${index}' for index, column in enumerate(filters, 1))}"
        record = await self.bot.pool.fetchrow(q, *filters.values())
        return self._get_obj(record)
