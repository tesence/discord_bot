import logging

from discord_bot import cfg
from discord_bot import log
from discord_bot import utils


CONF = cfg.CONF
LOG = logging.getLogger('debug')

HEADERS = {
    "Client-ID": CONF.TWITCH_API_CLIENT_ID,
    "accept": CONF.TWITCH_API_ACCEPT
}


async def get_ids(*names):
    """Retrieve all user ids.

    :param names: names whose we want the id
    """
    url = f"{CONF.TWITCH_API_URL}/users?login={','.join(names)}"
    try:
        body = await utils.request(url, headers=HEADERS)
        users = body['users']
    except (KeyError, TypeError) as e:
        message = f"Cannot parse retrieved ids for {names}"
        LOG.error(log.get_log_exception_message(message, e))
    else:
        result = {user['name']: user['_id'] for user in users}
        LOG.debug(f"API data for {list(names)}: {result} ({url})")
        return result


async def get_status(*twitch_ids):
    """Retrieve all stream status.

    :param twitch_ids: twitch ids whose we want the status
    """
    ids = ','.join([str(twitch_id) for twitch_id in twitch_ids])
    url = f"{CONF.TWITCH_API_URL}/streams/?channel={ids}"
    body = await utils.request(url, headers=HEADERS)
    try:
        streams = body['streams']
    except (KeyError, TypeError) as e:
        message = "Cannot retrieve stream data"
        LOG.error(log.get_log_exception_message(message, e))
    else:
        return {stream['channel']['_id']: stream for stream in streams}
