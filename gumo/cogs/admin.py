import logging

from discord.ext import commands

from gumo import config
from gumo import cogs
from gumo import utils

LOG = logging.getLogger('bot')


class AdminCommands(cogs.CogMixin):

    def __init__(self, bot):
        super(AdminCommands, self).__init__(bot)
        type(self).__name__ = "Admin commands"

    async def __local_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command()
    async def reload(self, ctx, *extensions):
        """Reload some extensions"""
        channel_repr = utils.get_channel_repr(ctx.channel)

        config.load()

        for extension in extensions:
            extension = f'cogs.{extension}'
            if extension in self.bot.extensions:
                self.bot.unload_extension(extension)
                self.bot.load_extension(extension)
                LOG.debug(f"Extension '{extension}' reloaded")
            else:
                LOG.warning(f"[{channel_repr}] '{extension}' is not a valid extension")


def setup(bot):
    bot.add_cog(AdminCommands(bot))
