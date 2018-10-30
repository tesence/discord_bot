import logging

from discord.ext import commands

from discord_bot import config
from discord_bot import Emoji
from discord_bot import utils

LOG = logging.getLogger('bot')


class checks:

    OWNER_ID = 133313675237916672

    @staticmethod
    def is_admin(ctx):
        return checks._is_admin(ctx.author)

    @staticmethod
    def _is_admin(member):
        admin_roles = config.get('ADMIN_ROLES', guild_id=member.guild.id)
        if admin_roles is None or member.id == checks.OWNER_ID:
            return True
        author_roles = [role.name for role in member.roles]
        return set(author_roles) & set(admin_roles)


class Bot(commands.Bot):

    def __init__(self, *args, **kwargs):
        command_prefix = kwargs.pop('command_prefix')
        super(Bot, self).__init__(*args, command_prefix=commands.when_mentioned_or(command_prefix), **kwargs)
        self.add_check(self.check_extension_access)
        self.load_extensions()
        self.add_command(self.reload)

    async def on_ready(self):
        LOG.debug(f"Bot is connected | username: {self.user} | user id: {self.user.id}")
        LOG.debug(f"Guilds: {', '.join(f'{guild.name}#{guild.id}' for guild in self.guilds)}")

    async def on_command(self, ctx):
        LOG.debug(f"[{utils.get_channel_repr(ctx.channel)}] Command '{ctx.command.name}' called by "
                  f"'{ctx.author.display_name}': '{ctx.message.content}'")

    async def check_extension_access(self, ctx):
        if not getattr(ctx, 'cog'):
            return True
        extension_name = utils.get_extension_name_from_ctx(ctx)
        if extension_name in __file__:
            return True
        allowed_extensions = config.get('EXTENSIONS', guild_id=ctx.guild.id, default=True)
        if allowed_extensions is None:
            return True
        return extension_name in allowed_extensions

    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command."""

        if hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)

        channel_repr = utils.get_channel_repr(ctx.channel)
        if isinstance(error, commands.MissingRequiredArgument):
            LOG.warning(f"[{channel_repr}] Missing argument in command {ctx.command}: {error.message}")
            message = "An argument is missing\n\n"
            message += f"{ctx.command.signature}"
            await self.send(ctx.channel, message, code_block=True)
        elif isinstance(error, commands.CommandOnCooldown):
            LOG.warning(f"[{channel_repr}] '{ctx.author.name}' tried to use the command '{ctx.command.name}' while it "
                        f"was still on cooldown for {round(error.retry_after, 2)}s")
            await ctx.message.add_reaction(Emoji.ARROWS_COUNTERCLOCKWISE)
        elif isinstance(error, commands.CheckFailure):
            LOG.error(f"[{channel_repr}] The extension '{utils.get_extension_name_from_ctx(ctx)}' is not enabled on "
                      f"the guild '{ctx.guild.name}#{ctx.guild.id}'")
        else:
            LOG.warning(f"[{channel_repr}] Exception '{type(error).__name__}' raised in command '{ctx.command}'",
                        exc_info=(type(error), error, error.__traceback__))

    async def on_raw_reaction_add(self, payload):
        channel = self.get_channel(payload.channel_id)
        user = channel.guild.get_member(payload.user_id)

        message = await channel.get_message(payload.message_id)
        emoji = payload.emoji.name
        author = message.author
        embed = message.embeds[0] if message.embeds else None

        is_bot_message = author.id == self.user.id
        is_bot_reaction = user.id == self.user.id

        if is_bot_message and not is_bot_reaction and emoji == Emoji.WASTEBASKET and checks._is_admin(user):
            channel_repr = utils.get_channel_repr(channel)
            await message.delete()
            log = f"[{channel_repr}] {user.name} has deleted the message '{message.content}' from " \
                  f"{message.author.name} "
            if embed:
                log += f"(Embed fields: {embed.to_dict()['fields']})"
            LOG.debug(log)

    async def start(self, *args, **kwargs):
        try:
            await super(Bot, self).start(*args, **kwargs)
        except ConnectionError:
            LOG.exception("Cannot connect to the websocket")

    def load_extensions(self):
        """Load all the extensions"""
        extensions_to_load = config.get('EXTENSIONS', default=True)
        LOG.debug(f"Extensions to be loaded: {list(extensions_to_load)}")
        for extension in extensions_to_load:
            extension = f"cogs.{extension}"
            if extension in self.extensions:
                LOG.debug(f"The extension '{extension}' is already loaded")
                continue
            try:
                self.load_extension(extension)
                LOG.debug(f"The extension '{extension}' has been successfully loaded")
            except:
                LOG.exception(f"Failed to load extension '{extension}'")

    async def send(self, channel, content, reaction=False, code_block=False, **kwargs):
        if code_block:
            content = utils.code_block(content)
        message = await channel.send(content=content, **kwargs)
        if reaction:
            await message.add_reaction(Emoji.WASTEBASKET)
        return message

    @commands.command()
    async def reload(self, ctx):
        config.load()
        self.load_extensions()
