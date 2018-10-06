import logging
import random

from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from discord_bot import cfg
from discord_bot import cogs

CONF = cfg.CONF
LOG = logging.getLogger('bot')


class DabCommands(cogs.CogMixin):

    def __init__(self, bot):
        super(DabCommands, self).__init__(bot)
        type(self).__name__ = "Dab commands"

    @commands.command()
    @commands.cooldown(1, getattr(CONF, 'DAB_COOLDOWN', 0), BucketType.channel)
    async def dab(self, ctx, *, dabbed=None):
        """Disrespect someone"""
        if not dabbed:
            await ctx.invoke(self.bot.get_command('help'), ctx.command.name)
        elif "@here" not in dabbed and "@everyone" not in dabbed:
            times = random.randint(0, 100)
            answer = f"{ctx.author.display_name} dabs on {dabbed} {times} times!"
            LOG.info(answer)
            await self.bot.send(ctx.channel, answer)


def setup(bot):
    bot.add_cog(DabCommands(bot))
