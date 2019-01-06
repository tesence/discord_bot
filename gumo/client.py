import logging

import discord
from discord.ext import commands

from gumo import config
from gumo import emoji
from gumo import utils

LOG = logging.getLogger('bot')

GLOBAL_EXTENSIONS = {'help', 'admin'}

DEFAULT_COMMAND_PREFIX = "!"
DEFAULT_EXTENSIONS = {'ori_rando.seedgen', 'ori_rando.logic_helper'}


async def get_prefix(bot, message):
    if isinstance(message.channel, discord.DMChannel):
        prefix = DEFAULT_COMMAND_PREFIX
    else:
        prefix = config.get('COMMAND_PREFIX', DEFAULT_COMMAND_PREFIX, guild_id=message.guild.id)
    return commands.when_mentioned_or(prefix)(bot, message)


class Bot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super(Bot, self).__init__(*args, command_prefix=get_prefix, **kwargs)
        self.pool = None
        self.remove_command('help')
        self.add_check(self.check_extension_access)
        self.load_extensions()

    async def on_ready(self):
        LOG.debug(f"Bot is connected | username: {self.user} | user id: {self.user.id}")
        LOG.debug(f"Guilds: {', '.join(f'{guild.name}#{guild.id}' for guild in self.guilds)}")

    async def on_command(self, ctx):
        LOG.debug(f"[{utils.get_channel_repr(ctx.channel)}] Command called by "
                  f"'{ctx.author.display_name}': '{ctx.message.content}'")

    async def check_extension_access(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            return True
        if not getattr(ctx, "cog"):
            return True
        extension_name = utils.get_extension_name_from_ctx(ctx)
        if extension_name in GLOBAL_EXTENSIONS:
            return True
        allowed_extensions = config.get('EXTENSIONS', DEFAULT_EXTENSIONS, guild_id=ctx.guild.id)
        return extension_name in allowed_extensions

    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command."""

        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.CommandNotFound,)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        channel_repr = utils.get_channel_repr(ctx.channel)
        if isinstance(error, commands.MissingRequiredArgument):
            LOG.warning(f"[{channel_repr}] Missing argument in command {ctx.command}: {error.args[0]}")
            message = "An argument is missing\n\n"
            message += f"{ctx.command.signature}"
            await self.send(ctx.channel, message, code_block=True)
        elif isinstance(error, commands.CommandOnCooldown):
            LOG.warning(f"[{channel_repr}] '{ctx.author.name}' tried to use the command '{ctx.command.name}' while it "
                        f"was still on cooldown for {round(error.retry_after, 2)}s")
            await ctx.message.add_reaction(emoji.ARROWS_COUNTERCLOCKWISE)
        elif isinstance(error, commands.CheckFailure):
            LOG.error(f"[{channel_repr}] Check failed: {error.args[0]} ({type(error).__name__})")
        else:
            LOG.warning(f"[{channel_repr}] Exception '{type(error).__name__}' raised in command '{ctx.command}'",
                        exc_info=(type(error), error, error.__traceback__))

    async def on_raw_reaction_add(self, payload):
        channel = self.get_channel(payload.channel_id)
        user = self.get_user(payload.user_id)

        message = await channel.get_message(payload.message_id)
        payload_emoji = payload.emoji.name
        author = message.author
        embed = message.embeds[0] if message.embeds else None

        is_bot_message = author.id == self.user.id
        is_bot_reaction = user.id == self.user.id

        if is_bot_message and not is_bot_reaction and payload_emoji == emoji.WASTEBASKET and await self.is_owner(user):
            channel_repr = utils.get_channel_repr(channel)
            await message.delete()
            log = f"[{channel_repr}] {user.name} has deleted the message '{message.content}' from {message.author.name}"
            if embed:
                log += f"(Embed fields: {embed.to_dict()['fields']})"
            LOG.debug(log)

    async def start(self, *args, **kwargs):
        try:
            token = config.creds['DISCORD_BOT_TOKEN']
            await super(Bot, self).start(token, *args, **kwargs)
        except ConnectionError:
            LOG.exception("Cannot connect to the websocket")

    def load_extensions(self):
        """Load all the extensions"""
        extensions_to_load = config.extensions_to_load
        for extension in GLOBAL_EXTENSIONS | DEFAULT_EXTENSIONS | extensions_to_load:
            extension = f"cogs.{extension}"
            if extension in self.extensions:
                LOG.debug(f"The extension '{extension}' is already loaded")
                continue
            try:
                self.load_extension(extension)
                LOG.debug(f"The extension '{extension}' has been successfully loaded")
            except (discord.ClientException, ModuleNotFoundError):
                LOG.exception(f"Failed to load extension '{extension}'")

    async def send(self, channel, content=None, reaction=False, code_block=False, **kwargs):
        if code_block:
            content = utils.code_block(content)
        message = await channel.send(content=content, **kwargs)
        if reaction:
            await message.add_reaction(emoji.WASTEBASKET)
        return message
