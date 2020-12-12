import logging

from discord.ext import commands

LOG = logging.getLogger(__name__)

GUILD_ID = 356253023275581442

ROLES = {
    'graine': 356253780678934532,
    'germe': 748493294845034570,
    'pomme de terre': 748493403829960784,
    'frites': 748493454040104962,
    'poutine': 748493495466983424,
    'ohpuree': 748493539402448927,
    'tartiflette': 748493586454151248,
    'raclette': 748493631702302771,
}


class JulganeGuildCommands(commands.Cog):

    def __init__(self, bot):
        self.display_name = "Julgane guild commands"
        self.bot = bot
        self.guild = None
        self.roles = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.guild or self.bot.get_guild(GUILD_ID)
        self.roles = {name: self.guild.get_role(id) for name, id in ROLES.items()}
        for member in self.guild.members:
            if self.roles['graine'] not in member.roles:
                await member.add_roles(self.roles['graine'])
                LOG.debug(f"The role '{self.roles['graine'].name}' has been given to '{member.name}'")

    @commands.Cog.listener()
    async def on_member_join(self, member):

        if not member.guild.id == GUILD_ID:
            return

        await member.add_roles(self.roles['graine'])
        LOG.debug(f"'{member.name}' just joined, the role '{self.roles['graine'].name}' has been given")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):

        if not after.guild.id == GUILD_ID or before.roles == after.roles:
            return

        added_rank_roles = [role for role in after.roles if role not in before.roles and
                            role in self.roles.values() and not role == self.roles['graine']]

        if not added_rank_roles or added_rank_roles == [self.roles['graine']]:
            return

        old_rank_roles = [role for role in after.roles if role in self.roles.values()
                          and role not in added_rank_roles]

        await after.remove_roles(*old_rank_roles)

        LOG.debug(f"'{after.name}' acquired the roles {', '.join([role.name for role in added_rank_roles])}, "
                  f"the roles {', '.join([role.name for role in old_rank_roles])}' have been removed")


def setup(bot):
    bot.add_cog(JulganeGuildCommands(bot))
