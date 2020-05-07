import logging
from urllib import parse

from gumo.api import base
from gumo.api.twitch import TWITCH_API_URL
from gumo import config
from gumo.api.twitch import token

LOG = logging.getLogger(__name__)


class TwitchAPIClient(base.APIClient):

    def __init__(self, loop):
        self._token_session = token.TokenSession(loop)
        super().__init__(loop=loop)

    async def get_users(self, user_ids=(), user_logins=()):
        """Retrieve all users.

        :param user_ids: ids whose we want the user
        :param user_logins: logins whose we want the user
        """
        params = [('id', x) for x in user_ids] + [('login', x) for x in user_logins]
        url = f"{TWITCH_API_URL}/users?{parse.urlencode(params)}"
        headers = await self._token_session.get_authorization_headers()
        body = await self.get(url, return_json=True, headers=headers)
        return body['data']

    async def get_games(self, *game_ids):
        """Retrieve all games.

        :param game_ids: ids whose we want the name
        """
        url = f"{TWITCH_API_URL}/games?{parse.urlencode([('id', game_id) for game_id in game_ids])}"
        headers = await self._token_session.get_authorization_headers()
        body = await self.get(url, return_json=True, headers=headers)
        return body['data']
