import asyncio
from datetime import datetime, timedelta
import logging
import math

import aiohttp

LOG = logging.getLogger(__name__)


class RateBucket:

    def __init__(self, rate, per=60):
        self._tokens = rate
        self._rate = rate
        self._per = per
        self._reset_date = None

    async def consume(self):
        self._reset_date = self._reset_date or datetime.utcnow() + timedelta(seconds=self._per)

        if self._tokens > 0:
            self._tokens -= 1
        else:
            await self._reset()

    async def _reset(self):
        wait = math.ceil((self._reset_date - datetime.utcnow()).total_seconds())
        if wait > 0:
            await asyncio.sleep(wait)
        self._tokens = self._rate
        self._reset_date = None
        await self.consume()


class APIError(Exception):

    def __init__(self, message, original=None):
        self.message = message
        if original:
            self.message += f" - {original.message} ({original.status})"
        super().__init__(self.message)


class APIClientError(APIError):

    def __init__(self, original):
        message = "Invalid Request"
        super().__init__(message, original)


class APIServerError(APIError):

    def __init__(self, original):
        message = "Server Error"
        super().__init__(message, original)


class APIClient:

    def __init__(self, bucket=None, *args, **kwargs):
        self._session = aiohttp.ClientSession(*args, **kwargs, raise_for_status=True)
        self._bucket = bucket

    async def request(self, method, url, return_json=False, **kwargs):

        LOG.debug(f"Outgoing request: {method.upper()} {url} (params={kwargs})")
        if self._bucket:
            await self._bucket.consume()

        try:
            r = await self._session.request(method, url, **kwargs)
            return await r.json() if return_json else await r.text()
        except aiohttp.ClientResponseError as error:
            if 400 <= error.status < 500:
                output_error = APIClientError(error)
                LOG.error(output_error.message)
                raise output_error
            elif 500 <= error.status < 600:
                output_error = APIServerError(error)
                LOG.error(output_error.message)
                raise output_error
        except aiohttp.ClientError as error:
            output_error = APIError(str(error))
            LOG.error(output_error.message)
            raise output_error

    async def get(self, uri, return_json=False, **kwargs):
        return await self.request("get", uri, return_json=return_json, **kwargs)

    async def post(self, uri, data=None, return_json=False, **kwargs):
        return await self.request("post", uri, return_json=return_json, json=data, **kwargs)
