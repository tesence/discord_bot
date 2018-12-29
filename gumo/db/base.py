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
        self.ready = asyncio.Event(loop=bot.loop)
        self.bot.loop.create_task(self.init())

    async def init(self):
        self.bot.pool = self.bot.pool or await asyncpg.create_pool(**config.creds['DATABASE_CREDENTIALS'],
                                                                   min_size=1, max_size=5)
        await self._create_table()
        self.ready.set()
        size = await self.get_size()
        LOG.debug(f"Number of '{self.table_name}' found: {size}")

    async def _create_table(self):
        try:
            column_definitions = []
            for column_name, column in self.table_columns.items():
                column_definition = f"{column_name} {column.type}"
                if not column.nullable:
                    column_definition += " NOT NULL"
                if column.primary_key:
                    column_definition += " PRIMARY KEY"
                if column.default is not None:
                    column_definition += f" DEFAULT {column.default}"
                column_definitions.append(column_definition)
                if column.foreign_key:
                    foreign_key = f"FOREIGN KEY ({column_name}) REFERENCES {column.foreign_key.model_name}" \
                                  f"({column.foreign_key.column_name})"
                    column_definitions.append(foreign_key)

            for arg in self.table_args:
                if isinstance(arg, UniqueConstraint):
                    constraint = f"CONSTRAINT {'_'.join(arg.column_names)} UNIQUE ({','.join(arg.column_names)})"
                    column_definitions.append(constraint)

            query = f"CREATE TABLE IF NOT EXISTS {self.table_name} ({', '.join(column_definitions)});"
            await self.bot.pool.execute(query)
        except exceptions.PostgresError:
            LOG.exception(f"Cannot create table {self.table_name}")

    @staticmethod
    def _format_conditions(**conditions):
        parsed_conditions = []
        for key, value in conditions.items():
            if isinstance(value, str):
                parsed_conditions.append(f"{key} = '{value}'")
            elif value is None:
                parsed_conditions.append(f"{key} is NULL")
            else:
                parsed_conditions.append(f"{key} = {value}")
        return parsed_conditions

    def _get_obj(self, record):
        return self.model(**dict(record.items())) if record else None

    async def get_size(self):
        query = f"SELECT COUNT(*) FROM {self.table_name}"
        record = await self.bot.pool.fetchrow(query)
        return record['count']

    async def get(self, **conditions):
        query = f"SELECT * FROM {self.table_name}"
        conditions = self._format_conditions(**conditions)
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        record = await self.bot.pool.fetchrow(query)
        return self._get_obj(record)

    async def exists(self, **conditions):
        conditions = self._format_conditions(**conditions)
        subquery = f"SELECT 1 FROM {self.table_name} "
        if conditions:
            subquery += f"WHERE {' AND '.join(conditions)}"
        query = f"SELECT EXISTS({subquery})"
        record = await self.bot.pool.fetchrow(query)
        return record['exists']

    async def list(self, **conditions):
        query = f"SELECT * FROM {self.table_name}"
        conditions = self._format_conditions(**conditions)
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        records = await self.bot.pool.fetch(query)
        return [self._get_obj(r) for r in records]

    async def create(self, **fields):
        columns = ",".join(fields)
        values = []
        for value in fields.values():
            if isinstance(value, str) or isinstance(value, int):
                values.append(f"'{value}'")
            elif value is not None:
                values.append(value)
            else:
                values.append("NULL")

        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({', '.join(values)}) RETURNING *"
        record = await self.bot.pool.fetchrow(query)
        return self._get_obj(record)

    async def delete(self, **conditions):
        query = f"DELETE FROM {self.table_name}"
        conditions = self._format_conditions(**conditions)
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        await self.bot.pool.execute(query)

    async def update(self, column, value, **conditions):
        conditions = self._format_conditions(**conditions)
        query = f"UPDATE {self.table_name} SET {column} = '{value}' WHERE {' AND '.join(conditions)} RETURNING *"
        record = await self.bot.pool.fetchrow(query)
        return self._get_obj(record)
