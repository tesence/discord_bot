import asyncio
import concurrent.futures
import logging
import os
import random
import re

import aiofiles
import discord
from discord.ext import commands
from discord import utils as discord_utils

from discord_bot.api import ori_randomizer
from discord_bot import cfg
from discord_bot import log
from discord_bot import utils

CONF = cfg.CONF
LOG = logging.getLogger('debug')

SEED_FILENAME = "randomizer.dat"
SPOILER_FILENAME = "spoiler.txt"

WHITE_CHECK_MARK_EMOJI = "\N{WHITE HEAVY CHECK MARK}"


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
        self.rando_role = None
        self.client = ori_randomizer.OriRandomizerAPIClient()
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
    async def seed(self, ctx, logic='', key_mode='', *additional_flags):
        """Generate a seed for the Ori randomizer

        Valid logics: casual, standard, expert, master, hard, ohko, 0xp, glitched
        Valid modes: shards, limitkeys, clues
        Valid flags: easy-path, normal-path, hard-path, normal, speed, dbash, extended, extended-damage, lure,
                     speed-lure, lure-hard, dboost, dboost-light, dboost-hard, cdash, cdash-farming, extreme,
                     timed-level, glitched
        """
        path_pattern = "(\w+)\-path"

        if not logic:
            LOG.debug("The logic is not specified, the logic is set to 'standard'")
            logic = "standard"

        additional_flags = list(additional_flags)
        paths = []
        for flag in additional_flags:
            if re.match(path_pattern, flag):
                paths.append(re.match(path_pattern, flag).group(1))
                additional_flags.remove(flag)
        path = paths[0] if paths else paths

        LOG.debug(f"Seed parameters: logic='{logic}' mode='{key_mode}' paths={paths} "
                  f"additional_flags={list(additional_flags)}")

        if logic.lower() not in ori_randomizer.PRESETS:
            raise InvalidLogicError(logic)

        if key_mode.lower() and key_mode not in ori_randomizer.MODES:
            raise InvalidModeError(key_mode)

        invalid_flags = set(additional_flags) - set(ori_randomizer.VARIATIONS)
        if invalid_flags:
            raise InvalidFlagError(*invalid_flags)

        download_message = await self.bot.send(ctx.channel, "Downloading the seed...")
        try:
            self.generating_seed = True

            # Limit the executor to 1 worker to make everything sequential
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            seed = str(random.randint(1, 1000000000))

            # Download the data
            LOG.debug("Downloading the seed data...")
            data = await self.client.get_data(seed, logic, key_mode, path)

            # Create a temporary subfolder to avoid name conflict
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
            message = f"Seed requested by **{ctx.author.nick or ctx.author.name}**\n" \
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

        except Exception as e:
            self.generating_seed = False
            error_message = "An error has occured while generating the seed"
            LOG.exception(log.get_log_exception_message(error_message, e))
            await download_message.edit(content=f"```{error_message}. Please try again later.```")
            raise SeedGeneratorError

    @commands.group(aliases=['lfg'])
    async def looking_for_rando(self, ctx):
        """Add/remove the rando role"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), "looking_for_rando")
        else:
            self.rando_role = self.rando_role or discord_utils.get(ctx.guild.roles, name=CONF.RANDO_ROLE)

    @looking_for_rando.command()
    async def add(self, ctx):
        if self.rando_role not in ctx.author.roles:
            await ctx.author.add_roles(self.rando_role)
            await ctx.message.add_reaction(WHITE_CHECK_MARK_EMOJI)
            LOG.debug(f"{ctx.author.name} now has the randomizer role")

    @looking_for_rando.command(aliases=['rm'])
    async def remove(self, ctx):
        if self.rando_role in ctx.author.roles:
            await ctx.author.remove_roles(self.rando_role)
            await ctx.message.add_reaction(WHITE_CHECK_MARK_EMOJI)
            LOG.debug(f"{ctx.author.name} no longer has the randomizer role")


def setup(bot):
    dab_commands = OriRandoCommands(bot)
    bot.add_cog(dab_commands)
