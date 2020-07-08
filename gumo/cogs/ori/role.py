import logging

import discord
from discord.ext import commands

from gumo.cogs.utils import role

LOG = logging.getLogger(__name__)

RANDO_ROLE = "Looking For Rando"


class OriRandoRoleCommands(commands.Cog, role.RoleCommands):

    def __init__(self, bot):
        self.display_name = "Ori rando"
        self.bot = bot
        self.rando_role = None

    async def __local_check(self, ctx):
        role = discord.utils.get(ctx.guild.roles, name=RANDO_ROLE)
        if not role:
            LOG.warning(f"Extension '{self.__module__}' unavailable for guild '{ctx.guild.name}#{ctx.guild.id}'. "
                        f"Cannot find role: '{RANDO_ROLE}'")
        return role is not None

    @commands.group(aliases=['lfg'])
    @commands.guild_only()
    async def looking_for_game(self, ctx):
        """Add/remove the rando role"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), command_name=ctx.command.name)

    @looking_for_game.command()
    @commands.guild_only()
    async def add(self, ctx):
        """Add the rando role"""
        await self.add_roles(ctx, RANDO_ROLE, guild=ctx.guild)

    @looking_for_game.command(aliases=['rm'])
    @commands.guild_only()
    async def remove(self, ctx):
        """Remove the rando role"""
        await self.remove_roles(ctx, RANDO_ROLE, guild=ctx.guild)


def setup(bot):
    bot.add_cog(OriRandoRoleCommands(bot))
