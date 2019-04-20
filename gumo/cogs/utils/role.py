import logging

import discord

from gumo import emoji

LOG = logging.getLogger(__name__)


class RoleCommands:

    async def _manage_roles(self, ctx, action, *role_names, guild=None):
        guild = guild or ctx.guild
        roles = {r: discord.utils.get(guild.roles, name=r) for r in role_names}
        member = guild.get_member(ctx.author.id)

        for name, role in list(roles.items()):
            if not isinstance(role, discord.Role):
                LOG.warning(f"The role '{name}' dis not a valid role in this guild")
                del roles[name]

        await getattr(member, action)(*roles.values())
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    async def add_roles(self, ctx, *role_names, guild=None):
        await self._manage_roles(ctx, 'add_roles', *role_names, guild=None)

    async def remove_roles(self, ctx, *role_names, guild=None):
        await self._manage_roles(ctx, 'remove_roles', *role_names, guild=None)
