import asyncio
import concurrent.futures
import logging
import os
import random
import re

import aiofiles
import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from discord_bot.api import ori_randomizer
from discord_bot import cfg
from discord_bot import utils

CONF = cfg.CONF
LOG = logging.getLogger('debug')

SEED_FILENAME = "randomizer.dat"
SPOILER_FILENAME = "spoiler.txt"


class OriRandoSeedGenCommands:

    def __init__(self, bot):
        type(self).__name__ = "Ori rando commands"
        self.bot = bot
        self.client = ori_randomizer.OriRandomizerAPIClient()

    async def _get_flags(self, filename):
        """ Get the first line of the seed file

        :param filename: the name of seed file
        :return: The first line of the seed file as a string
        """
        async with aiofiles.open(filename) as f:
            return await f.readline()

    @commands.command()
    @commands.cooldown(1, CONF.SEEDGEN_COOLDOWN, BucketType.guild)
    async def seed(self, ctx, *args):
        """Generate a seed for the Ori randomizer

        Valid logics: casual, standard, expert, master, hard, ohko, 0xp, glitched
        Valid modes: shards, limitkeys, clues, default
        Valid flags: easy-path, normal-path, hard-path, normal, speed, dbash, extended, extended-damage, lure,
                     speed-lure, lure-hard, dboost, dboost-light, dboost-hard, cdash, cdash-farming, extreme,
                     timed-level, glitched
        """
        author_name = ctx.author.nick or ctx.author.name
        LOG.debug(f"Seed requested by {author_name}: '{ctx.message.content}'")

        valid_seed_codes = re.findall('[^"]*"(.*)"', ctx.message.content)
        LOG.debug(f"Valid seed codes found: {valid_seed_codes}")
        seed = valid_seed_codes[0] if valid_seed_codes else str(random.randint(1, 1000000000))

        args = [arg.lower() for arg in args]
        valid_logics = [logic for logic in args if logic in ori_randomizer.LOGICS]
        LOG.debug(f"Valid logic presets found: {valid_logics}")

        valid_modes = [mode for mode in args if mode in ori_randomizer.MODES]
        LOG.debug(f"Valid modes found: {valid_modes}")

        valid_path_diffs = [path for path in args if path
                            in [f"{path_diff}-path" for path_diff in ori_randomizer.PATH_DIFFICULTIES]]
        valid_path_diffs = [valid_path_diff[:-5] for valid_path_diff in valid_path_diffs]
        LOG.debug(f"Valid path difficulties found: {valid_path_diffs}")

        valid_variations = [variation for variation in args if variation in ori_randomizer.VARIATIONS]
        LOG.debug(f"Valid variations found: {valid_variations}")

        logic = valid_logics[0] if valid_logics else 'standard'
        mode = valid_modes[0] if valid_modes else None
        path_diff = valid_path_diffs[0] if valid_path_diffs else None

        download_message = await self.bot.send(ctx.channel, "Downloading the seed...")
        try:

            # Limit the executor to 1 worker to make everything sequential
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            # Download the seed data
            LOG.debug("Downloading the seed data...")
            data = await self.client.get_data(seed=seed, logic=logic, key_mode=mode, path_diff=path_diff,
                                              additional_flags=valid_variations)

            # Create a temporary subfolder to avoid any name conflict
            LOG.debug("Creating the subfolder...")
            self.bot.loop.run_in_executor(executor, os.makedirs, seed)

            seed_path = f"{seed}/{SEED_FILENAME}"
            spoiler_path = f"{seed}/{SPOILER_FILENAME}"

            LOG.debug(f"Creating '{seed_path}' and '{spoiler_path}'...")
            file_futures = {
                utils.write_file(seed_path, data['players'][0]['seed']),
                utils.write_file(spoiler_path, data['players'][0]['spoiler'])
            }
            await asyncio.gather(*file_futures, loop=self.bot.loop)

            # Send the files in the chat
            LOG.debug("Sending the files in Discord...")
            seed_header = await self._get_flags(seed_path)
            message = f"Seed requested by **{author_name}**\n" \
                      f"`{seed_header}`"

            await download_message.delete()
            await self.bot.send(ctx.channel, message,
                                files=[discord.File(seed_path), discord.File(spoiler_path)])
            LOG.debug(f"The files have correctly been sent in Discord")

            # Delete everything once it's sent
            self.bot.loop.run_in_executor(executor, os.remove, seed_path)
            self.bot.loop.run_in_executor(executor, os.remove, spoiler_path)
            self.bot.loop.run_in_executor(executor, os.rmdir, seed)
            LOG.debug(f"Cleanup successful")

        except:
            error_message = "An error has occured while generating the seed"
            LOG.exception(error_message)
            await download_message.edit(content=f"```{error_message}. Please try again later.```")


def setup(bot):
    ori_rando_seedgen_commands = OriRandoSeedGenCommands(bot)
    bot.add_cog(ori_rando_seedgen_commands)
