import importlib
import logging
import re
import sys

import discord
from discord.ext import commands
from discord.ext.commands import converter, errors

from gumo import check
from gumo import client
from gumo import config
from gumo import emoji

LOG = logging.getLogger(__name__)


class GlobalRoleConverter(converter.IDConverter):

    async def convert(self, argument, guild):
        match = self._get_id_match(argument) or re.match(r"<@&([0-9]+)>$", argument)
        if match:
            result = guild.get_role(int(match.group(1)))
        else:
            result = discord.utils.get(guild._roles.values(), name=argument)

        if result is None:
            raise errors.BadArgument("Role '{}' not found.".format(argument))
        return result


class AdminCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.display_name = "Admin"

    async def __local_check(self, ctx):
        return await check.is_owner(ctx)

    @commands.group(hidden=True)
    async def reload(self, ctx):

        # Reloading configuration files
        config.load()
        if ctx.invoked_subcommand is None:
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @reload.command(name="ext", hidden=True)
    async def reload_ext(self, ctx, *extensions):

        # Reloading the extensions
        for extension in extensions:
            extension = f'gumo.cogs.{extension}'
            self.bot.reload_extension(extension)
            LOG.debug(f"Extension '{extension}' reloaded")

        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @reload.command(name="mod", hidden=True)
    async def reload_mod(self, ctx, prefix):

        # Reload the modules
        reloaded_modules = []
        for package in sys.modules:
            if package.startswith(prefix):
                importlib.reload(sys.modules[package])
                reloaded_modules.append(package)

        LOG.debug(f"The following modules have been reloaded: {reloaded_modules}")
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @commands.group(hidden=True)
    async def prefix(self, ctx):
        pass

    @prefix.command(name="add", hidden=True)
    async def prefix_add(self, ctx, new_prefix, guild_id=None):
        guild = self.bot.get_guild(int(guild_id)) if guild_id else ctx.guild
        columns = ['guild_name', 'guild_id', 'name']
        await self.bot.prefix_db_driver.create(columns, (guild.name, guild.id, new_prefix))
        self.bot.prefixes[ctx.guild.id].add(new_prefix)
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @prefix.command(name="rm", hidden=True)
    async def prefix_rm(self, ctx, new_prefix, guild_id=None):
        guild = self.bot.get_guild(int(guild_id)) if guild_id else ctx.guild
        await self.bot.prefix_db_driver.delete(guild_id=guild.id, name=new_prefix)
        try:
            self.bot.prefixes[ctx.guild.id].remove(new_prefix)
        except ValueError:
            pass
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @commands.group(hidden=True)
    async def ext(self, ctx):
        pass

    @ext.command(name="enable", hidden=True)
    async def ext_enable(self, ctx, extension, guild_id=None):
        if extension not in client.EXTENSIONS:
            return
        guild = self.bot.get_guild(int(guild_id)) if guild_id else ctx.guild
        columns = ['guild_name', 'guild_id', 'name']
        await self.bot.extension_db_driver.create(columns, (guild.name, guild.id, extension))
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @ext.command(name="disable", hidden=True)
    async def ext_disable(self, ctx, extension, guild_id=None):
        if extension not in client.EXTENSIONS:
            return
        guild = self.bot.get_guild(int(guild_id)) if guild_id else ctx.guild
        await self.bot.extension_db_driver.delete(guild_id=guild.id, name=extension)
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @commands.group(hidden=True)
    async def role(self, ctx):
        pass

    @role.command(name="add", hidden=True)
    async def role_add(self, ctx, argument, guild_id: int = None):
        guild = self.bot.get_guild(guild_id) if guild_id else ctx.guild
        if not guild:
            raise errors.BadArgument("Guild '{}' not found.".format(guild_id))
        admin_role = await GlobalRoleConverter().convert(argument, guild)
        columns = ['guild_name', 'guild_id', 'name', 'id']
        values = (guild.name, guild.id, admin_role.name, admin_role.id)
        await self.bot.admin_role_db_driver.create(columns, values)
        self.bot.admin_roles[ctx.guild.id].add(admin_role.id)
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @role.command(name="rm", hidden=True)
    async def role_rm(self, ctx, argument, guild_id: int = None):
        guild = self.bot.get_guild(guild_id) if guild_id else ctx.guild
        if not guild:
            raise errors.BadArgument("Guild '{}' not found.".format(guild_id))
        admin_role = await GlobalRoleConverter().convert(argument, guild)
        await self.bot.admin_role_db_driver.delete(guild_id=guild.id, id=admin_role.id)
        try:
            self.bot.admin_roles[ctx.guild.id].remove(admin_role.id)
        except ValueError:
            pass
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)


def setup(bot):
    bot.add_cog(AdminCommands(bot))
