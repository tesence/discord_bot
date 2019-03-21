import abc
import asyncio
import collections
from datetime import datetime, timedelta
import hashlib
import hmac
import logging
import socket
from urllib import parse

import sanic
from sanic import response

from gumo.api import base
from gumo import config


LOG = logging.getLogger(__name__)

TWITCH_API_URL = "https://api.twitch.tv/helix"
WEBHOOK_URL = f"{TWITCH_API_URL}/webhooks/"


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


def log_request(route):

    async def inner(server, request, *args, **kwargs):
        LOG.debug(f"Incoming request from '{request.ip}:{request.port}': "
                  f"'{request.method} http://{request.host}{request.path}' "
                  f"headers={request.headers}, args={request.args}, body={request.body}")
        return await route(server, request, *args, **kwargs)

    return inner


def verify_payload(route):
    """Decorator which verifies that a request was been sent from Twitch by comparing the 'X-Hub-Signature' header.

    code from https://gist.github.com/SnowyLuma/a9fb1c2707dc005fe88b874297fee79f"""

    async def inner(server, request, *args, **kwargs):
        secret = config.glob['TWITCH_WEBHOOK_SECRET'].encode('utf-8')
        digest = hmac.new(secret, msg=request.body, digestmod=hashlib.sha256).hexdigest()

        if hmac.compare_digest(digest, request.headers.get('X-Hub-Signature', '')[7:]):
            return await route(server, request, *args, **kwargs)

        LOG.warning("The hash for this notification is invalid")
        return sanic.response.text(None, status=403)

    return inner


def remove_duplicates(route):
    """Decorator which prevents duplicate notifications being processed more than once.

    code from: https://gist.github.com/SnowyLuma/a9fb1c2707dc005fe88b874297fee79f"""

    async def inner(server, request, *args, **kwargs):
        notification_id = request.headers.get('Twitch-Notification-ID')

        if notification_id in server._notification_ids:
            LOG.warning(f'Received duplicate notification with ID {notification_id}, discarding.')

            return sanic.response.text(None, status=204)

        server._notification_ids.append(notification_id)
        return await route(server, request, *args, **kwargs)

    return inner


class TwitchWebhookServer(base.APIClient):

    def __init__(self, loop, callback):
        headers = {"Client-ID": config.glob['TWITCH_API_CLIENT_ID']}
        super().__init__(headers=headers, loop=loop, bucket=base.RateBucket(800, 60))
        self._token_session = TokenSession(loop)
        self._app = sanic.Sanic(configure_logging=False)
        self._app.add_route(self._handle_get, "/<topic>/<user_id:int>", methods=['GET'])
        self._app.add_route(self._handle_post, "/<topic>/<user_id:int>", methods=['POST'])
        self._host = socket.gethostbyname(socket.gethostname())
        self._port = config.glob['TWITCH_WEBHOOK_PORT']
        self._callback = callback
        self._external_host = None
        self._server = None

        # Store the 50 last notification ids to prevent duplicates
        self._notification_ids = collections.deque(maxlen=50)

        self._pending_subscriptions = {}
        self._pending_cancellation = {}

        loop.create_task(self._set_external_host())

    async def _set_external_host(self):
        if not self._external_host:
            external_ip = await self.get('https://api.ipify.org/')
            self._external_host = f"http://{external_ip}:{self._port}"
            LOG.debug(f"External host: {self._external_host}")

    async def _get_webhook_action_params(self, mode, topic, user_id, lease_seconds=0):
        data = {
            'hub.mode': mode,
            'hub.topic': topic.get_uri(user_id=user_id),
            'hub.callback': f"{self._external_host}/{topic.NAME}/{user_id}",
            'hub.lease_seconds': lease_seconds,
            'hub.secret': config.glob['TWITCH_WEBHOOK_SECRET']
        }
        return data

    async def list_subscriptions(self):
        headers = await self._token_session.get_authorization_header()
        return await self.get("https://api.twitch.tv/helix/webhooks/subscriptions?first=100", return_json=True,
                              headers=headers)

    async def subscribe(self, topic, *user_ids, duration=86400):
        headers = await self._token_session.get_authorization_header()

        tasks = {user_id: self._subscribe(topic, user_id, duration, headers) for user_id in user_ids}
        await asyncio.gather(*tasks.values())

        if not len(tasks) == len([task for task in tasks.values() if task]):
            LOG.warning(f"Subscriptions failed: {[user_id for user_id, task in tasks.items() if not task]}")

    async def _subscribe(self, topic, user_id, duration, headers):
        success = False

        data = await self._get_webhook_action_params('subscribe', topic, user_id, lease_seconds=duration)
        self._pending_subscriptions[data['hub.topic']] = asyncio.Event()
        await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)

        try:
            await asyncio.wait_for(self._pending_subscriptions[data['hub.topic']].wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        else:
            success = True
        self._pending_subscriptions.pop(data['hub.topic'])
        return success

    async def cancel(self, topic, *user_ids):
        headers = await self._token_session.get_authorization_header()

        tasks = {user_id: self._cancel(topic, user_id, headers) for user_id in user_ids}
        await asyncio.gather(*tasks.values())

        if not len(tasks) == len([task for task in tasks.values() if task]):
            LOG.warning(f"Cancellations failed: {[user_id for user_id, task in tasks.items() if not task]}")

    async def _cancel(self, topic, user_id, headers):
        success = False

        data = await self._get_webhook_action_params('unsubscribe', topic, user_id)
        await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)
        self._pending_cancellation[data['hub.topic']] = asyncio.Event()

        try:
            await asyncio.wait_for(self._pending_cancellation[data['hub.topic']].wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        else:
            success = True
        self._pending_cancellation.pop(data['hub.topic'])
        return success

    @log_request
    async def _handle_get(self, request, topic, user_id):
        mode = request.args['hub.mode'][0]
        challenge = request.args['hub.challenge'][0] if 'hub.challenge' in request.args else None

        if mode == 'denied':
            LOG.warning(f"A subscription has been denied: {mode}")
            return response.HTTPResponse(body='200: OK', status=200)

        if challenge:
            LOG.info(f"Challenge received: {challenge}")
            try:
                if mode == 'subscribe':
                    self._pending_subscriptions[request.args['hub.topic'][0]].set()
                elif mode == 'unsubscribe':
                    self._pending_cancellation[request.args['hub.topic'][0]].set()
            except KeyError:
                LOG.warning(f"A challenged has been received, {topic.NAME}/{user_id} but there is no pending action, "
                            f"the subscription might have been made externally")
            return response.HTTPResponse(body=challenge, headers={'Content-Type': 'application/json'})

    @log_request
    @verify_payload
    @remove_duplicates
    async def _handle_post(self, request, topic, user_id):
        await self._callback(topic, str(user_id), request.json)
        return response.HTTPResponse(body='202: OK', status=202)

    async def start(self):
        try:
            self._server = await self._app.create_server(host=self._host, port=self._port)
            LOG.debug(f"Webhook server listening on {self._host}:{self._port}")
        except OSError:
            LOG.exception("Cannot start the webhook server")

    def stop(self):
        LOG.debug(f"Stopping webhook server...")
        self._server.close()
        LOG.debug(f"Webhook server successfully stopped")


class Topic(abc.ABC):

    NAME = None
    URL = None

    __slots__ = ()

    @classmethod
    def get_uri(cls, **kwargs):
        params = [(slot, value) for slot, value in kwargs.items() if slot in cls.__slots__]
        return f"{cls.URL}?{parse.urlencode(params)}"


class StreamChanged(Topic):

    NAME = "streams"
    URL = f"{TWITCH_API_URL}/streams"

    __slots__ = ('user_id',)
