class MultiKeyDict(dict):

    def __setitem__(self, key, value):
        for k in key:
            super().__setitem__(k, value)
