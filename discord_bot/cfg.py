import importlib


class Config:

    def load(self, filename):
        try:
            module = importlib.import_module("etc." + filename)

            self.CONF_NAME = filename

            # CLIENT
            self.COMMAND_PREFIX = getattr(module, "COMMAND_PREFIX", "!")
            self.ADMIN_ROLES = getattr(module, "ADMIN_ROLES", [])
            self.LOADED_EXTENSIONS = getattr(module, "LOADED_EXTENSIONS", [])
            self.DISCORD_BOT_TOKEN = getattr(module, "DISCORD_BOT_TOKEN")

            # TWITCH COG
            self.TWITCH_API_URL = getattr(module, "TWITCH_API_URL",  "https://api.twitch.tv/kraken")
            self.TWITCH_API_ACCEPT = getattr(module, "TWITCH_API_ACCEPT", "application/vnd.twitchtv.v5+json")
            self.TWITCH_API_CLIENT_ID = getattr(module, "TWITCH_API_CLIENT_ID")
            self.MIN_OFFLINE_DURATION = getattr(module, "MIN_OFFLINE_DURATION", 60)

            # SR COG
            self.SR_API_URL = getattr(module, "SR_API_URL", "https://www.speedrun.com/api/v1")
            self.SR_API_KEY = getattr(module, "SR_API_KEY")

            # DAB COG
            self.DAB_COOLDOWN = getattr(module, "DAB_COOLDOWN", 0)

            # DATABASE
            self.DB_HOST = getattr(module, "DB_HOST")
            self.DB_PORT = getattr(module, "DB_PORT", 5432)
            self.DB_NAME = getattr(module, "DB_NAME")
            self.DB_USER = getattr(module, "DB_USER")
            self.DB_PASSWORD = getattr(module, "DB_PASSWORD")

        except Exception as e:
            if type(e) == ImportError:
                message = "Cannot find the configuration file 'etc/{filename}.py'".format(filename=filename)
            elif type(e) == AttributeError:
                message = "Missing configuration variable: {key}".format(key=e.args[0])
            else:
                message = "Cannot import the configuration file 'etc/{filename}.py'".format(filename=filename)
            raise type(e)(message)


CONF = Config()
