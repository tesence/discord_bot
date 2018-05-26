import logging

from discord.ext import commands

from discord_bot import cfg
from discord_bot import log
from discord_bot import utils

CONF = cfg.CONF
LOG = logging.getLogger('debug')

WASTEBASKET_EMOJI = "\N{WASTEBASKET}"


class Bot(commands.Bot):

    # BOT EVENTS #
    async def on_ready(self):
        LOG.debug(f"Bot is connected | user id: {self.user.id} | username: {self.user}")
        self.load_extensions()

    # BOT ACTIONS #
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

    async def _send(self, channel, message, embed=None, code_block=False):
        if code_block:
            message = utils.code_block(message)
        message = await channel.send(message, embed=embed)
        await message.add_reaction(WASTEBASKET_EMOJI)

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
