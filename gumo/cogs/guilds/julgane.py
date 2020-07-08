import logging

import discord
from discord.ext import commands

from gumo.cogs.utils import role

LOG = logging.getLogger(__name__)

GUILD_ID = 356253023275581442
PODE_ROLE = 356253780678934532


class JulganeGuildCommands(commands.Cog, role.RoleCommands):

    def __init__(self, bot):
        self.display_name = "Julgane guild commands"
        self.bot = bot
        self.guild = None
        self.pode_role = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)
        self.pode_role = self.pode_role or self.guild.get_role(PODE_ROLE)
        for member in self.guild.members:
            if not self.pode_role in member.roles:
                await member.add_roles(self.pode_role)
                LOG.debug(f"The role '{self.pode_role.name}' has been given to '{member.name}'")


    @commands.Cog.listener()
    async def on_member_join(self, member):

        if not member.guild.id == GUILD_ID:
            return

        self.pode_role = member.guild.get_role(PODE_ROLE)
        await member.add_roles(self.pode_role)
        LOG.debug(f"'{member.name}' just joined, the role '{self.pode_role.name}' has been given")

def setup(bot):
    bot.add_cog(JulganeGuildCommands(bot))
