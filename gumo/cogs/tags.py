import asyncio
import collections
import logging
import re

from discord.ext import commands

from gumo import check
from gumo import db
from gumo import Emoji
from gumo import utils

LOG = logging.getLogger('bot')

REGEX = re.compile('^(.+)[^"]*(".*")$', re.MULTILINE | re.DOTALL)
EMOJI_REGEX = re.compile("^<:\w+:\d+>$")


class DuplicateTagError(commands.UserInputError):
    """If a user tries to create a tag that already exists"""


class TagCommands:

    def __init__(self, bot):
        type(self).__name__ = "Tag commands"
        self.bot = bot
        self.driver = db.TagDBDriver(self.bot, loop=self.bot.loop)
        self.data = collections.defaultdict(dict)
        asyncio.ensure_future(self.init(), loop=self.bot.loop)

    async def init(self):
        await self.driver.ready.wait()
        tags = await self.driver.list()
        for tag in tags:
            self.data[tag.guild_id][tag.code.lower()] = tag

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, code):
        """Return a tag value"""
        channel_repr = utils.get_channel_repr(ctx.channel)
        try:
            tag = self.data[ctx.guild.id][code.lower()]
            await self.driver.increment_usage(code)
        except KeyError:
            LOG.warning(f"[{channel_repr}] The tag '{code}' does not exist")
        else:
            await self.bot.send(ctx.channel, tag.content)

    @tag.command(name='create', aliases=['add'])
    @check.is_admin()
    async def create_tag(self, ctx, *, args):
        """Create a tag

        !tag create <code> "<content>"
        """
        if not re.match(REGEX, args):
            return
        code, content = re.match(REGEX, args).groups()
        code = code.strip()
        content = content[1:-1].strip()

        if code.lower() in [c.name for c in ctx.command.parent.commands]:
            LOG.warning("You cannot create a tag with the same name as a subcommand")
            return
        if code.lower() in self.data[ctx.guild.id]:
            raise DuplicateTagError(code)
        tag = await self.driver.create(code=code, content=content, author_id=ctx.author.id, guild_id=ctx.guild.id,
                                       created_at=str(ctx.message.created_at))
        self.data[ctx.guild.id][code.lower()] = tag
        await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    @tag.command(name='delete', aliases=['remove', 'rm'])
    @check.is_admin()
    async def delete_tag(self, ctx, *, code):
        """Delete a tag"""
        channel_repr = utils.get_channel_repr(ctx.channel)
        try:
            await self.driver.delete(code=code)
            del self.data[ctx.guild.id][code.lower()]
        except KeyError:
            LOG.warning(f"[{channel_repr}] The tag '{code}' does not exist")
        else:
            await ctx.message.add_reaction(Emoji.WHITE_CHECK_MARK)

    @tag.command(name='list')
    async def list_tag(self, ctx):
        """Return the list of available tags"""
        result = [f'`{tag.code}`' if not re.match(EMOJI_REGEX, tag.code) else tag.code for tag in self.data[ctx.guild.id].values()]
        result = "**Available tags**: " + ', '.join(tag for tag in result)
        await self.bot.send(ctx.channel, result)


def setup(bot):
    bot.add_cog(TagCommands(bot))
