import logging

from discord_bot.api import base
from discord_bot import cfg

CONF = cfg.CONF
LOG = logging.getLogger('debug')

LOGIC_MODES = ["casual", "standard", "expert", "master", "hard", "ohko", "0xp", "glitched"]
KEY_MODES = ["default", "shards", "limitkeys", "clues"]
PATH_DIFFICULTIES = ["easy", "normal", "hard"]
LOGIC_PATHS = ["normal", "speed", "dbash", "extended", "extended-damage", "lure", "speed-lure", "lure-hard", "dboost",
               "dboost-light", "dboost-hard", "cdash", "cdash-farming", "extreme", "timed-level", "glitched"]

# map of lowercase variation to correctly capitalized one.
VARIATIONS = {v.lower(): v for v in ["0XP", "NonProgressMapStones", "Entrance", "ForceMapStones",
                                     "ForceRandomEscape", "ForceTrees", "Hard", "NoPlants", "NoTeleporters", "OHKO",
                                     "Starved", "BonusPickups"]}

FLAGS = ["tracking", "classic_gen", "verbose_paths"]

HARD_PRESETS = ["master", "glitched"]

PRESET_VARS = {"master": ["starved"], "hard": ["hard"], "ohko": ["ohko", "hard"], "0xp": ["hard", "0xp"]}

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
AMBIGUOUS_PRESETS = ["hard", "glitched", "ohko", "0xp"]


class OriRandomizerAPIClient(base.APIClient):

    def __init__(self):
        super(OriRandomizerAPIClient, self).__init__(base_url=CONF.SEEDGEN_API_URL)

    async def get_data(self, seed, preset, key_mode=None, path_diff=None, variations=[], logic_paths=[], flags=[]):
        """ Retrieve the seed and spoiler download links

        :param seed: The seed number
        :param preset: The seed logic mode preset
        :param key_mode: The seed mode
        :param path_diff: The seed path difficulty
        :param variations: An optional list of variations
        :param logic_paths: An optional list of addtional logic paths
        :param flags: Any other flags
        :return: seed and spoiler data
        """

        params = {("seed", seed)}

        if "tracking" not in flags:
            params.add(("tracking", "Disabled"))

        if "verbose_paths" in flags:
            params.add(("verbose_paths", "on"))

        if "classic_gen" in flags:
            params.add(("gen_mode", "Classic"))

        if key_mode:
            params.add(("key_mode", key_mode.capitalize()))

        if path_diff:
            params.add(("path_diff", path_diff.capitalize()))
        elif preset in HARD_PRESETS:
            params.add(("path_diff", "Hard"))

        logic_paths = set(PRESETS[preset] + logic_paths)
        params = params | {("path", path) for path in logic_paths}

        if preset in PRESET_VARS:
            variations = set(variations + PRESET_VARS[preset])
        params = params | {("var", VARIATIONS[v]) for v in variations}

        LOG.debug(f"Parameters used for the seed generation: {params}")

        url = "/generator/json?" + "&".join([f"{param[0]}={param[1]}" for param in params])
        return await (await self.get(url)).json()
