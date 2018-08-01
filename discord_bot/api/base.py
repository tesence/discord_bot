import asyncio
import logging

import aiohttp
import aiofiles

from discord_bot import log

LOG = logging.getLogger('debug')


class APIClient:

    def __init__(self, base_url, *args, **kwargs):
        self.base_url = base_url
        self.session = aiohttp.ClientSession(*args, **kwargs)

    async def request(self, method, uri, **kwargs):
        url = self.base_url + uri
        try:
            r = await self.session.request(method, url, **kwargs)
            status_code = r.status
            if status_code == 200:
                return r
            elif 400 < status_code < 500:
                LOG.error(f"Bad request {url} ({status_code})")
            elif 500 <= status_code < 600:
                LOG.error(f"The request didn't succeed {url} ({status_code})")
        except Exception as e:
            if type(e) == asyncio.TimeoutError:
                message = "The timeout has been reached"
            else:
                message = "An error has occured"
            message += f" while requesting the url {url}"

            LOG.error(log.get_log_exception_message(message, e))

    async def get(self, uri):
        return await self.request("get", uri)

    async def download(self, uri, filename):
        content = await (await self.get(uri)).read()
        async with aiofiles.open(filename, "wb") as f:
            await f.write(content)
        return True
