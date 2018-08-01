import logging
import re

from discord_bot.api import base
from discord_bot import cfg

CONF = cfg.CONF
LOG = logging.getLogger('debug')

LOGICS = ["casual", "standard", "expert", "master", "hard", "ohko", "0xp", "glitched"]
MODES = ["default", "shards", "limitkeys", "clues"]
PATH_DIFFICULTIES = ["easy", "normal", "hard"]
VARIATIONS = ["normal", "speed", "dbash", "extended", "extended-damage", "lure", "speed-lure", "lure-hard", "dboost",
              "dboost-light", "dboost-hard", "cdash", "cdash-farming", "extreme", "timed-level", "glitched"]

PRESETS = {
    "casual": ["normal", "dboost-light"],
    "standard": ["normal", "speed", "lure", "dboost-light"],
    "dboost": ["normal", "speed", "lure", "dboost", "dboost-light"],
    "expert": ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "cdash", "extended",
               "extended-damage"],
    "master": ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "dboost-hard", "cdash", "dbash",
               "extended", "extended-damage", "lure-hard", "extreme"],
    "hard": ["normal", "speed", "lure", "dboost-light", "cdash", "dbash", "extended"],
    "ohko": ["normal", "speed", "lure", "cdash", "dbash", "extended"],
    "0xp": ["normal", "speed", "lure", "dboost-light"],
    "glitched": ["normal", "speed", "lure", "speed-lure", "dboost", "dboost-light", "dboost-hard", "cdash", "dbash",
                 "extended", "lure-hard", "timed-level", "glitched", "extended-damage", "extreme"]
}

DEFAULT_PATHDIFF = "normal"
DEFAULT_GENMODE = "balanced"
DEFAULT_FORCE_TREES = True
DEFAULT_SYNC_TYPE = "split"
DEFAULT_PLAYER_COUNT = 1
DEFAULT_SYNC_ID = ""
DEFAULT_SYNC_MODE = "shared"


class OriRandomizerAPIClient(base.APIClient):

    def __init__(self):
        super(OriRandomizerAPIClient, self).__init__(base_url="http://orirandocoopserver.appspot.com")

    async def get_download_links(self, seed, logic, mode, paths, additional_flags):
        """ Retrieve the seed and spoiler download links

        :param seed: The seed number
        :param logic: The seed logic
        :param mode: The seed mode
        :param paths: The seed path
        :param additional_flags: The additional seed flags
        :return: a tuple of download links
        """

        link_patttern = f"{self.base_url}(\/getseed[&|?=\w-]+)"

        preset_flags = PRESETS[logic]
        flags = set(preset_flags) | set(additional_flags)

        params = {
            "mode": mode,
            "pathdiff": paths[0] if len(paths) == 1 else DEFAULT_PATHDIFF,
            "genmode": DEFAULT_GENMODE,
            "forcetrees": DEFAULT_FORCE_TREES,
            "synctype": DEFAULT_SYNC_TYPE,
            "playerCount": DEFAULT_PLAYER_COUNT,
            "seed": seed,
            "syncid": DEFAULT_SYNC_ID,
            "syncmode": DEFAULT_SYNC_MODE
        }
        params.update({flag: True for flag in flags})
        LOG.debug(f"Parameters used for the seed generation: {params}")

        gen_uri = "/mkseed?" + "&".join(f"{key}={value}" for key, value in params.items())
        result = await (await self.get(gen_uri)).text()

        seed_link = re.search(link_patttern, result).group(1)
        spoiler_link = seed_link + "&splr=1"

        return seed_link, spoiler_link
