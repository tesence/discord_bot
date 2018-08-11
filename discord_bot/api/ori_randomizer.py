import logging

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


class OriRandomizerAPIClient(base.APIClient):

    def __init__(self):
        super(OriRandomizerAPIClient, self).__init__(base_url=CONF.SEEDGEN_API_URL)

    async def get_data(self, seed, logic, key_mode=None, path_diff=None, additional_flags=None):
        """ Retrieve the seed and spoiler download links

        :param seed: The seed number
        :param logic: The seed logic
        :param key_mode: The seed mode
        :param path_diff: The seed path
        :param additional_flags: The additional seed flags
        :return: seed and spoiler data
        """

        logic_paths = PRESETS[logic]
        logic_paths = set(logic_paths) | set(additional_flags or [])

        params = {("seed", seed), ('tracking', 'Disabled'), ('var', 'ForceTrees')}
        if key_mode:
            params.add(("key_mode", key_mode.capitalize()))

        if path_diff:
            params.add(("path_diff", path_diff.capitalize()))

        params = params | {("path", path) for path in logic_paths}
        LOG.debug(f"Parameters used for the seed generation: {params}")

        url = "/generator/json?" + "&".join([f"{param[0]}={param[1]}" for param in params])
        return await (await self.get(url)).json()
