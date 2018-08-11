import logging

from discord.ext import commands
from discord import utils as discord_utils

from discord_bot import cfg

CONF = cfg.CONF
LOG = logging.getLogger('debug')


WHITE_CHECK_MARK_EMOJI = "\N{WHITE HEAVY CHECK MARK}"


class OriRandoRoleCommands:

    def __init__(self, bot):
        type(self).__name__ = "Ori rando commands"
        self.bot = bot
        self.rando_role = None

    @commands.group(aliases=['lfg'])
    async def looking_for_game(self, ctx):
        """Add/remove the rando role"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), "looking_for_game")
        else:
            self.rando_role = self.rando_role or discord_utils.get(ctx.guild.roles, name=CONF.RANDO_ROLE)

    @looking_for_game.command()
    async def add(self, ctx):
        if self.rando_role not in ctx.author.roles:
            await ctx.author.add_roles(self.rando_role)
            await ctx.message.add_reaction(WHITE_CHECK_MARK_EMOJI)
            LOG.debug(f"{ctx.author.name} now has the randomizer role")

    @looking_for_game.command(aliases=['rm'])
    async def remove(self, ctx):
        if self.rando_role in ctx.author.roles:
            await ctx.author.remove_roles(self.rando_role)
            await ctx.message.add_reaction(WHITE_CHECK_MARK_EMOJI)
            LOG.debug(f"{ctx.author.name} no longer has the randomizer role")


def setup(bot):
    ori_rando_role_commands = OriRandoRoleCommands(bot)
    bot.add_cog(ori_rando_role_commands)
