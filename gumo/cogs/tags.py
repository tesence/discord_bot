import logging
import re

import asyncpg
from discord.ext import commands

from gumo import check
from gumo import db
from gumo import emoji
from gumo import utils

LOG = logging.getLogger('bot')

REGEX = re.compile('^([^"]+)[^"]*(".*")$', re.MULTILINE | re.DOTALL)
EMOJI_REGEX = re.compile("^<:\w+:\d+>$")


class TagCommands:

    def __init__(self, bot):
        self.display_name = "Tag"
        self.bot = bot
        self.driver = db.TagDBDriver(self.bot)

    async def on_ready(self):
        await self.driver.init()

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, *, code):
        """Return a tag value"""
        channel_repr = utils.get_channel_repr(ctx.channel)
        tag = await self.driver.increment_usage(code=code, guild_id=ctx.guild.id)
        if tag:
            await self.bot.send(ctx.channel, tag.content)
        else:
            LOG.warning(f"[{channel_repr}] The tag '{code}' does not exist")

    @tag.command(name='create', aliases=['add'], usage='tag create <code> "<content>"')
    @commands.guild_only()
    @check.is_admin()
    async def create_tag(self, ctx, *, args):
        """Create a tag"""
        if not re.match(REGEX, args):
            return
        code, content = re.match(REGEX, args).groups()
        code = code.strip()
        content = content[1:-1].strip()

        if code.lower() in [c.name for c in ctx.command.parent.commands]:
            LOG.warning("You cannot create a tag with the same name as a subcommand")
            return
        try:
            await self.driver.create(code=code, content=content, author_id=ctx.author.id, guild_id=ctx.guild.id)
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)
        except asyncpg.UniqueViolationError:
            LOG.warning(f"A tag with the code '{code}' already exists")

    @tag.command(name='delete', aliases=['remove', 'rm'])
    @commands.guild_only()
    @check.is_admin()
    async def delete_tag(self, ctx, *, code):
        """Delete a tag"""
        channel_repr = utils.get_channel_repr(ctx.channel)
        try:
            await self.driver.delete(code=code)
        except KeyError:
            LOG.warning(f"[{channel_repr}] The tag '{code}' does not exist")
        else:
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @tag.command(name='list')
    @commands.guild_only()
    async def list_tag(self, ctx):
        """Return the list of available tags"""
        result = [f'`{tag.code}`' if not re.match(EMOJI_REGEX, tag.code) else tag.code
                  for tag in await self.driver.list(guild_id=ctx.guild.id)]
        result = "**Available tags**: " + ', '.join(tag for tag in result)
        await self.bot.send(ctx.channel, result)


def setup(bot):
    bot.add_cog(TagCommands(bot))
