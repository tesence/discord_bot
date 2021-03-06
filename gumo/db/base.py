import logging

import asyncpg
from asyncpg import exceptions

from gumo import config


LOG = logging.getLogger(__name__)


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
        self.column_names = list(column_names)


class BaseModel:

    __tablename__ = None
    __table_args__ = ()

    @classmethod
    def columns(cls):
        return {name: definition for name, definition in vars(cls).items() if isinstance(definition, Column)}

    @classmethod
    def constraint(cls):
        if cls.__table_args__:
            for arg in cls.__table_args__:
                if isinstance(arg, UniqueConstraint):
                    return arg.column_names
        return [name for name, definition in cls.columns().items() if definition.primary_key]

    @classmethod
    async def create(cls, pool):
        try:
            column_definitions = []
            for column_name, column in cls.columns().items():
                column_definition = f"{column_name} {column.type}"
                column_definition += (not column.nullable) * " NOT NULL"
                column_definition += column.primary_key * " PRIMARY KEY"
                column_definition += (column.default is not None) * f" DEFAULT {column.default}"
                column_definitions.append(column_definition)
                if column.foreign_key:
                    foreign_key = f"FOREIGN KEY ({column_name}) REFERENCES {column.foreign_key.model_name}" \
                        f"({column.foreign_key.column_name})"
                    column_definitions.append(foreign_key)

            for arg in cls.__table_args__:
                if isinstance(arg, UniqueConstraint):
                    constraint = f"CONSTRAINT {cls.__tablename__}_{'_'.join(arg.column_names)} " \
                        f"UNIQUE ({', '.join(arg.column_names)})"
                    column_definitions.append(constraint)

            query = f"CREATE TABLE IF NOT EXISTS {cls.__tablename__} ({', '.join(column_definitions)});"
            await pool.execute(query)
        except exceptions.PostgresError:
            LOG.exception(f"Cannot create table {cls.__tablename__}")

    def __init__(self, **kwargs):
        for column in self.columns():
            setattr(self, column, kwargs.get(column))

    def __repr__(self):
        formatted_attributes = [f'{column}={getattr(self, column)}' for column in self.columns()]
        return f"<{self.__class__.__name__} {' '.join(formatted_attributes)}>"


class DBDriver:

    def __init__(self, bot, model):
        self.bot = bot
        self.model = model
        self.table_name = self.model.__tablename__

    async def init(self):
        self.bot.pool = self.bot.pool or await asyncpg.create_pool(min_size=2, **config['DATABASE_CREDENTIALS'],
                                                                   max_inactive_connection_lifetime=604800)
        await self.model.create(self.bot.pool)
        size = await self.count()
        LOG.debug(f"Number of '{self.table_name}' found: {size}")

    def _get_obj(self, record):
        return self.model(**dict(record.items())) if record else None

    @staticmethod
    def _get_formatted_data(**filters):
        formatted_filters = [f'{column} = ${index}' if filters[column] is not None else f'{column} IS NULL'
                             for index, column in enumerate(filters, 1)]
        filtered_values = [value for value in filters.values() if value is not None]
        return formatted_filters, filtered_values

    async def count(self):
        query = f"SELECT COUNT(*) FROM {self.table_name}"
        record = await self.bot.pool.fetchrow(query)
        return record['count']

    async def _list(self, order_by=None, desc=False, limit=0, **filters):
        formatted_filters, filtered_values = self._get_formatted_data(**filters)
        query = f"SELECT * FROM {self.table_name}"
        query += bool(filters) * f" WHERE {' AND '.join(formatted_filters)}"
        query += bool(order_by) * (f" ORDER BY {order_by}" + desc * " DESC")
        query += bool(limit) * f" LIMIT {limit}"
        return await self.bot.pool.fetch(query, *filtered_values)

    async def list(self, order_by=None, desc=False, limit=0, **filters):
        records = await self._list(order_by=order_by, desc=desc, limit=limit, **filters)
        return [self._get_obj(r) for r in records]

    async def get(self, order_by=None, desc=False, **filters):
        records = await self._list(order_by=order_by, desc=desc, limit=1, **filters)
        return self._get_obj(records[0]) if records else None

    async def create(self, *values, columns=None, ensure=False):
        columns = columns or self.model.columns()
        joined_constraint_columns = ", ".join(self.model.constraint())
        joined_columns = ", ".join(columns)
        joined_markers = ", ".join(f'${index}' for index in range(1, len(columns) + 1))
        query = f"INSERT INTO {self.table_name} ({joined_columns}) VALUES ({joined_markers}) "
        query += ensure * f"ON CONFLICT ({joined_constraint_columns}) DO NOTHING"
        query += " RETURNING *"
        async with self.bot.pool.acquire() as connection:
            records = [await connection.fetchrow(query, *value) for value in values]
            return [self._get_obj(r) for r in records if r]

    async def delete(self, **filters):
        if not filters:
            raise RuntimeError("Cannot delete using empty filters")
        formatted_filters, filtered_values = self._get_formatted_data(**filters)
        query = f"DELETE FROM {self.table_name}"
        query += bool(filters) * f" WHERE {' AND '.join(formatted_filters)}"
        query += " RETURNING *"
        records = await self.bot.pool.fetch(query, *filtered_values)
        return [self._get_obj(r) for r in records if r]

    async def update(self, column, value, **filters):
        if not filters:
            raise RuntimeError("Cannot update using empty filters")
        formatted_filters, filtered_values = self._get_formatted_data(**filters)
        value = f"'{value}'" if value is not None else "NULL"
        query = f"UPDATE {self.table_name} SET {column} = {value}"
        query += bool(filters) * f" WHERE {' AND '.join(formatted_filters)}"
        query += " RETURNING *"
        records = await self.bot.pool.fetch(query, *filtered_values)
        return [self._get_obj(r) for r in records if r]
