from .logic_helper import OriLogicHelperCommands
from .role import OriRandoRoleCommands
from .seedgen import OriRandoSeedGenCommands


def setup(bot):
    bot.add_cog(OriLogicHelperCommands(bot))
    bot.add_cog(OriRandoRoleCommands(bot))
    bot.add_cog(OriRandoSeedGenCommands(bot))
