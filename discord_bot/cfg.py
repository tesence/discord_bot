import os
import yaml


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
        self.attrs = {}

    def __contains__(self, item):
        return item in self.attrs

    def get(self, key, default_value=None, guild_id=None, default=False):
        if key in self.attrs:
            return self.attrs.get(key, default_value)

        value = None
        if self.attrs.get(guild_id, None):
            value = self.attrs[guild_id].get(key)

        if default:
            value = value or self.attrs['default'].get(key)

        return value or default_value

    def _load_file(self, path, name):
        with open(os.path.join(path, name), 'r') as f:
            return yaml.safe_load(f) or {}

    def load(self, config_folder):
        if not os.path.isdir(config_folder):
            return ConfigurationFolderNotFound(config_folder)

        candidates = [f for f in os.listdir(config_folder) if f.endswith('.yaml')]
        for candidate in candidates:
            candidate_name = candidate.rsplit(".", 1)[0]
            data = self._load_file(config_folder, candidate)
            if candidate_name == "config":
                self.attrs.update(data)
            elif candidate_name == "default":
                self.attrs.update({'default': data})
            else:
                guild_id = data.pop('GUILD_ID', None)
                if data and not guild_id:
                    raise MissingGuildIDError(candidate)
                self.attrs.update({guild_id: data})


config = Config()
