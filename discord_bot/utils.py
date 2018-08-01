import logging
import os

from discord_bot import cfg

CONF = cfg.CONF

LOG = logging.getLogger('debug')


def check_is_admin(ctx):
    return is_admin(ctx.author)


def is_admin(user):
    if not CONF.ADMIN_ROLES:
        return True
    author_roles = [role.name for role in user.roles]
    return user.id == 133313675237916672 or set(author_roles) & set(CONF.ADMIN_ROLES)


def get_project_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def get_project_name():
    return os.path.basename(os.path.dirname(__file__))


def code_block(message):
    return "```" + str(message) + "```"
