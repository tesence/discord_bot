import logging

from gumo.api import base

LOG = logging.getLogger(__name__)

SEEDGEN_API_URL = "https://orirando.com"

LOGIC_MODES = ["casual", "standard", "expert", "master", "glitched"]
KEY_MODES = ["default", "shards", "limitkeys", "clues", "free"]

PATH_DIFFICULTIES = ["easy", "normal", "hard"]

LOGIC_PATHS = [
    "casual-core", "casual-dboost",
    "standard-core", "standard-dboost", "standard-lure", "standard-abilities",
    "expert-core", "expert-dboost", "expert-lure", "expert-abilities",
    "master-core", "master-dboost", "master-lure", "master-abilities",
    "dbash", "gjump", "glitched", "timed-level", "insane"
]

# map of lowercase variation to correctly capitalized one.
VARIATIONS = {v.lower(): v for v in ["Starved", "Hard", "OHKO", "0XP", "ClosedDungeons", "OpenWorld", "DoubleSkills",
                                     "StrictMapstones", "BonusPickups", "NonProgressMapStones"]}

FLAGS = ["tracking", "classic_gen", "verbose_paths"]
HARD_PRESETS = ["master", "glitched"]
PRESET_VARS = {"master": ["starved"]}

PRESETS = {}
PRESETS['casual'] = ["casual-core", "casual-dboost"]
PRESETS['standard'] = PRESETS['casual'] + ["standard-core", "standard-dboost", "standard-lure", "standard-abilities"]
PRESETS['expert'] = PRESETS['standard'] + ["expert-core", "expert-dboost", "expert-lure", "expert-abilities", "dbash"]
PRESETS['master'] = PRESETS['expert'] + ["master-core", "master-dboost", "master-lure", "master-abilities", "gjump"]
PRESETS['glitched'] = PRESETS['expert'] + ["glitched", "timed-level"]

AMBIGUOUS_PRESETS = ["glitched"]


class OriRandomizerAPIClient(base.APIClient):

    def __init__(self, loop):
        super(OriRandomizerAPIClient, self).__init__(loop=loop)

    async def get_data(self, seed, preset, key_mode=None, path_diff=None, goal_modes=(), variations=(), logic_paths=(),
                       flags=()):
        """ Retrieve the seed and spoiler download links

        :param seed: The seed number
        :param preset: The seed logic mode preset
        :param key_mode: The seed mode
        :param path_diff: The seed path difficulty
        :param goal_modes: The goal modes
        :param variations: An optional list of variations
        :param logic_paths: An optional list of additional logic paths
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

        for goal_mode in goal_modes:
            if goal_mode[0] == "WorldTour":
                params.add(("var", goal_mode[0]))
                if goal_mode[1]:
                    params.add(("relics", goal_mode[1]))
            elif goal_mode[0] == "WarmthFrags":
                params.add(("var", goal_mode[0]))
                if goal_mode[1]:
                    params.add(("frags_req", goal_mode[1]))
                if goal_mode[2]:
                    params.add(("frags", goal_mode[2]))
            else:
                params.add(("var", goal_mode[0]))

        if not goal_modes:
            params.add(("var", "ForceTrees"))

        if path_diff:
            params.add(("path_diff", path_diff.capitalize()))
        elif preset in HARD_PRESETS:
            params.add(("path_diff", "Hard"))

        logic_paths = set(PRESETS[preset]) | set(logic_paths)
        params = params | {("path", path) for path in logic_paths}

        if preset in PRESET_VARS:
            variations = set(variations) | set(PRESET_VARS[preset])
        params = params | {("var", VARIATIONS[v]) for v in variations}

        if preset == 'casual':
            params.add(('cell_freq', 20))
        elif preset == 'standard':
            params.add(('cell_freq', 40))

        LOG.debug(f"Parameters used for the seed generation: {params}")

        uri = "/generator/json?" + "&".join([f"{key}={value}" for key, value in params])
        return await self.get(f"{SEEDGEN_API_URL}/{uri}", return_json=True)
