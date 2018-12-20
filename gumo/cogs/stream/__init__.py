from .core import StreamManager


def setup(bot):
    bot.add_cog(StreamManager(bot))
