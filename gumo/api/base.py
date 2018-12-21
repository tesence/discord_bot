import logging

import aiohttp

LOG = logging.getLogger('bot')


ERROR_MESSAGE = "API error while requesting the endpoint"


class APIClient:

    def __init__(self, base_url, warning_exceptions=(), error_exceptions=(), *args, **kwargs):
        self.base_url = base_url
        self.session = aiohttp.ClientSession(*args, **kwargs)
        self.warning_exceptions = warning_exceptions
        self.error_exceptions = error_exceptions

    async def request(self, method, uri, **kwargs):
        url = self.base_url + uri
        endpoint = uri.split('?')[0]
        try:
            r = await self.session.request(method, url, **kwargs)
            status_code = r.status
            if 200 <= status_code < 300:
                return await r.json()
            elif 400 <= status_code < 500:
                LOG.error(f"API Client error {url} ({status_code})")
            elif 500 <= status_code < 600:
                LOG.warning(f"API Server error {url} ({status_code})")
        except self.warning_exceptions:
            pass
        except self.error_exceptions as e:
            LOG.exception(f"{ERROR_MESSAGE} '{endpoint}' ({type(e).__name__})")
        except aiohttp.ClientError:
            LOG.exception(f"Unexpected API error")

    async def get(self, uri):
        return await self.request("get", uri)
