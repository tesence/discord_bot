import os
import logging
import yaml

LOG = logging.getLogger('bot')


class ConfigurationFolderNotFound(Exception):
    """Configuration folder does not exist"""


class ConfigurationVariableNotFound(Exception):
    """Configuration variable does not exist"""


class MissingGuildIDError(Exception):
    """Configuration file is missing a guild id"""

    def __init__(self, attribute):
        message = f"The file '{attribute}' is missing a guild id"
        super(MissingGuildIDError, self).__init__(message)


class Config:

    def __init__(self):
        self.config_folder = None
        self.attrs = {}

    def __contains__(self, item):
        return item in self.attrs

    @staticmethod
    def _load_file(path, name):
        with open(os.path.join(path, name), 'r') as f:
            return yaml.safe_load(f) or {}

    def get(self, key, default_value=None, guild_id=None, default=False):
        candidates = (
            self.attrs.get(key, None),
            self.attrs[guild_id].get(key, None) if self.attrs.get(guild_id, None) else None,
            self.attrs['default'].get(key, None) if default else None,
            default_value
        )
        return next((c for c in candidates if c is not None), None)

    def load(self, config_folder=None):
        self.config_folder = config_folder or self.config_folder
        if not os.path.isdir(self.config_folder):
            return ConfigurationFolderNotFound(self.config_folder)
        self.attrs = {} if self.attrs else self.attrs
        candidates = [f for f in os.listdir(self.config_folder) if f.endswith('.yaml')]
        for candidate in candidates:
            candidate_name = candidate.rsplit(".", 1)[0]
            data = self._load_file(self.config_folder, candidate)
            if candidate_name == "config":
                self.attrs.update(data)
            elif candidate_name == "default":
                self.attrs.update({'default': data})
            else:
                guild_id = data.pop('GUILD_ID', None)
                if data and not guild_id:
                    raise MissingGuildIDError(candidate)
                self.attrs.update({guild_id: data})
        LOG.debug(f"Loaded configuration: {self.attrs}")


config = Config()
