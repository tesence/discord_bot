from concurrent import futures
import logging

import discord
from discord.ext import commands

from gumo import config
from gumo import emoji

LOG = logging.getLogger(__name__)

GLOBAL_EXTENSIONS = ['help', 'admin']

DEFAULT_COMMAND_PREFIX = "!"
DEFAULT_EXTENSIONS = ['ori.rando.seedgen', 'ori.rando.logic_helper', 'ori.guild']


async def get_prefix(bot, message):
    if isinstance(message.channel, discord.DMChannel):
        prefix = DEFAULT_COMMAND_PREFIX
    else:
        prefix = config.get('COMMAND_PREFIX', DEFAULT_COMMAND_PREFIX, guild_id=message.guild.id)
    return commands.when_mentioned_or(prefix)(bot, message)


class Bot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, command_prefix=get_prefix, **kwargs)
        self.pool = None
        self.remove_command('help')
        self.add_check(self.check_extension_access)
        self.load_extensions()

    async def on_ready(self):
        LOG.debug(f"Bot is connected | username: {self.user} | user id: {self.user.id}")
        LOG.debug(f"Guilds: {', '.join(f'{guild.name}#{guild.id}' for guild in self.guilds)}")

    async def on_command(self, ctx):
        _repr = ctx.channel.recipient if isinstance(ctx.channel, discord.DMChannel) \
            else f"{ctx.guild.name}#{ctx.channel.name}"
        LOG.debug(f"[{_repr}] Command called by '{ctx.author.display_name}': '{ctx.message.content}'")

    async def check_extension_access(self, ctx):

        if isinstance(ctx.channel, discord.DMChannel):
            return True

        extension_name = ctx.cog.__module__.split(".", 2)[-1]

        whitelist = GLOBAL_EXTENSIONS + config.get('EXTENSIONS', DEFAULT_EXTENSIONS, guild_id=ctx.guild.id)
        return any(extension_name.startswith(name) for name in whitelist)

    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command."""

        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.CommandNotFound,)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        if not isinstance(error, (commands.CommandOnCooldown, futures.TimeoutError)):
            ctx.command.reset_cooldown(ctx)

        if isinstance(error, commands.MissingRequiredArgument):
            LOG.warning(f"Missing argument in command {ctx.command}: {error.args}")
            await ctx.invoke(self.get_command('help'), command_name=ctx.command.qualified_name)
        elif isinstance(error, commands.CommandOnCooldown):
            LOG.warning(f"'{ctx.author.name}' tried to use the command '{ctx.command.name}' while it "
                        f"was still on cooldown for {round(error.retry_after, 2)}s")
            await ctx.message.add_reaction(emoji.ARROWS_COUNTERCLOCKWISE)
        elif isinstance(error, commands.CheckFailure):
            LOG.error(f"Check failed: {error.args[0]} ({type(error).__name__})")
        else:
            LOG.warning(f"Exception '{type(error).__name__}' raised in command '{ctx.command}'",
                        exc_info=(type(error), error, error.__traceback__))

    async def on_raw_reaction_add(self, payload):
        channel = self.get_channel(payload.channel_id)
        user = self.get_user(payload.user_id)

        message = await channel.fetch_message(payload.message_id)
        payload_emoji = payload.emoji.name
        author = message.author

        is_bot_message = author.id == self.user.id
        is_bot_reaction = user.id == self.user.id

        if is_bot_message and not is_bot_reaction and payload_emoji == emoji.WASTEBASKET and await self.is_owner(user):
            await message.delete()

    async def start(self, *args, **kwargs):
        try:
            token = config.glob['DISCORD_BOT_TOKEN']
            await super().start(token, *args, **kwargs)
        except ConnectionError:
            LOG.exception("Cannot connect to the websocket")

    def load_extensions(self):
        """Load all the extensions"""
        extensions_to_load = config.extensions_to_load
        for extension in set(GLOBAL_EXTENSIONS + DEFAULT_EXTENSIONS + list(extensions_to_load)):
            extension = f"gumo.cogs.{extension}"
            if extension in self.extensions:
                LOG.debug(f"The extension '{extension}' is already loaded")
                continue
            try:
                self.load_extension(extension)
                LOG.debug(f"The extension '{extension}' has been successfully loaded")
            except (discord.ClientException, ModuleNotFoundError):
                LOG.exception(f"Failed to load extension '{extension}'")
