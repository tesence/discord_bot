import logging

from discord.ext.commands import errors

from discord_bot import cfg

CONF = cfg.CONF
LOG = logging.getLogger('debug')

DB_CONF_VARIABLES = ['DATABASE_CREDENTIALS']


class MissingCogConfigurationVariable(errors.CommandError):
    """Required configuration variable is missing"""


class BadCogConfigurationVariable(errors.CommandError):
    """Required configuration variable has a bad value"""


class CogMixin:

    def __init__(self, bot, conf_variables):
        self.bot = bot
        self.conf_variables = conf_variables
        self._check_required_conf_variables()

    def _check_required_conf_variables(self):
        LOG.debug(f"Checking configuration variables for the cog '{type(self).__name__}': {self.conf_variables}")
        for conf_variable in self.conf_variables:
            if not hasattr(CONF, conf_variable):
                msg = f"Missing the configuration variable: {conf_variable}"
                raise MissingCogConfigurationVariable(msg)
            elif getattr(CONF, conf_variable) is None:
                msg = f"Bad configuration variable value: {conf_variable}"
                raise BadCogConfigurationVariable(msg)


class DBCogMixin(CogMixin):

    def __init__(self, bot, conf_variables):
        super(DBCogMixin, self).__init__(bot, list(conf_variables) + DB_CONF_VARIABLES)
