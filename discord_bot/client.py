import logging

from discord.ext import commands

from discord_bot import log
from discord_bot import utils

LOG = logging.getLogger('debug')

INITIAL_EXTENSIONS = ['stream.setup', 'sr']


class Bot(commands.Bot):

    # BOT EVENTS #
    async def on_ready(self):
        LOG.debug("Bot is connected | user id: {bot_id} | username: {bot_name}"
                  .format(bot_id=self.user.id, bot_name=self.user))
        self.load_extensions()

    # BOT ACTIONS #
    def load_extensions(self):
        """Load all the extensions"""
        extension_module_name = "{project_name}.cogs".format(project_name=utils.get_project_name())
        for extension in INITIAL_EXTENSIONS:
            try:
                self.load_extension(extension_module_name + "." + extension)
                LOG.debug("The extension '{extension}' has been successfully loaded"
                          .format(extension=extension.split(".")[0]))
            except Exception as e:
                message = "Failed to load extension '{extension}'".format(extension=extension.split(".")[0])
                LOG.error(log.get_log_exception_message(message, e))

    async def say(self, channel, message):
        await channel.send("```" + message + "```")
