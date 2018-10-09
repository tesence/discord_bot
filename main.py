#!/usr/bin/python

import argparse
import sys

from discord_bot import config
from discord_bot import client
from discord_bot import log
from discord_bot import utils

parser = argparse.ArgumentParser("Start the Discord bot")
parser.add_argument('--config-file', '-c', dest='config_file', help="Bot configuration file")
parser.add_argument('--log-dir', '-l', dest='log_dir',
                    default=f"/var/log/{utils.get_project_name()}/", help="Bot log folder")


def main():

    args = parser.parse_args()
    log.setup(args.log_dir, args.config_file)
    config.load(args.config_file)

    sys.path.append(utils.get_project_name())

    bot = client.Bot(command_prefix=config.COMMAND_PREFIX)
    bot.loop.run_until_complete(bot.start(config.DISCORD_BOT_TOKEN))


if __name__ == "__main__":
    main()
