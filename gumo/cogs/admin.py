import logging

from discord.ext import commands

from gumo import check
from gumo import config
from gumo import cogs

LOG = logging.getLogger('bot')


class AdminCommands(cogs.CogMixin):

    def __init__(self, bot):
        super(AdminCommands, self).__init__(bot)
        type(self).__name__ = "Admin commands"

    async def __local_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command()
    @check.is_owner()
    async def reload(self, ctx, *extensions):
        """Reload some extensions"""
        config.load()

        for extension in extensions:
            extension = f'cogs.{extension}'
            self.bot.unload_extension(extension)
            self.bot.load_extension(extension)
            LOG.debug(f"Extension '{extension}' reloaded")


def setup(bot):
    bot.add_cog(AdminCommands(bot))
