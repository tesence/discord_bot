#!/usr/bin/python

import argparse
import sys

from gumo import config
from gumo import client
from gumo import log
from gumo import utils

parser = argparse.ArgumentParser("Start the Discord bot")
parser.add_argument('--config-dir', '-c', dest='config_folder', help="Bot configuration folder")
parser.add_argument('--log-dir', '-l', dest='log_dir',
                    default=f"/var/log/{utils.get_project_name()}/", help="Bot log folder")


def main():

    args = parser.parse_args()
    log.setup(args.log_dir, args.config_folder)
    config.load(args.config_folder)

    sys.path.append(utils.get_project_name())

    bot = client.Bot(command_prefix=config.get('COMMAND_PREFIX'))
    bot.loop.run_until_complete(bot.start(config.get('DISCORD_BOT_TOKEN')))


if __name__ == "__main__":
    main()
