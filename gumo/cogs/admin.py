import logging

from discord.ext import commands

from gumo import check
from gumo import config

LOG = logging.getLogger('bot')


class AdminCommands:

    def __init__(self, bot):
        type(self).__name__ = "Admin commands"
        self.bot = bot

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
