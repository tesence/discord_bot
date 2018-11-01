import asyncio
import logging

from discord.ext.commands import errors

from gumo import config
from gumo import db

LOG = logging.getLogger('bot')

DB_CONF_VARIABLES = ['DATABASE_CREDENTIALS']


class MissingCogConfigurationVariable(errors.CommandError):
    """Required configuration variable is missing"""

    def __init__(self, config_variable):
        message = f"Missing the configuration variable '{config_variable}'"
        super(MissingCogConfigurationVariable, self).__init__(message)


class CogMixin:

    def __init__(self, bot, *conf_variables):
        self.bot = bot
        self.conf_variables = conf_variables
        self._check_required_conf_variables()

    def _check_required_conf_variables(self):
        if not self.conf_variables:
            return
        LOG.debug(f"Checking configuration variables for the cog '{type(self).__name__}': {self.conf_variables}")
        for config_variable in self.conf_variables:
            if config_variable not in config:
                raise MissingCogConfigurationVariable(config_variable)


class DBCogMixin(CogMixin):

    def __init__(self, bot, *conf_variables):
        super(DBCogMixin, self).__init__(bot, *(list(conf_variables) + DB_CONF_VARIABLES))
        self.pool = None
        self.connection_ready = asyncio.Event(loop=self.bot.loop)
        asyncio.ensure_future(self.setup_database_connection(), loop=self.bot.loop)

    async def setup_database_connection(self):
        self.pool = await db.get_pool()
        self.connection_ready.set()
