import io
import logging
import random
import re

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from discord_bot.api import ori_randomizer
from discord_bot import cfg
from discord_bot.cogs import base

CONF = cfg.CONF
LOG = logging.getLogger('debug')

CONF_VARIABLES = ['SEEDGEN_API_URL', 'SEEDGEN_COOLDOWN']

SEED_FILENAME = "randomizer.dat"
SPOILER_FILENAME = "spoiler.txt"


class OriRandoSeedGenCommands(base.CogMixin):

    def __init__(self, bot):
        super(OriRandoSeedGenCommands, self).__init__(bot, CONF_VARIABLES)
        type(self).__name__ = "Ori rando commands"
        self.client = ori_randomizer.OriRandomizerAPIClient()

    @commands.command()
    @commands.cooldown(1, CONF.SEEDGEN_COOLDOWN, BucketType.guild)
    async def seed(self, ctx, *args):
        """Generate a seed for the Ori randomizer

        Default: standard, clues, forcetrees

        - presets: casual, standard, expert, master, hard, ohko, 0xp, glitched

        - modes: shards, limitkeys, clues, default

        - logic paths: normal, speed, dbash, extended, extended-damage, lure, speed-lure, lure-hard, dboost, dboost-light, dboost-hard, cdash, cdash-farming, extreme, timed-level, glitched

        - variations: forcetrees, entrance, hard, starved, ohko, nonprogressmapstones, 0xp, noplants, noteleporters

        - flags: tracking, verbose_paths, classic_gen, hard-path, easy-path
        """

        author_name = ctx.author.nick or ctx.author.name
        LOG.debug(f"Seed requested by {author_name}: '{ctx.message.content}'")

        seed_codes = re.findall('[^"]*"(.*)"', ctx.message.content)
        LOG.debug(f"Valid seed codes found: {seed_codes}")
        seed = seed_codes[0] if seed_codes else str(random.randint(1, 1000000000))

        args = [arg.lower() for arg in args]

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

        LOG.debug(f"seeds_codes={seed_codes}, presets={logic_presets}, key_modes={key_modes}, variations={variations}, "
                  f"paths={logic_paths}, flags={flags}")

        variations = variations or ["forcetrees"]

        path_diff = None
        if "hard-path" in args:
            path_diff = "Hard"
        elif "easy-path" in args:
            path_diff = "Easy"

        logic_preset = logic_presets[0] if logic_presets else 'standard'
        key_mode = key_modes[0] if key_modes else None

        download_message = await self.bot.send(ctx.channel, "Downloading the seed...")
        try:
            # Download the seed data
            LOG.debug("Downloading the seed data...")
            data = await self.client.get_data(seed, logic_preset, key_mode, path_diff, variations, logic_paths, flags)

            # Store the data into file buffers
            seed_buffer = io.BytesIO(bytes(data['players'][0]['seed'], encoding="utf8"))
            spoiler_buffer = io.BytesIO(bytes(data['players'][0]['spoiler'], encoding="utf8"))

            # Send the files in the chat
            LOG.debug("Sending the files in Discord...")
            seed_header = data['players'][0]['seed'].split("\n")[0]
            message = f"Seed requested by **{author_name}**\n" \

            if "tracking" in flags:
                message += f"**Map**: {CONF.SEEDGEN_API_URL + data['map_url']}\n"
                message += f"**History**: {CONF.SEEDGEN_API_URL + data['history_url']}\n"

            message += f"`{seed_header}`"

            await download_message.delete()
            await self.bot.send(ctx.channel, message,
                                files=[discord.File(seed_buffer, filename=SEED_FILENAME),
                                       discord.File(spoiler_buffer, filename=SPOILER_FILENAME)])
            LOG.debug(f"The files have correctly been sent in Discord")
        except:
            error_message = "An error has occured while generating the seed"
            LOG.exception(error_message)
            await download_message.edit(content=f"```{error_message}. Please try again later.```")


def setup(bot):
    bot.add_cog(OriRandoSeedGenCommands(bot))
