import asyncio
import functools
import logging

import asyncpg
from asyncpg import exceptions

from discord_bot import cfg


CONF = cfg.CONF
LOG = logging.getLogger('bot')


class Column:

    def __init__(self, type, foreign_key=None, primary_key=False, nullable=True, default=None):
        self.type = type
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
    __table_args__ = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def transaction():
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            await args[0].ready.wait()
            connection = await args[0].pool.acquire()
            async with connection.transaction():
                result = await func(*args, **kwargs)
            await args[0].pool.release(connection)
            return result
        return wrapped
    return wrapper


class DBDriver:

    def __init__(self, loop, model):
        self.model = model
        self.loop = loop
        self.ready = asyncio.Event(loop=loop)
        self.pool = None
        asyncio.ensure_future(self.configure(), loop=loop)

    @property
    def table_name(self):
        return self.table_info['name']

    async def configure(self):
        self.pool = await asyncpg.create_pool(**CONF.DATABASE_CREDENTIALS)
        self._get_table_info()
        await self._create_table_if_not_exist()
        self.ready.set()

    def _get_table_info(self):
        self.table_info = {
            "name": vars(self.model).get('__tablename__'),
            "args": vars(self.model).get('__table_args__'),
            "columns": {attr: value for attr, value in vars(self.model).items() if isinstance(value, Column)}
        }

    async def _create_table_if_not_exist(self):
        try:
            column_definitions = []
            for column_name, column in self.table_info['columns'].items():
                column_definition = f"{column_name} {column.type}"
                if not column.nullable:
                    column_definition += " NOT NULL"
                if column.primary_key:
                    column_definition += " PRIMARY KEY"
                column_definitions.append(column_definition)
                if column.foreign_key:
                    foreign_key = f"FOREIGN KEY ({column_name}) REFERENCES {column.foreign_key.model_name}" \
                                  f"({column.foreign_key.column_name})"
                    column_definitions.append(foreign_key)

            if self.table_info['args']:
                for arg in self.table_info['args']:
                    if isinstance(arg, UniqueConstraint):
                        constraint = f"CONSTRAINT {'_'.join(arg.column_names)} UNIQUE ({','.join(arg.column_names)})"
                        column_definitions.append(constraint)

            query = f"CREATE TABLE IF NOT EXISTS {self.table_info['name']}" \
                    f"({', '.join(column_definitions)});"

            await self.pool.execute(query)
        except exceptions.PostgresError:
            LOG.exception(f"Cannot create table {self.table_name}")

    @staticmethod
    def _format_conditions(**conditions):
        parsed_conditions = []
        for key, value in conditions.items():
            if isinstance(value, str):
                value = f"'{value}'"
            elif value is None:
                value = "NULL"
            parsed_conditions.append(f"{key} = {value}")
        return parsed_conditions

    @transaction()
    async def get(self, **conditions):
        try:
            query = f"SELECT * FROM {self.table_name}"
            conditions = self._format_conditions(**conditions)
            if conditions:
                query += f" WHERE {' AND '.join(conditions)}"
            query += ";"
            result = await self.pool.fetchrow(query)
            if result:
                result = self.model(**dict(result.items()))
        except exceptions.PostgresError:
            LOG.error(f"Cannot retrieve data for values: {conditions} ('{query}')")
        else:
            return result

    @transaction()
    async def list(self, **conditions):
        try:
            query = f"SELECT * FROM {self.table_name}"
            conditions = self._format_conditions(**conditions)
            if conditions:
                query += f" WHERE {' AND '.join(conditions)}"
            query += ";"
            result = [self.model(**dict(e.items())) for e in await self.pool.fetch(query)]
        except exceptions.PostgresError:
            LOG.error(f"Cannot retrieve data for values: {conditions} ('{query}')")
        else:
            return result

    @transaction()
    async def create(self, **fields):
        try:
            columns = ",".join(list(fields.keys()))

            values = []
            for value in fields.values():
                if isinstance(value, str) or isinstance(value, int):
                    values.append(f"'{value}'")
                elif value is not None:
                    values.append(value)
                else:
                    values.append("NULL")

            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({', '.join(values)})"
            await self.pool.execute(query)
            result = await self.get(**fields)
        except exceptions.PostgresError:
            LOG.exception(f"Cannot create data for values: {fields} ('{query}')")
        else:
            return result

    @transaction()
    async def delete(self, **conditions):
        try:
            query = f"DELETE FROM {self.table_name}"
            conditions = self._format_conditions(**conditions)
            if conditions:
                query += f" WHERE {' AND '.join(conditions)}"
            query += ";"
            await self.pool.execute(query)
        except exceptions.PostgresError:
            LOG.exception(f"Cannot delete data for conditions: {conditions} ('{query}')")

    @transaction()
    async def update(self, column, value, **conditions):
        try:
            conditions = self._format_conditions(**conditions)
            query = f"UPDATE {self.table_name} SET {column} = '{value}' WHERE {' AND '.join(conditions)}"
            await self.pool.execute(query)
        except exceptions.PostgresError:
            LOG.exception(f"Cannot update data with values {column}:{value} for conditions {conditions} ('{query}')")

    @transaction()
    async def join(self, join_type, joined_table_name, column_name, joined_column_name, intersection=True):
        try:
            query = f"SELECT * FROM {self.table_name} " \
                    f"{join_type} JOIN {joined_table_name} " \
                    f"ON {self.table_name}.{column_name} = {joined_table_name}.{joined_column_name} "
            if not intersection:
                query += f"WHERE {joined_table_name}.{joined_column_name} IS NULL "
                if join_type == "FULL JOIN":
                    query += f"OR WHERE {self.table_name}.{column_name} IS NULL "
            query += ";"
            result = [self.model(**dict(e.items())) for e in await self.pool.fetch(query)]
        except exceptions.PostgresError:
            LOG.exception(f"Cannot perform the join ('{query}')")
        else:
            return result
