import logging
import random

from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from discord import utils as discord_utils

from gumo.cogs.utils import role
from gumo import config
from gumo import emoji

LOG = logging.getLogger('bot')

DAB_COOLDOWN = 180
DEFAULT_SWITCH_COOLDOWN = 600


def check_undabable_role(ctx):
    role_name = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
    return role_name and discord_utils.get(ctx.guild.roles, name=role_name)


def _has_undabable_role(ctx):
    role_name = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
    role = discord_utils.get(ctx.guild.roles, name=role_name)
    return role in ctx.author.roles


def has_undabable_role(ctx):
    return _has_undabable_role(ctx)


def has_not_undabable_role(ctx):
    return not _has_undabable_role(ctx)


class DabCommands(role.RoleCommands):

    def __init__(self, bot):
        super(DabCommands, self).__init__()
        self.display_name = "Dab"
        self.bot = bot
        self.role = None

    @commands.command()
    @commands.guild_only()
    @commands.check(has_not_undabable_role)
    @commands.cooldown(1, DAB_COOLDOWN, BucketType.member)
    async def dab(self, ctx, *, dabbed):
        """Disrespect someone"""
        role_name = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
        if role_name:
            role = discord_utils.get(ctx.guild.roles, name=role_name)
            for member in ctx.message.mentions:
                if role in member.roles:
                    await ctx.message.add_reaction(emoji.RAISED_HAND)
                    return

        times = random.randint(0, 100)
        answer = f"{ctx.author.display_name} dabs on {dabbed} {times} times!"
        await self.bot.send(ctx.channel, answer)

    @commands.command()
    @commands.guild_only()
    @commands.check(check_undabable_role)
    @commands.check(has_undabable_role)
    @commands.cooldown(1, DEFAULT_SWITCH_COOLDOWN, BucketType.member)
    async def dabable(self, ctx):
        """ALlow people to dab on you (default)"""
        self.role = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
        await self.remove_roles(ctx, self.role)

    @commands.command()
    @commands.guild_only()
    @commands.check(check_undabable_role)
    @commands.check(has_not_undabable_role)
    @commands.cooldown(1, DEFAULT_SWITCH_COOLDOWN, BucketType.member)
    async def undabable(self, ctx):
        """Prevent people from dabbing on you"""
        self.role = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
        await self.add_roles(ctx, self.role)


def setup(bot):
    bot.add_cog(DabCommands(bot))
