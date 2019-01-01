from datetime import datetime, timedelta
import logging
import re
from urllib import parse

import sanic
from sanic import response

from gumo.api import base
from gumo import config

LOG = logging.getLogger('bot')

TWITCH_API_URL = "https://api.twitch.tv/helix"
WEBHOOK_URL = f"{TWITCH_API_URL}/webhooks/hub"
TOPIC_REGEX = r".*https:\/\/api\.twitch\.tv/helix/streams\?user_id=(\d+).*"
SUBSCRIPTION_DURATION = 86400


class TokenSession(base.APIClient):

    def __init__(self, loop):
        super(TokenSession, self).__init__(loop=loop)
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


class TwitchWebhookServer(base.APIClient):

    def __init__(self, loop, callback):
        headers = {"Client-ID": config.glob['TWITCH_API_CLIENT_ID']}
        super(TwitchWebhookServer, self).__init__(headers=headers, loop=loop, bucket=base.RateBucket(800, 60))
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

    async def _get_webhook_action_params(self, mode, user_id):
        await self._set_external_host()
        topic = f"{TWITCH_API_URL}/streams?user_id={user_id}"
        lease_seconds = SUBSCRIPTION_DURATION
        data = {
            'hub.mode': mode,
            'hub.topic': topic,
            'hub.callback': self._external_host,
            'hub.lease_seconds': lease_seconds
        }
        return data

    async def subscribe_missing_streams(self, streams):
        body = await self._list_subscriptions()
        subscription_users = [re.search(TOPIC_REGEX, sub['topic']).group(1) for sub in body['data']]

        missing_subscriptions = set(stream.id for stream in streams) - set(subscription_users)
        if missing_subscriptions:
            LOG.info(f"There is no subscription for the users: {missing_subscriptions}")
            for user_id in missing_subscriptions:
                await self.subscribe(user_id)

    async def refresh_outdated_subscriptions(self):
        body = await self._list_subscriptions()
        now = datetime.utcnow()
        for sub in body['data']:
            user_id = re.search(TOPIC_REGEX, sub['topic']).group(1)
            expires_at = sub['expires_at']

            duration_left = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ") - now
            if duration_left < timedelta(seconds=SUBSCRIPTION_DURATION * 5/60):
                await self.unsubscribe(user_id)
                await self.subscribe(user_id)
                LOG.info(f"The subscription for '{user_id}' has expired '{expires_at}', it has been refreshed")

    async def subscribe(self, user_id):
        headers = await self._token_session.get_authorization_header()
        data = await self._get_webhook_action_params('subscribe', user_id)
        await self.post(WEBHOOK_URL, data, headers=headers)
        LOG.debug(f"Subscription to '{user_id}' successful")

    async def unsubscribe(self, user_id):
        headers = await self._token_session.get_authorization_header()
        data = await self._get_webhook_action_params('unsubscribe', user_id)
        await self.post(WEBHOOK_URL, data, headers=headers)
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
            user_id = re.search(TOPIC_REGEX, request.headers['Link']).group(1)
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
