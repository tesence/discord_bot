from datetime import datetime, timedelta
import logging
import re
from urllib import parse

import sanic
from sanic import response

from gumo.api import base
from gumo import config

LOG = logging.getLogger(__name__)

TWITCH_API_URL = "https://api.twitch.tv/helix"
WEBHOOK_URL = f"{TWITCH_API_URL}/webhooks/"
SUBSCRIPTION_DURATION = 86400


class TokenSession(base.APIClient):

    def __init__(self, loop):
        super().__init__(loop=loop)
        self._token = None
        self._expires_at = None

    async def get_token(self):
        now = datetime.utcnow()
        need_refresh = True if not self._expires_at else now > self._expires_at

        if need_refresh:
            params = {
                'client_id': config.glob['TWITCH_API_CLIENT_ID'],
                'client_secret': config.glob['TWITCH_API_CLIENT_SECRET'],
                'grant_type': "client_credentials"
            }
            url = f"https://id.twitch.tv/oauth2/token?{parse.urlencode(params)}"
            token_data = await self.post(url, return_json=True)
            self._token = token_data['access_token']
            self._expires_at = now + timedelta(seconds=token_data['expires_in'])
            LOG.debug(f"New token issued: {token_data['access_token']} (expires on {self._expires_at})")

        return self._token

    async def get_authorization_header(self):
        token = await self.get_token()
        return {'Authorization': f"Bearer {token}"}


class StreamChanged:
    URL = f"{TWITCH_API_URL}/streams"
    REGEX = r".*https:\/\/api\.twitch\.tv/helix/streams\?user_id=(\d+).*"

    @property
    def as_uri(self):
        return f"{self.URL}?user_id={self.user_id}"

    def __init__(self, user_id):
        self.user_id = user_id


class TwitchWebhookServer(base.APIClient):

    def __init__(self, loop, callback):
        headers = {"Client-ID": config.glob['TWITCH_API_CLIENT_ID']}
        super().__init__(headers=headers, loop=loop, bucket=base.RateBucket(800, 60))
        self._app = sanic.Sanic(configure_logging=False)
        self._app.add_route(self._handle_get, "/", methods=['GET'])
        self._app.add_route(self._handle_post, "/", methods=['POST'])
        self._server = None
        self._external_host = None
        self._port = None
        self._token_session = TokenSession(loop)
        self._callback = callback

    async def _set_external_host(self):
        if not self._external_host:
            external_ip = await self.get('https://api.ipify.org/')
            self._external_host = f"http://{external_ip}:{self._port}"

    async def _get_webhook_action_params(self, mode, topic, lease_seconds=SUBSCRIPTION_DURATION):
        await self._set_external_host()
        data = {
            'hub.mode': mode,
            'hub.topic': topic.as_uri,
            'hub.callback': self._external_host,
            'hub.lease_seconds': lease_seconds
        }
        return data

    async def update_subscriptions(self, user_ids):
        subscriptions = await self._list_subscriptions()
        subcribed_users_by_id = {
            re.search(StreamChanged.REGEX, sub['topic']).group(1): sub
            for sub in subscriptions['data']
        }

        missing_subscriptions = set()
        outdated_subscriptions = set()
        now = datetime.utcnow()

        for user_id in user_ids:

            # If the subscription is missing
            if user_id not in subcribed_users_by_id:
                missing_subscriptions.add(user_id)

            else:
                expires_at = subcribed_users_by_id[user_id]['expires_at']
                duration_left = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ") - now

                # If the subscription expires in less than an hour
                if duration_left < timedelta(seconds=33200):
                    outdated_subscriptions.add(user_id)

        if missing_subscriptions:
            LOG.info(f"No subscription for users: {missing_subscriptions}")

        if outdated_subscriptions:
            LOG.info(f"Outdated subscriptions for users: {outdated_subscriptions}")

        await self.unsubscribe(*outdated_subscriptions)
        await self.subscribe(*missing_subscriptions | outdated_subscriptions)

    async def subscribe(self, *user_ids):
        headers = await self._token_session.get_authorization_header()
        for user_id in user_ids:
            data = await self._get_webhook_action_params('subscribe', StreamChanged(user_id))
            await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)
            LOG.debug(f"Subscription to '{user_id}' successful")

    async def unsubscribe(self, *user_ids):
        headers = await self._token_session.get_authorization_header()
        for user_id in user_ids:
            data = await self._get_webhook_action_params('unsubscribe', StreamChanged(user_id))
            await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)
            LOG.debug(f"Unsubscription from '{user_id}' successful")

    async def _list_subscriptions(self):
        headers = await self._token_session.get_authorization_header()
        return await self.get("https://api.twitch.tv/helix/webhooks/subscriptions?first=100", return_json=True,
                              headers=headers)

    @staticmethod
    def _log_request(request):
        LOG.debug(f"Incoming request from '{request.ip}:{request.port}': "
                  f"'{request.method} http://{request.host}{request.path}' "
                  f"headers={request.headers}, args={request.args}, body={request.body}")

    async def _handle_get(self, request):
        self._log_request(request)
        mode = request.args['hub.mode'][0] if 'hub.mode' in request.args else None
        challenge = request.args['hub.challenge'][0] if 'hub.challenge' in request.args else None

        if mode == 'denied':
            LOG.warning(f"A subscription has been denied: {mode}")
            return response.HTTPResponse(body='200: OK', status=200)

        if challenge:
            LOG.debug(f"Challenge received: {challenge}")
            return response.HTTPResponse(body=challenge, headers={'Content-Type': 'application/json'})
        else:
            return response.HTTPResponse(body='200: OK', status=200)

    async def _handle_post(self, request):
        self._log_request(request)
        try:
            user_id = re.search(StreamChanged.REGEX, request.headers['Link']).group(1)
            await self._callback(user_id, request.json)
            return response.HTTPResponse(body='202: OK', status=202)
        except KeyError:
            return response.HTTPResponse(body='400: Bad Request', status=400)

    async def start(self, host, port):
        try:
            self._port = port
            self._server = await self._app.create_server(host=host, port=port)
            LOG.debug(f"Webhook server listening on {host}:{port}")
        except OSError:
            LOG.warning("A webhook server is already running")

    def stop(self):
        LOG.debug(f"Stopping webhook server...")
        self._server.close()
