import logging

import multidict
from discord.ext import commands

from gumo.cogs.utils import role

LOG = logging.getLogger(__name__)


class PronounRoleCommands(role.RoleCommands):

    GUILD_ID = 116250700685508615
    ROLES = ["He/Him", "She/Her", "They/Them"]

    def __init__(self, bot):
        super(PronounRoleCommands, self).__init__()
        self.display_name = "Pronoun roles"
        self.bot = bot
        self.roles = multidict.CIMultiDict(**{role_name: role_name for role_name in self.ROLES})
        self.guild = None

    async def on_ready(self):
        self.guild = self.bot.get_guild(self.GUILD_ID)

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
        await self.add_roles(ctx, *valid_pronouns, guild=self.guild)

    @pronoun.command(name='remove', aliases=['rm'])
    async def remove_pronouns(self, ctx):
        await self.remove_roles(ctx, *self.ROLES, guild=self.guild)


def setup(bot):
    bot.add_cog(PronounRoleCommands(bot))
