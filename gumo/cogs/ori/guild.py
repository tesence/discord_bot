import asyncio
import collections
import logging
import random
import re

import multidict
import discord
from discord.ext import commands

from gumo.cogs.utils import role
from gumo.emoji import EMOJI_REGEX

LOG = logging.getLogger(__name__)

GUILD_ID = 116250700685508615
ROLES = ["He/Him", "She/Her", "They/Them"]


class EmojiChain:

    def __init__(self):
        self.contributors = set()
        self.emoji = None
        self.answered = False
        self.limit = random.randint(3, 6)
        self.timeout = random.randint(0, 20)

    def __bool__(self):
        return bool(self.contributors) and bool(self.emoji)

    def __repr__(self):
        return f"<emoji={self.emoji} contributors={len(self.contributors)} answered={self.answered} " \
               f"limit={self.limit} timeout={self.timeout}>"


class OriGuildCommands(commands.Cog, role.RoleCommands):

    def __init__(self, bot):
        super().__init__()
        self.display_name = "Ori guild commands"
        self.bot = bot
        self.roles = multidict.CIMultiDict(**{role_name: role_name for role_name in ROLES})
        self.emoji_chain_by_channel = collections.defaultdict(EmojiChain)

    @commands.Cog.listener()
    async def on_message(self, message):

        ctx = await self.bot.get_context(message)

        if isinstance(ctx.channel, discord.DMChannel):
            return

        # Ignore if:
        # - The author is a bot
        # - The bot does not have write permission in the channel
        # - The message has been send in another guild
        if ctx.author.bot or not ctx.me.permissions_in(ctx.channel).send_messages or not message.guild.id == GUILD_ID:
            return

        # Check if the message is a single emoji and retrieve the related guild emoji, None otherwise
        emoji = None
        if re.match(EMOJI_REGEX, message.content):
            emoji = self.bot.get_emoji(int(re.match(EMOJI_REGEX, message.content).group(1)))

        current_chain = self.emoji_chain_by_channel[ctx.channel]

        # If someone sends a message that is not a single guild emoji, or the wrong one, reset the chain
        if current_chain and (not emoji or not current_chain.emoji == emoji):
            del self.emoji_chain_by_channel[ctx.channel]
            current_chain = self.emoji_chain_by_channel[ctx.channel]

        if emoji:

            # If someone starts a chain, use the guild emoji in the message
            if not current_chain:
                current_chain.emoji = emoji

            # Add the author as a contributor of the emoji chain
            current_chain.contributors.add(message.author)

            # If enough people contributed to consider it a emoji chain
            if len(current_chain.contributors) >= current_chain.limit and not current_chain.answered:
                current_chain.answered = True
                await asyncio.sleep(current_chain.timeout)
                await message.channel.send(current_chain.emoji)

    @commands.group(invoke_without_command=True)
    async def pronoun(self, ctx, *pronouns):
        """Add/remove pronoun roles

        e.g:
        `!pronoun He/Him They/Them`
        `!pronoun remove`

        Available roles: `He/Him`, `She/Her`, `They/Them`

        *Note: This command can be used in the Ori discord or you can send a direct message to the bot*
        """
        if not pronouns:
            await ctx.invoke(self.bot.get_command('help'), command_name=ctx.command.name)
            return
        valid_pronouns = [self.roles[pronoun] for pronoun in pronouns if pronoun in self.roles]
        await self.add_roles(ctx, *valid_pronouns, guild=self.bot.get_guild(GUILD_ID))

    @pronoun.command(name='remove', aliases=['rm'])
    async def remove_pronouns(self, ctx):
        await self.remove_roles(ctx, *ROLES, guild=self.bot.get_guild(GUILD_ID))


def setup(bot):
    bot.add_cog(OriGuildCommands(bot))
