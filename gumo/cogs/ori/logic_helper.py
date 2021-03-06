import logging
from collections import defaultdict

from discord.ext import commands

from gumo.api import ori_randomizer

LOG = logging.getLogger(__name__)

SKILLS = {
    'ba': "SK|0", 'bash': "SK|0",
    'cf': "SK|2", 'chargeflame': "SK|2",
    'wj': "SK|3", 'walljump': "SK|3",
    'st': "SK|4", 'stomp': "SK|4",
    'dj': "SK|5", 'doublejump': "SK|5",
    'cj': "SK|8", 'chargejump': "SK|8",
    'cl': "SK|12", 'climb': "SK|12",
    'gl': "SK|14", 'glide': "SK|14",
    'da': "SK|50", 'dash': "SK|50",
    'gr': "SK|51", 'grenade': "SK|51"
}
EVENTS = {
    'watervein': "EV|0", 'wv': "EV|0",
    'water': "EV|1",     'cleanwater': "EV|1",
    'gumonseal': "EV|2", 'gs': "EV|2",
    'wind': "EV|3",      'windrestored': "EV|3",
    'sunstone': "EV|4",  'ss': "EV|4",
}
CELLS_STONES = {
    'health': "HC", 'hc': "HC",
    'energy': "EC", 'ec': "EC",
    'keystone': "KS", 'ks': "KS",
    'mapstone': "MS", 'ms': "MS",
}
TP_NAMES = ["swamp", "grove", "valley", "grotto", "forlorn", "sorrow"]
PRESETS = ["casual", "standard", "expert", "master", "glitched"]


class OriLogicHelperCommands(commands.Cog):

    def __init__(self, bot):
        self.display_name = "Ori rando"
        self.bot = bot

    @commands.command(usage="logic <preset> [list of items]")
    @commands.guild_only()
    async def logic(self, ctx, *args):
        """Links a logic helper map using the supplied parameters

        Default: `standard` (no items)

        - **presets**: `casual`, `standard`, `expert`, `master`, `glitched`

        - **items**: `WallJump`, `ChargeFlame`, `DoubleJump`, `Bash`, `Stomp`, `Glide`, `Climb`, `ChargeJump`, `Dash`, `Grenade`, `WaterVein`, `GumonSeal`, `SS` (Sunstone), `HC` (Health), `EC` (Energy), `KS` (Keystone), `MS` (Mapstone), `Water`, `Wind`, `GrottoTP`, `GroveTP`, `SwampTP`, `ValleyTP`, `SorrowTP`, `ForlornTP`

        *Denote multiples by appending "xN" to it, without a space.*

        **Examples**:
            standard logic, 2 Keystones, 1 Mapstone, ChargeJump: `!logic CJ KSx2 Mapstone`
            expert logic, Bash, Grenade, 4 Energy: `!logic expert Bash Grenade Energyx4`
        """
        args = [arg.lower() for arg in args]

        preset = "standard"
        skills = set()
        events = set()
        tps = set()
        cells_stones = defaultdict(lambda: 0)

        for arg in args:
            if arg in PRESETS:
                if preset != "standard":
                    LOG.debug(f"Got multiple presets. Using the latest {arg}")
                preset = arg
                continue
            if 'x' in arg:
                name, _, cnt = arg.partition('x')
                try:
                    cnt = int(cnt)
                except ValueError:
                    LOG.debug(f"Failed to get count from {arg}, will attempt to continue assuming "
                              f"there's only 1...")
                    cnt = 1
            else:
                name = arg
                cnt = 1
            if name in SKILLS:
                skills.add(SKILLS[name])
                LOG.debug(f"Recognized {name} as {SKILLS[name]}")
                continue
            elif name in EVENTS:
                events.add(EVENTS[name])
                LOG.debug(f"Recognized {name} as {EVENTS[name]}")
                continue
            elif name in CELLS_STONES:
                cells_stones[CELLS_STONES[name]] += cnt
                LOG.debug(f"Recognized {name} as {CELLS_STONES[name]}")
                continue
            elif "tp" in name:
                trimmed = name.replace("tp", "")
                if trimmed in TP_NAMES:
                    tps.add("TP|"+trimmed.capitalize())
                    LOG.debug(f"Recognized Teleporter {name}")
                    continue
                else:
                    LOG.error(f"Unrecognized Teleporter {name}")
                    continue
            else:
                LOG.error(f"Unrecognized pickup {name}")

        base_url = f"{ori_randomizer.SEEDGEN_API_URL}/logichelper?"
        args = [f"pathmode={preset}"]
        for item, cnt in cells_stones.items():
            args.append(f"{item}={cnt}")
        if skills:
            args.append(f"skills={'+'.join(skills)}")
        if tps:
            args.append(f"tps={'+'.join(tps)}")
        if events:
            args.append(f"evs={'+'.join(events)}")

        url = base_url + "&".join(args)

        LOG.debug(f"Finished parsing. final url: {url}")

        await ctx.send(f"Logic Helper Link: {url}")
        LOG.debug(f"Sent URL to discord")


def setup(bot):
    bot.add_cog(OriLogicHelperCommands(bot))
