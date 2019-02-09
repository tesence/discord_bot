import logging

from discord.ext import commands

from gumo import check
from gumo import config

LOG = logging.getLogger(__name__)


class AdminCommands:

    def __init__(self, bot):
        self.bot = bot
        self.display_name = "Admin"

    @commands.command(hidden=True)
    @check.is_owner()
    async def reload(self, ctx, *extensions):
        """Reload some extensions"""
        config.load()

        for extension in extensions:
            extension = f'gumo.cogs.{extension}'
            self.bot.unload_extension(extension)
            self.bot.load_extension(extension)
            LOG.debug(f"Extension '{extension}' reloaded")


def setup(bot):
    bot.add_cog(AdminCommands(bot))
