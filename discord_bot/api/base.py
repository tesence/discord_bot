import asyncio
import logging

import aiohttp

LOG = logging.getLogger('bot')


class APIClient:

    def __init__(self, base_url, *args, **kwargs):
        self.base_url = base_url
        self.session = aiohttp.ClientSession(*args, **kwargs)

    async def request(self, method, uri, **kwargs):
        url = self.base_url + uri
        try:
            r = await self.session.request(method, url, **kwargs)
            status_code = r.status
            if 200 <= status_code < 300:
                return r
            elif 400 <= status_code < 500:
                LOG.error(f"Bad request {url} ({status_code})")
            elif 500 <= status_code < 600:
                LOG.error(f"The request didn't succeed {url} ({status_code})")
        except asyncio.TimeoutError:
            LOG.error(f"The timeout has been reached while requesting the url: {url}")
        except aiohttp.ClientError as e:
            LOG.error(f"An error has occurred while requesting the url ({type(e).__name__}): {url}")

    async def get(self, uri):
        return await self.request("get", uri)
