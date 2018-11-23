import logging

from discord.ext import commands

from gumo import config
from gumo.cogs.utils import role

LOG = logging.getLogger('bot')


class OriRandoRoleCommands(role.RoleCommands):

    def __init__(self, bot):
        super(OriRandoRoleCommands, self).__init__()
        type(self).__name__ = "Ori rando commands"
        self.bot = bot
        self.rando_role = None

    @commands.group(aliases=['lfg'])
    async def looking_for_game(self, ctx):
        """Add/remove the rando role

        Type "!lfg add" to get the role
        Type "!lfg remove" to remove the role
        """
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)
        else:
            self.rando_role = config.get('RANDO_ROLE', guild_id=ctx.guild.id)

    @looking_for_game.command()
    async def add(self, ctx):
        """Add the rando role"""
        await self.add_role(ctx, self.rando_role)

    @looking_for_game.command(aliases=['rm'])
    async def remove(self, ctx):
        """Remove the rando role"""
        await self.remove_role(ctx, self.rando_role)


def setup(bot):
    bot.add_cog(OriRandoRoleCommands(bot))
