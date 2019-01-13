import logging
import random

from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from gumo import utils

LOG = logging.getLogger('bot')

DAB_COOLDOWN = 180


class DabCommands:

    def __init__(self, bot):
        self.display_name = "Dab"
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, DAB_COOLDOWN, BucketType.member)
    async def dab(self, ctx, *, dabbed=None):
        """Disrespect someone"""
        channel_repr = utils.get_channel_repr(ctx.channel)
        if not dabbed:
            await ctx.invoke(self.bot.get_command('help'), command_name=ctx.command.name)
        elif "@here" not in dabbed and "@everyone" not in dabbed:
            times = random.randint(0, 100)
            answer = f"{ctx.author.display_name} dabs on {dabbed} {times} times!"
            LOG.info(f"[{channel_repr}] {answer}")
            await self.bot.send(ctx.channel, answer)


def setup(bot):
    bot.add_cog(DabCommands(bot))
