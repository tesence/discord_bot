import collections
import json
import logging
import os

import aiohttp

LOG = logging.getLogger('debug')


def get_project_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def get_project_name():
    return os.path.basename(os.path.dirname(__file__))


def get_file_path(filename):
    return "{project_dir}/{filename}".format(project_dir=get_project_dir(), filename=filename)


def save_file(filepath, data):
    with open(filepath, mode='w+', encoding="utf-8") as fs:
        fs.write(data)
        LOG.debug("Updating %s data: %s", filepath, str(data))


def save_json_file(filepath, data):
    with open(filepath, mode='w+', encoding="utf-8") as fs:
        json.dump(collections.OrderedDict(data), fs, indent=2)
        LOG.debug("Updating %s data: %s", filepath, str(data))


def load_file(filepath):
    with open(filepath, mode='r', encoding="utf-8") as fs:
        try:
            data = fs.read()
            LOG.debug("%s loaded: %s", filepath, data.replace("\n", ""))
            return data
        except FileNotFoundError:
            LOG.exception("Cannot load the file: %s", filepath)


def load_json_file(filename):
    if filename.split(".").pop() == "json":
        content = load_file(filename)
        if content:
            try:
                return json.loads(content)
            except (TypeError, ValueError):
                LOG.exception("Cannot load the json file: {filename}".format(filename=filename))
    else:
        LOG.error("'%s' is not a json file", filename)


async def request(url, headers):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            status_code = resp.status
            response = await resp.json()
            return response, status_code


def ordinal(num):
    num = int(num)
    SUFFIXES = {1: 'st', 2: 'nd', 3: 'rd'}
    if 10 <= num % 100 <= 20:
        suffix = 'th'
    else:
        # the second parameter is a default.
        suffix = SUFFIXES.get(num % 10, 'th')
    return str(num) + suffix


def convert_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%d:%02d:%02d" % (h, m, s)


def underline(message):
    return "__" + str(message) + "__"


def bold(message):
    return "**" + str(message) + "**"
