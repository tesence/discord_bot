import importlib


class Config:

    def load(self, filename):
        """Load the configuration variable according to the file name"""
        try:
            self.CONF_NAME = filename
            module = importlib.import_module("etc." + filename)
            for attribute in dir(module):
                if not attribute.startswith("__"):
                    setattr(self, attribute, getattr(module, attribute))

        except Exception as e:
            if type(e) == ImportError:
                message = f"Cannot find the configuration file 'etc/{filename}.py'"
            else:
                message = f"Cannot import the configuration file 'etc/{filename}.py'"
            raise type(e)(message)


CONF = Config()
