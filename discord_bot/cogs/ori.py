import asyncio
import concurrent.futures
import logging
import os
import random
import re

import aiofiles
import discord
from discord.ext import commands

from discord_bot.api import ori_randomizer
from discord_bot import cfg
from discord_bot import log

CONF = cfg.CONF
LOG = logging.getLogger('debug')

SEED_FILENAME = "randomizer.dat"
SPOILER_FILENAME = "spoiler.txt"


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
        self.client = ori_randomizer.OriRandomizerAPIClient()
        self.generating_seed = False
        self.bot.handled_exceptions += [SeedGeneratorError, InvalidModeError, InvalidFlagError, InvalidLogicError]

    async def on_command_error(self, ctx, error):

        if isinstance(error, InvalidLogicError):
            LOG.error(f"Invalid logic: '{error.args[0]}'")
            message = f"Invalid logic: '{error.args[0]}'\n"
            message += f"The valid logics are: {', '.join(ori_randomizer.LOGICS)}\n\n"
            message += f"!{self.seed.signature}"
            return await self.bot.send(ctx.channel, message, code_block=True)
        elif isinstance(error, InvalidModeError):
            LOG.error(f"Invalid mode: '{error.args[0]}'")
            message = f"Invalid mode: '{error.args[0]}'\n"
            message += f"The valid modes are: {', '.join(ori_randomizer.MODES)}\n\n"
            message += f"!{self.seed.signature}"
            return await self.bot.send(ctx.channel, message, code_block=True)
        elif isinstance(error, InvalidFlagError):
            LOG.error(f"Invalid flags: {', '.join(error.args)}'")
            message = f"Invalid flags: '{', '.join(error.args)}'\n"
            message += f"The valid flags are: {', '.join(ori_randomizer.VARIATIONS)}\n\n"
            message += f"!{self.seed.signature}"
            return await self.bot.send(ctx.channel, message, code_block=True)

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

            if logic not in ori_randomizer.PRESETS:
                raise InvalidLogicError(logic)

            if mode not in ori_randomizer.MODES:
                raise InvalidModeError(mode)

            invalid_flags = set(additional_flags) - set(ori_randomizer.VARIATIONS)
            if invalid_flags:
                raise InvalidFlagError(*invalid_flags)

            download_message = await self.bot.send(ctx.channel, "Downloading the seed...")
            try:
                self.generating_seed = True

                # Limit the executor to 1 worker to make everything sequential
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                seed = random.randint(1, 1000000000)

                seed_uri, spoiler_uri = await self.client.get_download_links(seed, logic, mode, paths, additional_flags)
                seed_filepath = f"{seed}/{SEED_FILENAME}"
                spoiler_filepath = f"{seed}/{SPOILER_FILENAME}"

                # Create a temporary subfolder to avoid name conflict
                self.bot.loop.run_in_executor(executor, os.makedirs, str(seed))
                LOG.debug(f"Folder '{seed}' successfully created")

                # Download the files
                LOG.debug("Downloading the seed and the spoiler...")
                files_download_futures = [
                    self.client.download(seed_uri, seed_filepath),
                    self.client.download(spoiler_uri, spoiler_filepath)
                ]
                await asyncio.gather(*files_download_futures, loop=self.bot.loop)
                LOG.debug(f"'{SEED_FILENAME}' and '{SPOILER_FILENAME}' successfully created")

                # Send the files in the chat
                asyncio.ensure_future(download_message.delete(), loop=self.bot.loop)
                seed_header = await self._get_flags(seed_filepath)
                await self.bot.send(ctx.channel, seed_header, reaction=True,
                                    files=[discord.File(seed_filepath), discord.File(spoiler_filepath)])
                LOG.debug(f"The files have correctly been sent in Discord")

                # Delete everything once it's sent
                self.bot.loop.run_in_executor(executor, os.remove, seed_filepath)
                self.bot.loop.run_in_executor(executor, os.remove, spoiler_filepath)
                self.bot.loop.run_in_executor(executor, os.rmdir, str(seed))
                LOG.debug(f"Cleanup successful")

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
