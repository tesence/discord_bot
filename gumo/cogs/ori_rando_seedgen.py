import io
import json
import logging
import random
import os
import re

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from gumo.api import ori_randomizer
from gumo import config
from gumo import cogs
from gumo import utils

LOG = logging.getLogger('bot')

SEED_FILENAME = "randomizer.dat"
SPOILER_FILENAME = "spoiler.txt"
DOWNLOAD_MESSAGES_FILE_PATH = "data/download_messages.json"

GOAL_MODES = utils.MultiKeyDict()
GOAL_MODES['ft', 'forcetrees', 'force-trees'] = "ForceTrees"
GOAL_MODES['wt', 'worldtour', 'world-tour'] = "WorldTour"
GOAL_MODES['wf', 'warmthfragments', 'warmth-fragments'] = "WarmthFrags"
GOAL_MODES['fm', 'forcemapstones', 'force-mapstones'] = "ForceMapStones"

DEFAULT_SEEDGEN_COOLDOWN = 0


class OriRandoSeedGenCommands(cogs.CogMixin):

    def __init__(self, bot):
        super(OriRandoSeedGenCommands, self).__init__(bot)
        type(self).__name__ = "Ori rando commands"
        self.client = ori_randomizer.OriRandomizerAPIClient(self.bot.loop)

    @staticmethod
    def _get_download_message():
        """Get a random message from the list stored in data/download_messages.json

        :return: a random download message
        """
        file_absolute_path = utils.get_project_dir() + "/" + DOWNLOAD_MESSAGES_FILE_PATH
        if os.path.isfile(file_absolute_path):
            try:
                with open(file_absolute_path, "r") as f:
                    download_messages = json.load(f)
                    if download_messages:
                        return random.choice(download_messages)
                    return random.choice(download_messages)
            except json.decoder.JSONDecodeError:
                LOG.exception(f"Cannot load the file '{DOWNLOAD_MESSAGES_FILE_PATH}'")
        return "Downloading the seed"

    @commands.command()
    @commands.cooldown(1, config.get('SEEDGEN_COOLDOWN', DEFAULT_SEEDGEN_COOLDOWN), BucketType.guild)
    async def seed(self, ctx, *, args=""):
        """Generate a seed for the Ori randomizer

        Default: standard, clues, forcetrees, open

        TODO: Write this

        A seed name can be set using double quotes
        """
        channel_repr = utils.get_channel_repr(ctx.channel)
        seed_codes = re.findall('[^"]*(".*")', args)
        LOG.debug(f"Valid seed codes found: {seed_codes}")
        seed = seed_codes[0][1:-1] if seed_codes else str(random.randint(1, 1000000000))

        for seed_code in seed_codes:
            args = args.replace(seed_code, "")
        args = [arg.lower() for arg in args.split()]

        goal_modes = []
        for arg in args:
            token, _, value = arg.partition('=')
            if token in GOAL_MODES:
                token = GOAL_MODES[token]
                if token == "ForceTrees" or token == "ForceMapStones":
                    goal_modes.append((token,))
                elif token == "WorldTour":
                    goal_modes.append((token, value if value.isdigit() else None))
                elif token == "WarmthFrags":
                    frags_req, _, frags = value.partition("/")
                    goal_modes.append((token,
                                       frags_req if frags_req.isdigit() else None,
                                       frags if frags.isdigit() else None))

        def get_matching(target_list):
            matching_vals = [arg for arg in args if arg in target_list]
            return matching_vals

        logic_presets = get_matching(ori_randomizer.LOGIC_MODES)

        # handle the ambiguous cases.
        unambiguous_presets = [preset for preset in logic_presets if preset not in ori_randomizer.AMBIGUOUS_PRESETS]
        if len(logic_presets) != len(unambiguous_presets):
            if unambiguous_presets:
                # take an unambiguous preset over an ambiguous one
                logic_presets = unambiguous_presets
            else:
                # if we don't have an unambiguous preset, remove the one we're going to use so it doesn't get picked
                # up as a variation or logic path.
                args.remove(logic_presets[0])

        key_modes = get_matching(ori_randomizer.KEY_MODES)
        variations = get_matching(ori_randomizer.VARIATIONS)
        logic_paths = get_matching(ori_randomizer.LOGIC_PATHS)
        flags = get_matching(ori_randomizer.FLAGS)

        LOG.debug(f"[{channel_repr}] seeds_codes={seed_codes}, presets={logic_presets}, key_modes={key_modes}, "
                  f"goal_modes={goal_modes}, variations={variations}, paths={logic_paths}, flags={flags}")

        path_diff = None
        if "hard-path" in args:
            path_diff = "Hard"
        elif "easy-path" in args:
            path_diff = "Easy"

        logic_preset = logic_presets[0] if logic_presets else 'standard'
        key_mode = key_modes[0] if key_modes else None

        download_message = await self.bot.send(ctx.channel, f"{self._get_download_message()}...")
        try:
            # Download the seed data
            LOG.debug(f"[{channel_repr}] Downloading the seed data: '{download_message.content}'")
            data = await self.client.get_data(seed, logic_preset, key_mode, path_diff, goal_modes, variations,
                                              logic_paths, flags)

            # Store the data into file buffers
            seed_buffer = io.BytesIO(bytes(data['players'][0]['seed'], encoding="utf8"))
            spoiler_buffer = io.BytesIO(bytes(data['players'][0]['spoiler'], encoding="utf8"))

            # Send the files in the chat
            seed_header = data['players'][0]['seed'].split("\n")[0]
            message = f"Seed requested by **{ctx.author.display_name}**\n"
            message += f"`{seed_header}`\n"
            message += f"**Spoiler link**: {ori_randomizer.SEEDGEN_API_URL + data['players'][0]['spoiler_url']}\n"
            if "tracking" in flags:
                message += f"**Map**: {ori_randomizer.SEEDGEN_API_URL + data['map_url']}\n"
                message += f"**History**: {ori_randomizer.SEEDGEN_API_URL + data['history_url']}\n"

            await download_message.delete()
            await self.bot.send(ctx.channel, message,
                                files=[discord.File(seed_buffer, filename=SEED_FILENAME),
                                       discord.File(spoiler_buffer, filename=SPOILER_FILENAME)])
            LOG.debug(f"[{channel_repr}] The files have correctly been sent in Discord")
        except:
            error_message = "An error has occured while generating the seed"
            LOG.exception(f"[{channel_repr}] {error_message}")
            await download_message.edit(content=f"```{error_message}. Please try again later.```")


def setup(bot):
    bot.add_cog(OriRandoSeedGenCommands(bot))
