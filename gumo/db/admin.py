from gumo.db import base


class Prefix(base.BaseModel):

    __tablename__ = "prefixes"
    __table_args__ = base.UniqueConstraint('guild_id', 'name'),

    guild_name = base.Column('varchar(255)', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    name = base.Column('varchar(255)', nullable=False)


class Extension(base.BaseModel):

    __tablename__ = "extensions"
    __table_args__ = base.UniqueConstraint('guild_id', 'name'),

    guild_name = base.Column('varchar(255)', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    name = base.Column('varchar(255)', nullable=False)


class AdminRole(base.BaseModel):

    __tablename__ = "admin_roles"
    __table_args__ = base.UniqueConstraint('guild_id', 'id'),

    guild_name = base.Column('varchar(255)', nullable=False)
    guild_id = base.Column('bigint', nullable=False)
    name = base.Column('varchar(255)', nullable=False)
    id = base.Column('bigint', nullable=False)


class PrefixDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, Prefix)


class ExtensionDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, Extension)


class AdminRoleDBDriver(base.DBDriver):

    def __init__(self, bot):
        super().__init__(bot, AdminRole)
