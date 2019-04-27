#!/usr/bin/python

import os
import sys

from gumo import config
from gumo import client
from gumo import utils


def main():

    config.load(os.environ.get('GUMO_CONFIG_FILE'))

    sys.path.append(utils.get_project_name())

    bot = client.Bot()

    bot.loop.create_task(bot.start())
    bot.loop.run_forever()


if __name__ == "__main__":
    main()
