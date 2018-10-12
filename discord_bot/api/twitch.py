import aiohttp
import logging

from discord_bot.api import base
from discord_bot import config


LOG = logging.getLogger('bot')

TWITCH_API_URL = "https://api.twitch.tv/kraken"


WARNING_EXCEPTIONS = (aiohttp.ClientPayloadError, aiohttp.ServerDisconnectedError)


class TwitchAPIClient(base.APIClient):

    def __init__(self, loop):
        headers = {
            "Client-ID": config.TWITCH_API_CLIENT_ID,
            "accept": "application/vnd.twitchtv.v5+json"
        }
        super(TwitchAPIClient, self).__init__(base_url=TWITCH_API_URL, headers=headers, loop=loop,
                                              warning_exceptions=WARNING_EXCEPTIONS)

    async def get_ids(self, *names):
        """Retrieve all user ids.

        :param names: names whose we want the id
        """
        uri = f"/users?login={','.join(names)}"
        body = await self.get(uri)
        if body:
            try:
                data = {user['name']: user['_id'] for user in body['users']}
            except:
                LOG.exception(f"Cannot retrieve channel ids")
            else:
                return data

    async def get_status(self, *ids):
        """Retrieve all stream status.

        :param ids: twitch ids whose we want the status
        """
        uri = f"/streams?channel={','.join(ids)}"
        body = await self.get(uri)
        if body:
            try:
                data = {str(stream['channel']['_id']): stream for stream in body['streams']}
            except:
                LOG.exception(f"Cannot retrieve stream data")
            else:
                return data
