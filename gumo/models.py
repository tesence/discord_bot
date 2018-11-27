class MultiKeyDict(dict):

    def __setitem__(self, key, value):
        for k in key:
            super(MultiKeyDict, self).__setitem__(k, value)


class NotifiedChannel:

    def __init__(self, channel, tags):
        self.channel = channel
        self.tags = tags
