import logging

import discord
from discord.ext.commands import converter

from gumo import Emoji


LOG = logging.getLogger('bot')


class RoleCommands:

    def __init__(self, *role_names):
        self.role_converter = converter.RoleConverter()

    async def add_roles(self, ctx, *role_names, guild=None):
        for role_name in role_names:
            await self._add_role(ctx, role_name, guild)

    async def _add_role(self, ctx, role_name, guild):
        role = discord.utils.get(guild.roles, name=role_name)
        member = discord.utils.get(guild.members, id=ctx.author.id)
        if role not in member.roles:
            await member.add_roles(role)
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)
            LOG.debug(f"{ctx.author.name} now has the role '{role.name}' in the guild '{guild.name}'")

    async def remove_roles(self, ctx, *role_names, guild=None):
        for role_name in role_names:
            await self._remove_role(ctx, role_name, guild)

    async def _remove_role(self, ctx, role_name, guild):
        role = discord.utils.get(guild.roles, name=role_name)
        member = discord.utils.get(guild.members, id=ctx.author.id)
        if role in member.roles:
            await member.remove_roles(role)
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)
            LOG.debug(f"{ctx.author.name} no longer has the role '{role.name}' in the guild '{guild.name}'")
