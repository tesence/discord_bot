import importlib.util


class Config:

    def load(self, config_file):
        """Load the configuration variable according to the file name"""
        try:
            spec = importlib.util.spec_from_file_location("conf", config_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attribute in dir(module):
                if not attribute.startswith("__"):
                    setattr(self, attribute, getattr(module, attribute))

        except Exception as e:
            if type(e) == ImportError:
                message = f"Cannot find the configuration file '{config_file}'"
            else:
                message = f"Cannot import the configuration file '{config_file}'"
            raise type(e)(message)


CONF = Config()
