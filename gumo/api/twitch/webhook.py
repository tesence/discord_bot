import abc
import asyncio
import collections
from datetime import datetime
import hashlib
import hmac
import logging
import socket
from urllib import parse

import sanic
from sanic import exceptions as sanic_exc
from sanic import handlers
from sanic import response

from gumo.api import base
from gumo.api.twitch import TWITCH_API_URL
from gumo import config
from gumo.api.twitch import token


LOG = logging.getLogger(__name__)

WEBHOOK_URL = f"{TWITCH_API_URL}/webhooks"


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
        secret = config['TWITCH_WEBHOOK_SECRET'].encode('utf-8')
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

        result = await route(server, request, *args, **kwargs)
        server._notification_ids.append(notification_id)
        return result

    return inner


class CustomErrorHandler(handlers.ErrorHandler):

    def default(self, request, exception):
        if isinstance(exception, sanic_exc.NotFound):
            LOG.warning(f"An exception has been ignored ({''.join(exception.args)})")
            return response.text("Error: Requested URL / not found", status=404)
        return super().default(request, exception)


class TwitchWebhookServer(base.APIClient):

    def __init__(self, loop, callback):

        headers = {"Client-ID": config['TWITCH_API_CLIENT_ID']}

        super().__init__(headers=headers, loop=loop, bucket=base.RateBucket(800, 60))
        self._token_session = token.TokenSession(loop)
        self._app = sanic.Sanic(error_handler=CustomErrorHandler(), configure_logging=False)
        self._app.add_route(self._handle_get, "<endpoint:[a-z/]+>", methods=['GET'])
        self._app.add_route(self._handle_post, "<endpoint:[a-z/]+>", methods=['POST'])
        self._host = socket.gethostbyname(socket.gethostname())
        self._port = config['TWITCH_WEBHOOK_PORT']
        self._callback = callback
        self._external_host = None
        self._server = None

        self._topic_by_endpoint = {topic.ENDPOINT: topic for topic in Topic.__subclasses__()}

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

    async def _get_webhook_action_params(self, mode, topic, duration=86400):
        data = {
            'hub.mode': mode,
            'hub.topic': topic.as_uri,
            'hub.callback': f"{self._external_host}{topic.ENDPOINT}?{parse.urlencode(topic.params)}",
            'hub.secret': config['TWITCH_WEBHOOK_SECRET']
        }
        if mode == 'subscribe':
            data['hub.lease_seconds'] = duration

        return data

    async def list_subscriptions(self):
        headers = await self._token_session.get_authorization_header()
        body = await self.get(f"{WEBHOOK_URL}/subscriptions?first=100", return_json=True, headers=headers)
        return [Subscription.get_subscription(sub) for sub in body['data']]

    async def subscribe(self, *topics, duration=86400):
        headers = await self._token_session.get_authorization_header()

        tasks = {topic: self._subscribe(topic, duration, headers) for topic in topics}
        await asyncio.gather(*tasks.values())

        if not len(tasks) == len([task for task in tasks.values() if task]):
            LOG.warning(f"Subscriptions failed: {[topic for topic, task in tasks.items() if not task]}")

    async def _subscribe(self, topic, duration, headers):
        success = False

        data = await self._get_webhook_action_params('subscribe', topic, duration)
        self._pending_subscriptions[topic.as_uri] = asyncio.Event()
        await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)

        try:
            await asyncio.wait_for(self._pending_subscriptions[topic.as_uri].wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        else:
            success = True
        self._pending_subscriptions.pop(topic.as_uri)
        return success

    async def cancel(self, *topics):
        headers = await self._token_session.get_authorization_header()

        tasks = {topic: self._cancel(topic, headers) for topic in topics}
        await asyncio.gather(*tasks.values())

        if not len(tasks) == len([task for task in tasks.values() if task]):
            LOG.warning(f"Cancellations failed: {[topic for topic, task in tasks.items() if not task]}")

    async def _cancel(self, topic, headers):
        success = False

        data = await self._get_webhook_action_params('unsubscribe', topic)
        await self.post(f"{WEBHOOK_URL}/hub", data, headers=headers)
        self._pending_cancellation[topic.as_uri] = asyncio.Event()

        try:
            await asyncio.wait_for(self._pending_cancellation[topic.as_uri].wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        else:
            success = True
        self._pending_cancellation.pop(topic.as_uri)
        return success

    @log_request
    async def _handle_get(self, request, endpoint):
        topic = self._topic_by_endpoint[f"/{endpoint}"](**{k: request.args.get(k) for k in request.args})
        mode = request.args['hub.mode'][0]

        if mode == 'denied':
            LOG.warning(f"A subscription has been denied for topic: {topic}")
            return response.HTTPResponse(body='200: OK', status=200)

        if 'hub.challenge' in request.args:
            challenge = request.args['hub.challenge'][0]
            LOG.info(f"Challenge received: {challenge}")
            try:
                if mode == 'subscribe':
                    self._pending_subscriptions[topic.as_uri].set()
                elif mode == 'unsubscribe':
                    self._pending_cancellation[topic.as_uri].set()
            except KeyError:
                LOG.warning(f"A challenge has been received, {topic} but there is no pending action, "
                            f"the subscription might have been made externally")
            return response.HTTPResponse(body=challenge, headers={'Content-Type': 'application/json'})

    @log_request
    @verify_payload
    @remove_duplicates
    async def _handle_post(self, request, endpoint):
        topic = self._topic_by_endpoint[f"/{endpoint}"](**{k: request.args.get(k) for k in request.args})
        await self._callback(topic, request.json)
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


class Subscription:

    def __init__(self, topic, expires_at, callback):
        self.topic = topic
        self.expires_at = expires_at
        self.callback = callback

    def __repr__(self):
        return f"<{self.__class__.__name__} topic='{self.topic.as_uri}' expires_at='{self.expires_at}'' " \
            f"callback='{self.callback}'> "

    @property
    def expires_in(self):
        return (self.expires_at - datetime.now()).total_seconds()

    @classmethod
    def get_subscription(cls, sub):
        topic = Topic.get_topic(sub['topic'])
        expires_at = datetime.strptime(sub['expires_at'], "%Y-%m-%dT%H:%M:%SZ")
        callback = sub['callback']
        return cls(topic, expires_at, callback)


class Topic(abc.ABC):

    __slots__ = ()

    ENDPOINT = None

    def __init__(self, **kwargs):
        self.params = {slot: value for slot, value in kwargs.items() if slot in self.__slots__}

    def __repr__(self):
        return f"<{self.__class__.__name__} uri='{self.as_uri}'>"

    def __str__(self):
        return self.__repr__()

    def __hash__(self):
        return hash(str(self))

    @property
    def as_uri(self):
        return f"{TWITCH_API_URL}{self.ENDPOINT}?{parse.urlencode(self.params)}"

    @classmethod
    def get_topic(cls, url):
        parsed_url = parse.urlparse(url)
        topic_class = next((subclass for subclass in cls.__subclasses__()
                            if f"/helix{subclass.ENDPOINT}" == parsed_url.path), None)
        params = dict(parse.parse_qsl(parsed_url.query))
        return topic_class(**params)

    @property
    def id(self):
        return next((self.params.get(slot) for slot in self.__slots__ if self.params.get(slot) is not None), None)


class StreamChanged(Topic):

    __slots__ = ('user_id',)

    ENDPOINT = "/streams"


class UserFollows(Topic):

    __slots__ = ('from_id', 'to_id')

    ENDPOINT = "/users/follows"
