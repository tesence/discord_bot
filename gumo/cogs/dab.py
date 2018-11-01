import logging
import random

from discord.ext import commands
from gumo import config
from discord.ext.commands.cooldowns import BucketType
from gumo import utils

from gumo import cogs

LOG = logging.getLogger('bot')

DEFAULT_DAB_COOLDOWN = 120


class DabCommands(cogs.CogMixin):

    def __init__(self, bot):
        super(DabCommands, self).__init__(bot)
        type(self).__name__ = "Dab commands"

    @commands.command()
    @commands.cooldown(1, config.get('DAB_COOLDOWN', DEFAULT_DAB_COOLDOWN), BucketType.channel)
    async def dab(self, ctx, *, dabbed=None):
        """Disrespect someone"""
        channel_repr = utils.get_channel_repr(ctx.channel)
        if not dabbed:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)
        elif "@here" not in dabbed and "@everyone" not in dabbed:
            times = random.randint(0, 100)
            answer = f"{ctx.author.display_name} dabs on {dabbed} {times} times!"
            LOG.info(f"[{channel_repr}] {answer}")
            await self.bot.send(ctx.channel, answer)

    @commands.command()
    async def ban(self, ctx, *, arg=None):
        await self.bot.send(ctx.channel, f"{arg} has been banned", code_block=True)


def setup(bot):
    bot.add_cog(DabCommands(bot))
