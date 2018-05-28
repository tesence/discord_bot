import asyncio
import logging
import os

import aiohttp

from discord_bot import cfg
from discord_bot import log

CONF = cfg.CONF

LOG = logging.getLogger('debug')


def check_is_admin(ctx):
    return _is_admin(ctx.message.author)


def _is_admin(user):
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


async def request(url, headers):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                status_code = resp.status
                if status_code == 200:
                    return await resp.json()
                elif 400 < status_code < 500:
                    LOG.error(f"Bad request {url} ({status_code})")
                elif 500 <= status_code < 600:
                    LOG.error(f"The request didn't succeed {url} ({status_code})")

    except Exception as e:
        message = None
        if type(e) == aiohttp.client_exceptions.ClientError:
            message = "An error has occured"
        elif type(e) == asyncio.TimeoutError:
            message = "The timeout has been reached"
        message += f" while requesting the url {url}"

        LOG.error(log.get_log_exception_message(message, e))
