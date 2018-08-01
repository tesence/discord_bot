import logging

from discord_bot.api import base
from discord_bot import cfg
from discord_bot import log


CONF = cfg.CONF
LOG = logging.getLogger('debug')

HEADERS = {
    "Client-ID": CONF.TWITCH_API_CLIENT_ID,
    "accept": CONF.TWITCH_API_ACCEPT
}


class TwitchAPIClient(base.APIClient):

    def __init__(self):
        super(TwitchAPIClient, self).__init__(base_url=CONF.TWITCH_API_URL, headers=HEADERS)

    async def get_ids(self, *names):
        """Retrieve all user ids.

        :param names: names whose we want the id
        """
        uri = f"/users?login={','.join(names)}"
        try:
            body = await (await self.get(uri)).json()
            users = body['users']
        except (AttributeError, KeyError, TypeError) as e:
            message = f"Cannot parse retrieved ids for {names}"
            LOG.error(log.get_log_exception_message(message, e))
        else:
            result = {user['name']: user['_id'] for user in users}
            LOG.debug(f"API data for {list(names)}: {result} ({uri})")
            return result

    async def get_status(self, *twitch_ids):
        """Retrieve all stream status.

        :param twitch_ids: twitch ids whose we want the status
        """
        ids = ','.join([str(twitch_id) for twitch_id in twitch_ids])
        uri = f"/streams/?channel={ids}"
        try:
            body = await (await self.get(uri)).json()
            streams = body['streams']
        except (AttributeError, KeyError, TypeError) as e:
            message = "Cannot retrieve stream data"
            LOG.error(log.get_log_exception_message(message, e))
        else:
            return {stream['channel']['_id']: stream for stream in streams}

