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
        headers = {"Client-ID": config['TWITCH_API_CLIENT_ID']}
        super().__init__(headers=headers, loop=loop)

    async def get_users_by_login(self, *user_logins):
        """Retrieve all users.

        :param user_logins: names whose we want the id
        """
        url = f"{TWITCH_API_URL}/users?{parse.urlencode([('login', user_id) for user_id in user_logins])}"
        headers = await self._token_session.get_authorization_header()
        body = await self.get(url, return_json=True, headers=headers)
        return {user['login']: user for user in body['data']}

    async def get_users_by_id(self, *user_ids):
        """Retrieve all users.

        :param user_ids: ids whose we want the name
        """
        url = f"{TWITCH_API_URL}/users?{parse.urlencode([('id', user_id) for user_id in user_ids])}"
        headers = await self._token_session.get_authorization_header()
        body = await self.get(url, return_json=True, headers=headers)
        return {user['id']: user for user in body['data']}

    async def get_games_by_id(self, *game_ids):
        """Retrieve all games.

        :param game_ids: ids whose we want the name
        """
        url = f"{TWITCH_API_URL}/games?{parse.urlencode([('id', game_id) for game_id in game_ids])}"
        headers = await self._token_session.get_authorization_header()
        body = await self.get(url, return_json=True, headers=headers)
        return {game['id']: game for game in body['data']}

    async def get_stream_status(self, *user_ids):
        """Retrieve all stream status.

        :param user_ids: ids whose we want the status
        """
        url = f"{TWITCH_API_URL}/streams?{parse.urlencode([('user_id', user_id) for user_id in user_ids])}"
        headers = await self._token_session.get_authorization_header()
        body = await self.get(url, return_json=True, headers=headers)
        return {stream['id']: stream for stream in body['data']}
