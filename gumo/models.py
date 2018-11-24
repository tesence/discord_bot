class MultiKeyDict(dict):

    def __setitem__(self, key, value):
        for k in key:
            super(MultiKeyDict, self).__setitem__(k, value)
