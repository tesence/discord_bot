#!/usr/bin/python


import asyncio
import sys

import cfg
from discord_bot import client
from discord_bot import log


def main():
    sys.path.append('discord_bot')

    bot = client.Bot(command_prefix=cfg.COMMAND_PREFIX)

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(coro_or_future=bot.start(cfg.DISCORD_BOT_TOKEN),
                          loop=loop)
    loop.run_forever()


if __name__ == "__main__":
    log.setup()
    main()
