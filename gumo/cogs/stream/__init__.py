from .core import StreamCommands


def setup(bot):
    bot.add_cog(StreamCommands(bot))
