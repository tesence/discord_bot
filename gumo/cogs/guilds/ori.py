import asyncio
import collections
import logging
import random
import re

import multidict
import discord
from discord.ext import commands

from gumo.cogs.utils import role
from gumo import emoji
from gumo.emoji import EMOJI_REGEX

LOG = logging.getLogger(__name__)

GUILD_ID = 116250700685508615
ROLES = ["He/Him", "She/Her", "They/Them"]

WOTW_RANDO_ROLE_ID = 470331619400482816
BF_RANDO_ROLE_ID = 762350650071449611

class EmojiChain:

    def __init__(self):
        self.contributors = []
        self.emoji = None
        self.answered = False

    def __bool__(self):
        return bool(self.contributors) and bool(self.emoji)


class OriGuildCommands(commands.Cog, role.RoleCommands):

    def __init__(self, bot):
        super().__init__()
        self.display_name = "Ori guild commands"
        self.bot = bot
        self.roles = multidict.CIMultiDict(**{role_name: role_name for role_name in ROLES})
        self.emoji_chain_by_channel = collections.defaultdict(EmojiChain)
        self.emoji_chain_threshold = random.randint(3, 7)
        self.emoji_chain_timeout = random.randint(0, 20)

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

        if not emoji:
            # Then, this is not a guild emoji
            return

        # If someone starts a chain, use the guild emoji in the message
        if not current_chain:
            current_chain.emoji = emoji

        # Add the author as a contributor of the emoji chain
        if message.author not in current_chain.contributors:
            current_chain.contributors.append(message.author)

        # If enough people contributed to consider it a emoji chain
        if len(current_chain.contributors) >= self.emoji_chain_threshold and not current_chain.answered:
            current_chain.answered = True
            await asyncio.sleep(self.emoji_chain_timeout)
            await message.channel.send(current_chain.emoji)
            LOG.debug(f"Contributing to '{emoji.name}' chain of size {len(current_chain.contributors)} in channel "
                      f"'{ctx.channel.guild.name}#{ctx.channel.name}' started by "
                      f"'{current_chain.contributors[0].display_name}' (timeout: {self.emoji_chain_timeout}s)")
            self.emoji_chain_threshold = random.randint(3, 7)
            self.emoji_chain_timeout = random.randint(0, 20)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        user = self.bot.get_user(payload.user_id)
        ctx = await self.bot.get_context(message)

        # Ignore if:
        # - The listener is triggered by one of the bot's reactions
        # - The bot does not have reaction permission in the channel
        # - The message has been send in another guild
        if user == self.bot.user or not ctx.me.permissions_in(channel).add_reactions or \
                not message.guild.id == GUILD_ID:
            return

        emoji = self.bot.get_emoji(payload.emoji.id)

        if not emoji:
            # Then, this is not a guild emoji
            return

        for reaction in message.reactions:

            if reaction.emoji == emoji and reaction.count >= self.emoji_chain_threshold:

                if self.bot.user in await reaction.users().flatten():
                    continue

                await asyncio.sleep(self.emoji_chain_timeout)
                await message.add_reaction(emoji)
                LOG.debug(f"Contributing to '{emoji.name}' reaction chain of size {reaction.count} on "
                          f"message sent by '{message.author.display_name}' at '{message.created_at}' in channel "
                          f"'{ctx.channel.guild.name}#{ctx.channel.name}' (timeout: {self.emoji_chain_timeout}s)")
                self.emoji_chain_threshold = random.randint(3, 7)
                self.emoji_chain_timeout = random.randint(0, 20)

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


class OriRandoRoleCommands(commands.Cog):

    def __init__(self, bot):
        self.display_name = "Ori rando"
        self.bot = bot
        self.bf_rando_role = None
        self.wotw_rando_role = None
        self.guild = None

    @commands.group()
    @commands.guild_only()
    async def lfr(self, ctx):
        """Add/remove rando roles"""

        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('help'), command_name=ctx.command.name)

    def _get_valid_roles(self, roles):
        self.guild = self.bot.get_guild(GUILD_ID)
        self.bf_rando_role = self.bf_rando_role or self.guild.get_role(BF_RANDO_ROLE_ID)
        self.wotw_rando_role = self.wotw_rando_role or self.guild.get_role(WOTW_RANDO_ROLE_ID)

        valid_roles = []
        if "both" in roles:
            valid_roles = [self.bf_rando_role, self.wotw_rando_role]
        else:
            if "bf" in roles:
                valid_roles.append(self.bf_rando_role)
            if "wotw" in roles:
                valid_roles.append(self.wotw_rando_role)

        return valid_roles

    @lfr.command()
    @commands.guild_only()
    async def add(self, ctx, *roles):
        """Add rando roles

        e.g:
        `!lfr add bf` to get pinged about Blind Forest rando
        `!lfr add wotw` to get pinged about Will of the Wisps rando
        `!lfr add both` to get pinged about both (`!lfr add bf wotw` also works)
        """

        if not roles:
            raise commands.UserInputError("Missing roles to add")

        else:
            valid_roles = self._get_valid_roles(roles)
            await ctx.author.add_roles(*valid_roles)
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)

    @lfr.command(aliases=['rm'])
    @commands.guild_only()
    async def remove(self, ctx, *roles):
        """Remove rando roles

        e.g:
        `!lfr remove bf` to not get pinged about Blind Forest rando anymore
        `!lfr remove wotw` to not get pinged about Will of the Wisps rando anymore
        `!lfr remove both` to not get pinged about any rando anymore (`!lfr remove bf wotw` also works)
        """
        if not roles:
            raise commands.UserInputError("Missing roles to remove")

        else:
            valid_roles = self._get_valid_roles(roles)
            await ctx.author.remove_roles(*valid_roles)
            await ctx.message.add_reaction(emoji.WHITE_CHECK_MARK)


def setup(bot):
    bot.add_cog(OriRandoRoleCommands(bot))
    bot.add_cog(OriGuildCommands(bot))
