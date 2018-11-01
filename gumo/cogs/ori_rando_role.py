import logging

from discord.ext import commands

from gumo import config
from gumo import cogs
from gumo.cogs.utils import role

LOG = logging.getLogger('bot')


class OriRandoRoleCommands(cogs.CogMixin, role.RoleCommands):

    def __init__(self, bot):
        cogs.CogMixin.__init__(self, bot)
        role.RoleCommands.__init__(self)
        type(self).__name__ = "Ori rando commands"
        self.rando_role = None

    @commands.group(aliases=['lfg'])
    async def looking_for_game(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)
        else:
            self.rando_role = config.get('RANDO_ROLE', guild_id=ctx.guild.id)

    @looking_for_game.command()
    async def add(self, ctx):
        await self.add_role(ctx, self.rando_role)

    @looking_for_game.command(aliases=['rm'])
    async def remove(self, ctx):
        await self.remove_role(ctx, self.rando_role)


def setup(bot):
    bot.add_cog(OriRandoRoleCommands(bot))
