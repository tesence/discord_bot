import importlib
import logging
import sys

from discord.ext import commands

from gumo import check
from gumo import config
from gumo import emoji

LOG = logging.getLogger(__name__)


class AdminCommands:

    def __init__(self, bot):
        self.bot = bot
        self.display_name = "Admin"

    async def __local_check(self, ctx):
        return await check.is_owner(ctx)

    @commands.group(hidden=True)
    async def reload(self, ctx):

        # Reloading configuration files
        config.load()
        if ctx.invoked_subcommand is None:
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @reload.command(name="ext", hidden=True)
    async def reload_ext(self, ctx, *extensions):

        # Reloading the extensions
        for extension in extensions:
            extension = f'gumo.cogs.{extension}'
            self.bot.unload_extension(extension)
            self.bot.load_extension(extension)
            LOG.debug(f"Extension '{extension}' reloaded")

        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @reload.command(name="mod", hidden=True)
    async def reload_mod(self, ctx, prefix):

        # Reload the modules
        reloaded_modules = []
        for package in sys.modules:
            if package.startswith(prefix):
                importlib.reload(sys.modules[package])
                reloaded_modules.append(package)

        LOG.debug(f"The following modules have been reloaded: {reloaded_modules}")
        await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)


def setup(bot):
    bot.add_cog(AdminCommands(bot))
