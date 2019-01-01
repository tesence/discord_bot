import asyncio
from datetime import datetime, timedelta
import logging
import math

import aiohttp

LOG = logging.getLogger('bot')


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


class APIClient:

    def __init__(self, warning_exceptions=(), error_exceptions=(), bucket=None, *args, **kwargs):
        self._session = aiohttp.ClientSession(*args, **kwargs)
        self._warning_exceptions = warning_exceptions
        self._error_exceptions = error_exceptions
        self._bucket = bucket

    async def request(self, method, url, return_json=False, **kwargs):
        if self._bucket:
            await self._bucket.consume()

        endpoint = url.split('?')[0]
        try:
            r = await self._session.request(method, url, **kwargs)
            status_code = r.status
            if 200 <= status_code < 300:
                return await r.json() if return_json else await r.text()
            elif 400 <= status_code < 500:
                LOG.error(f"API Client error {url} ({status_code})")
            elif 500 <= status_code < 600:
                LOG.warning(f"API Server error {url} ({status_code})")
        except self._warning_exceptions:
            pass
        except self._error_exceptions as e:
            LOG.exception(f"API error while requesting the endpoint '{endpoint}' ({type(e).__name__})")
        except aiohttp.ClientError:
            LOG.exception(f"Unexpected API error")

    async def get(self, uri, return_json=False, **kwargs):
        return await self.request("get", uri, return_json=return_json, **kwargs)

    async def post(self, uri, data=None, return_json=False, **kwargs):
        return await self.request("post", uri, return_json=return_json, json=data, **kwargs)
