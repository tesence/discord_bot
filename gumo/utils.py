import os

import discord


def get_project_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def get_project_name():
    return os.path.basename(os.path.dirname(__file__))


def code_block(message):
    return "```" + str(message) + "```"


def get_channel_repr(channel):
    if isinstance(channel, discord.DMChannel):
        _repr = channel.recipient
    else:
        _repr = f"{channel.guild.name}#{channel.name}"
    return _repr
