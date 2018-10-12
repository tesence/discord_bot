import logging

from discord.ext import commands
from discord import utils as discord_utils

from discord_bot import config
from discord_bot import Emoji
from discord_bot import cogs

LOG = logging.getLogger('bot')

CONF_VARIABLES = ['RANDO_ROLE']


class OriRandoRoleCommands(cogs.CogMixin):

    def __init__(self, bot):
        super(OriRandoRoleCommands, self).__init__(bot, *CONF_VARIABLES)
        type(self).__name__ = "Ori rando commands"
        self.rando_role = None

    @commands.group(aliases=['lfg'])
    async def looking_for_game(self, ctx):
        """Add/remove the rando role"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)
        else:
            rando_role_name = config.get('RANDO_ROLE', guild_id=ctx.guild.id)
            self.rando_role = discord_utils.get(ctx.guild.roles, name=rando_role_name)

    @looking_for_game.command()
    async def add(self, ctx):
        if self.rando_role not in ctx.author.roles:
            await ctx.author.add_roles(self.rando_role)
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)
            LOG.debug(f"{ctx.author.name} now has the randomizer role")

    @looking_for_game.command(aliases=['rm'])
    async def remove(self, ctx):
        if self.rando_role in ctx.author.roles:
            await ctx.author.remove_roles(self.rando_role)
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)
            LOG.debug(f"{ctx.author.name} no longer has the randomizer role")


def setup(bot):
    bot.add_cog(OriRandoRoleCommands(bot))
