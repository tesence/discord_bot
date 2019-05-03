from discord.ext import commands

from gumo.api import base
from gumo import emoji

class MiscCommands(commands.Cog, base.APIClient):

    def __init__(self, bot):
        self.bot = bot
        super().__init__(loop=self.bot.loop)

    @commands.command()
    async def checkname(self, ctx, *, name):
        """Check if a name on twitch is available"""
        async with self._session.get(f"https://passport.twitch.tv/usernames/{name}") as r:
            if r.status == 204:
                await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)
            else:
                await ctx.message.add_reaction(emoji.CROSS_MARK)


def setup(bot):
    bot.add_cog(MiscCommands(bot))
