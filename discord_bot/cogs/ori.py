import concurrent.futures
import logging
import os
import random
import re

import aiofiles
import discord
from discord.ext import commands

from discord_bot import cfg
from discord_bot import log
from discord_bot import utils

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

BASE_URL = "http://orirandocoopserver.appspot.com"

SEED_FILENAME = "randomizer.dat"
SPOILER_FILENAME = "spoiler.txt"

CONF = cfg.CONF
LOG = logging.getLogger('debug')


class InvalidLogicError(commands.CommandError):
    """Exception when the seed logic is invalid."""


class InvalidModeError(commands.CommandError):
    """Exception when the game mode is invalid."""


class InvalidFlagError(commands.CommandError):
    """Exception when a flag is invalid."""


class SeedGeneratorError(commands.CommandError):
    """Exception when an error occurred during the seed generation"""


class OriRandoCommands:

    def __init__(self, bot):
        type(self).__name__ = "Ori rando commands"
        self.bot = bot
        self.generating_seed = False
        self.bot.handled_exceptions += [SeedGeneratorError, InvalidModeError, InvalidFlagError, InvalidLogicError]

    async def on_command_error(self, ctx, error):

        if isinstance(error, InvalidLogicError):
            LOG.error(f"Invalid logic: '{error.args[0]}'")
            message = f"Invalid logic: '{error.args[0]}'\n"
            message += f"The valid logics are: {', '.join(LOGICS)}\n\n"
            message += f"!{self.seed.signature}"
            return await self.bot.send(ctx.channel, message, code_block=True)
        elif isinstance(error, InvalidModeError):
            LOG.error(f"Invalid mode: '{error.args[0]}'")
            message = f"Invalid mode: '{error.args[0]}'\n"
            message += f"The valid modes are: {', '.join(MODES)}\n\n"
            message += f"!{self.seed.signature}"
            return await self.bot.send(ctx.channel, message, code_block=True)
        elif isinstance(error, InvalidFlagError):
            LOG.error(f"Invalid flags: {', '.join(error.args)}'")
            message = f"Invalid flags: '{', '.join(error.args)}'\n"
            message += f"The valid flags are: {', '.join(VARIATIONS)}\n\n"
            message += f"!{self.seed.signature}"
            return await self.bot.send(ctx.channel, message, code_block=True)

    async def _get_download_links(self, seed, logic, mode, paths, additional_flags):
        """ Retrieve the seed and spoiler download links

        :param seed: The seed number
        :param logic: The seed logic
        :param mode: The seed mode
        :param paths: The seed path
        :param additional_flags: The additional seed flags
        :return: a tuple of download links
        """

        link_patttern = f"({BASE_URL}\/getseed[&|?=\w-]+)"

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

        gen_url = BASE_URL + "/mkseed?" + "&".join(f"{key}={value}" for key, value in params.items())
        result = await utils.request(gen_url, json=False)

        seed_link = re.search(link_patttern, result).group(1)
        spoiler_link = seed_link + "&splr=1"

        return seed_link, spoiler_link

    async def _get_flags(self, filename):
        """ Get the first line of the seed file

        :param filename: the name of seed file
        :return: The first line of the seed file as a string
        """
        async with aiofiles.open(filename) as f:
            return await f.readline()

    @commands.command()
    async def seed(self, ctx, logic, mode, *additional_flags):
        """Generate a seed for the Ori randomizer

        Valid logics: casual, standard, expert, master, hard, ohko, 0xp, glitched
        Valid modes: shards, limitkeys, clues
        Valid flags: easy-path, normal-path, hard-path, normal, speed, dbash, extended, extended-damage, lure,
                     speed-lure, lure-hard, dboost, dboost-light, dboost-hard, cdash, cdash-farming, extreme,
                     timed-level, glitched
        """
        path_pattern = "(\w+)\-path"

        if self.generating_seed:
            LOG.warning("A seed is already being generated")
        else:

            additional_flags = list(additional_flags)
            paths = []
            for flag in additional_flags:
                if re.match(path_pattern, flag):
                    paths.append(re.match(path_pattern, flag).group(1))
                    additional_flags.remove(flag)

            LOG.debug(f"Seed parameters: logic='{logic}' mode='{mode}' paths={paths} "
                      f"additional_flags={list(additional_flags)}")

            if logic not in PRESETS:
                raise InvalidLogicError(logic)

            if mode not in MODES:
                raise InvalidModeError(mode)

            invalid_flags = set(additional_flags) - set(VARIATIONS)
            if invalid_flags:
                raise InvalidFlagError(*invalid_flags)

            download_message = await ctx.send("Downloading the seed...")
            try:
                self.generating_seed = True

                # Limit the executor to 1 worker to make everything sequential
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                seed = random.randint(1, 1000000000)

                seed_link, spoiler_link = await self._get_download_links(seed, logic, mode, paths, additional_flags)
                seed_filepath = f"{seed}/{SEED_FILENAME}"
                spoiler_filepath = f"{seed}/{SPOILER_FILENAME}"

                # Create a temporary subfolder to avoid name conflict
                self.bot.loop.run_in_executor(executor, os.makedirs, str(seed))

                # Download the files
                await utils.download_file(seed_link, seed_filepath)
                await utils.download_file(spoiler_link, spoiler_filepath)

                # Send the files in the chat
                await download_message.delete()
                seed_header = await self._get_flags(seed_filepath)
                await ctx.send(content=seed_header, files=[discord.File(seed_filepath), discord.File(spoiler_filepath)])

                # Delete everything once it's sent
                self.bot.loop.run_in_executor(executor, os.remove, seed_filepath)
                self.bot.loop.run_in_executor(executor, os.remove, spoiler_filepath)
                self.bot.loop.run_in_executor(executor, os.rmdir, str(seed))

                self.generating_seed = False

            except Exception as e:
                self.generating_seed = False
                error_message = "An error has occured while generating the seed"
                LOG.exception(log.get_log_exception_message(error_message, e))
                await self.bot.send(ctx.channel, f"{error_message}. Please try again later.", code_block=True)
                raise SeedGeneratorError


def setup(bot):
    dab_commands = OriRandoCommands(bot)
    bot.add_cog(dab_commands)
