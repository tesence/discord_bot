import logging
import sys
import traceback

from discord.ext import commands

from discord_bot import cfg
from discord_bot import log
from discord_bot import utils

CONF = cfg.CONF
LOG = logging.getLogger('debug')

WASTEBASKET_EMOJI = "\N{WASTEBASKET}"


class Bot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super(Bot, self).__init__(*args, **kwargs)
        self.handled_exceptions = []

    async def on_ready(self):
        LOG.debug(f"Bot is connected | user id: {self.user.id} | username: {self.user}")
        self.load_extensions()

    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command.
        ctx   : Context
        error : Exception"""

        if hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)

        if isinstance(error, commands.MissingRequiredArgument):
            LOG.error(f"Missing argument in command {ctx.command}")
            message = "An argument is missing\n\n"
            message += f"{self.command_prefix}{ctx.command.signature}"
            await self.send(ctx.channel, message, code_block=True)
        elif type(error) not in self.handled_exceptions:
            LOG.error(f"Exception '{type(error).__name__}' raised in command '{ctx.command}':")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    async def on_raw_reaction_add(self, payload):
        channel = self.get_channel(payload.channel_id)
        user = channel.guild.get_member(payload.user_id)

        message = await channel.get_message(payload.message_id)
        emoji = payload.emoji.name
        author = message.author
        has_embeds = bool(message.embeds)

        is_bot_message = author.id == self.user.id
        is_bot_reaction = user.id == self.user.id

        if is_bot_message and not is_bot_reaction and emoji == WASTEBASKET_EMOJI and utils._is_admin(user):
            await message.delete()
            LOG.debug(f"{user.name} has deleted the message '{message.content}' from {message.author.name} "
                      f"(has_embeds={has_embeds})")

    async def start(self, *args, **kwargs):
        try:
            await super(Bot, self).start(*args, **kwargs)
        except ConnectionError as e:
            message = "Cannot connect to the websocket"
            LOG.error(log.get_log_exception_message(message, e))

    def load_extensions(self):
        """Load all the extensions"""
        extension_module_name = f"{utils.get_project_name()}.cogs"
        for extension in CONF.LOADED_EXTENSIONS:
            try:
                self.load_extension(extension_module_name + "." + extension)
                LOG.debug(f"The extension '{extension.split('.')[0]}' has been successfully loaded")
            except Exception as e:
                message = f"Failed to load extension '{extension.split('.')[0]}'"
                LOG.error(log.get_log_exception_message(message, e))

    async def send(self, channel, message, embed=None, code_block=False):
        if code_block:
            message = utils.code_block(message)
        message = await channel.send(message, embed=embed)
        await message.add_reaction(WASTEBASKET_EMOJI)
        return message
