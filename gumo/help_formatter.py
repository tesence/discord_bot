import discord
from discord.ext.commands import formatter

from gumo import config


class HelpFormatter(formatter.HelpFormatter):

    async def format(self):
        pages = await super(HelpFormatter, self).format()
        if isinstance(self.context.channel, discord.TextChannel):
            footers = config.get('HELP_FOOTERS', guild_id=self.context.guild.id)
            if footers:
                footer = "\n".join(footers)
                pages[0] += footer
        return pages
