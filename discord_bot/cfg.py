import importlib


class Config:

    def __init__(self):

        self.CONF_NAME = None

        # CLIENT
        self.COMMAND_PREFIX = None
        self.DISCORD_BOT_TOKEN = None

        # TWITCH COG
        self.TWITCH_API_URL = None
        self.TWITCH_API_ACCEPT = None
        self.TWITCH_API_CLIENT_ID = None
        self.MIN_OFFLINE_DURATION = None

        # SR COG
        self.SR_API_URL = None
        self.SR_API_KEY = None

        # DATABASE
        self.DB_HOST = None
        self.DB_PORT = None
        self.DB_NAME = None
        self.DB_USER = None
        self.DB_PASSWORD = None

    def load(self, filename):

        module = importlib.import_module("etc." + filename)

        self.CONF_NAME = filename

        # CLIENT
        self.COMMAND_PREFIX = module.COMMAND_PREFIX
        self.DISCORD_BOT_TOKEN = module.DISCORD_BOT_TOKEN

        # TWITCH COG
        self.TWITCH_API_URL = module.TWITCH_API_URL
        self.TWITCH_API_ACCEPT = module.TWITCH_API_ACCEPT
        self.TWITCH_API_CLIENT_ID = module.TWITCH_API_CLIENT_ID
        self.MIN_OFFLINE_DURATION = module.MIN_OFFLINE_DURATION

        # SR COG
        self.SR_API_URL = module.SR_API_URL
        self.SR_API_KEY = module.SR_API_KEY

        # DATABASE
        self.DB_HOST = module.DB_HOST
        self.DB_PORT = module.DB_PORT
        self.DB_NAME = module.DB_NAME
        self.DB_USER = module.DB_USER
        self.DB_PASSWORD = module.DB_PASSWORD


CONF = Config()
