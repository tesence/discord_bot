import os
import logging
import yaml

LOG = logging.getLogger(__name__)


class ConfigurationFolderNotFound(Exception):
    """Configuration folder does not exist"""


class MissingGuildIDError(Exception):
    """Configuration file is missing a guild id"""

    def __init__(self, attribute):
        message = f"The file '{attribute}' is missing a guild id"
        super().__init__(message)


class Config:

    def __init__(self):
        self.config_folder = None
        self.glob = {}
        self.attrs = {}

    @property
    def extensions_to_load(self):
        extensions_to_load = set()
        for c in list(self.attrs.values()):
            extensions = c.get('EXTENSIONS')
            if extensions:
                extensions_to_load = extensions_to_load | set(extensions)
        return extensions_to_load

    @staticmethod
    def _load_file(path, name):
        with open(os.path.join(path, name), 'r') as f:
            return yaml.safe_load(f) or {}

    def get(self, key, default=None, guild_id=None):
        result = default
        if guild_id in self.attrs:
            result = self.attrs[guild_id].get(key, default)
        return result

    def load(self, config_folder=None):
        if config_folder:
            self.config_folder = config_folder
        if not os.path.isdir(self.config_folder):
            raise ConfigurationFolderNotFound(self.config_folder)
        self.attrs = {}
        candidates = [f for f in os.listdir(self.config_folder) if f.endswith('.yaml')]
        for candidate in candidates:
            candidate_name = candidate.rsplit(".", 1)[0]
            data = self._load_file(self.config_folder, candidate)
            if candidate_name == "global":
                self.glob.update(data)
            else:
                guild_id = data.pop('GUILD_ID', None)
                if data and not guild_id:
                    raise MissingGuildIDError(candidate)
                self.attrs.update({guild_id: data})
        LOG.debug(f"Loaded global configuration: {self.glob}")
        LOG.debug(f"Loaded guild configurations: {self.attrs}")


config = Config()
