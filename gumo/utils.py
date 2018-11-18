import logging
import os

from discord.ext.commands import converter

LOG = logging.getLogger('bot')


def get_project_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def get_project_name():
    return os.path.basename(os.path.dirname(__file__))


def code_block(message):
    return "```" + str(message) + "```"


def get_extension_name_from_ctx(ctx):
    return ctx.cog.__module__.split(".")[:2][1]


def get_channel_repr(channel):
    return f"{channel.guild.name}#{channel.name}"


class MultiKeyDict(dict):

    def __setitem__(self, key, value):
        for k in key:
            super(MultiKeyDict, self).__setitem__(k, value)
