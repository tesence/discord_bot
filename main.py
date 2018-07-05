#!/usr/bin/python

import sys

from discord_bot import cfg
from discord_bot import client
from discord_bot import log

CONF = cfg.CONF


def main():
    sys.path.append('discord_bot')

    bot = client.Bot(command_prefix=CONF.COMMAND_PREFIX)
    bot.loop.run_until_complete(bot.start(CONF.DISCORD_BOT_TOKEN))


if __name__ == "__main__":
    CONF.load(sys.argv[1])
    log.setup()
    main()
