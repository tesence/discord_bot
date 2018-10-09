import logging

from discord.ext import commands

from discord_bot import config
from discord_bot import Emoji
from discord_bot import utils

LOG = logging.getLogger('bot')

DEFAULT_LOADED_EXTENSIONS = ["stream", "dab", "ori_rando_seedgen", "ori_rando_role", "ori_logic_helper"]


class checks:

    OWNER_ID = 133313675237916672

    @staticmethod
    def is_admin(ctx):
        return checks._is_admin(ctx.author)

    @staticmethod
    def _is_admin(member):
        admin_roles = config.ADMIN_ROLES.get(member.guild.id, None)
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

    async def on_ready(self):
        LOG.debug(f"Bot is connected | user id: {self.user.id} | username: {self.user.name}")

    async def on_command(self, ctx):
        LOG.debug(f"Command '{ctx.command.name}' called by '{ctx.author.display_name}': '{ctx.message.content}'")

    async def check_extension_access(self, ctx):
        if not getattr(ctx, 'cog'):
            return True

        extension_name = utils.get_extension_name_from_ctx(ctx)
        extensions = config.LOADED_EXTENSIONS.get(ctx.guild.id)
        allowed_extensions = extensions if config.LOADED_EXTENSIONS.get(ctx.guild.id) else DEFAULT_LOADED_EXTENSIONS
        return extension_name in allowed_extensions

    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command."""

        if hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)

        if isinstance(error, commands.MissingRequiredArgument):
            LOG.warning(f"Missing argument in command {ctx.command}: {error.message}")
            message = "An argument is missing\n\n"
            message += f"{ctx.command.signature}"
            await self.send(ctx.channel, message, code_block=True)
        elif isinstance(error, commands.CommandOnCooldown):
            LOG.warning(f"{ctx.author.name} tried to use the command '{ctx.command.name}' while it was still on "
                        f"cooldown for {round(error.retry_after, 2)}s")
            await ctx.message.add_reaction(Emoji.ARROWS_COUNTERCLOCKWISE)
        elif isinstance(error, commands.CheckFailure):
            LOG.error(f"The extension '{utils.get_extension_name_from_ctx(ctx)}' is not enabled on the guild "
                      f"'{ctx.guild.name}#{ctx.guild.id}'")
        else:
            LOG.warning(f"Exception '{type(error).__name__}' raised in command '{ctx.command}'",
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
            await message.delete()
            log = f"{user.name} has deleted the message '{message.content}' from {message.author.name} "
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
        for extension in DEFAULT_LOADED_EXTENSIONS:
            try:
                extension = f"cogs.{extension}"
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
