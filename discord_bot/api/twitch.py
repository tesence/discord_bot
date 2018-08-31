import logging

from discord_bot.api import base
from discord_bot import cfg


CONF = cfg.CONF
LOG = logging.getLogger('bot')

HEADERS = {
    "Client-ID": CONF.TWITCH_API_CLIENT_ID,
    "accept": CONF.TWITCH_API_ACCEPT
}


class TwitchAPIClient(base.APIClient):

    def __init__(self, loop):
        super(TwitchAPIClient, self).__init__(base_url=CONF.TWITCH_API_URL, headers=HEADERS, loop=loop)

    async def get_ids(self, *names):
        """Retrieve all user ids.

        :param names: names whose we want the id
        """
        uri = f"/users?login={','.join(names)}"
        try:
            body = await (await self.get(uri)).json()
            users = body['users']
        except (KeyError, TypeError):
            LOG.exception(f"Cannot parse retrieved ids for {names}")
        except AttributeError:
            pass
        else:
            result = {user['name']: int(user['_id']) for user in users}
            LOG.debug(f"API data for {list(names)}: {result} ({uri})")
            return result
        return {}

    async def get_status(self, *twitch_ids):
        """Retrieve all stream status.

        :param twitch_ids: twitch ids whose we want the status
        """
        ids = ','.join([str(twitch_id) for twitch_id in twitch_ids])
        uri = f"/streams/?channel={ids}"
        try:
            body = await (await self.get(uri)).json()
            streams = body['streams']
        except (KeyError, TypeError):
            LOG.exception("Cannot retrieve stream data")
        except AttributeError:
            pass
        else:
            return {stream['channel']['_id']: stream for stream in streams}
        return {}

