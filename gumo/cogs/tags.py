import json
import logging
import os

from discord.ext import commands

from gumo import config
from gumo import cogs
from gumo import utils

LOG = logging.getLogger('bot')

TAG_FILE_PATH = "data/tags.json"


class TagCommands(cogs.CogMixin):

    def __init__(self, bot):
        super(TagCommands, self).__init__(bot)
        type(self).__name__ = "Tag commands"
        self.tag_file_absolute_path = utils.get_project_dir() + "/" + TAG_FILE_PATH
        self.data = {}

        # Create the file if it does not exist
        if not os.path.isfile(self.tag_file_absolute_path):
            self._save()

    def _load(self):
        with open(TAG_FILE_PATH, 'r') as tag_file:
            self.data.update(json.load(tag_file))

    def _save(self):
        with open(TAG_FILE_PATH, 'w') as tag_file:
            json.dump(self.data, tag_file, indent=2)

    async def on_ready(self):
        self._load()

        # Get the list of guild that have the tag extension enabled
        guilds = {g for g in self.bot.guilds if 'tags' in config.get('EXTENSIONS', guild_id=g.id, default=True)}

        for guild in guilds:
            guild_id = str(guild.id)
            if guild_id not in self.data:
                self.data[guild_id] = {}

        self._save()

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, key):
        """Return a tag value"""
        self._load()
        tag = self.data[str(ctx.guild.id)].get(key)
        if tag:
            await self.bot.send(ctx.channel, tag)

    @tag.command(name='list')
    async def list_tag(self, ctx):
        """Return the list of available tags"""
        result = "**Available tags**: " + ', '.join(f'`{tag}`' for tag in self.data[str(ctx.guild.id)])
        await self.bot.send(ctx.channel, result)


def setup(bot):
    bot.add_cog(TagCommands(bot))
