import os
import yaml


class Config(dict):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_file = None

    def load(self, config_file=None):
        self.config_file = self.config_file or config_file
        with open(self.config_file, 'r') as f:
            self.update(yaml.safe_load(f))


config = Config()
