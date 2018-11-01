import logging

from discord.ext.commands import converter

from gumo import Emoji


LOG = logging.getLogger('bot')


class RoleCommands:

    def __init__(self):
        self.role_converter = converter.RoleConverter()

    async def _get_role(self, ctx, role):
        return await self.role_converter.convert(ctx, role)

    async def add_role(self, ctx, role):
        role = await self._get_role(ctx, role)
        if role not in ctx.author.roles:
            await ctx.author.add_roles(role)
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)
            LOG.debug(f"{ctx.author.name} now has the role: {role.name}")

    async def remove_role(self, ctx, role):
        role = await self._get_role(ctx, role)
        if role in ctx.author.roles:
            await ctx.author.remove_roles(role)
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)
            LOG.debug(f"{ctx.author.name} no longer has the role: {role.name}")
