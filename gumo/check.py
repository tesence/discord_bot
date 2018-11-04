from discord.ext import commands

from gumo import config


class NotAdmin(commands.CheckFailure):
    """Exception when someone uses an admin command without being admin"""


def is_owner():
    async def predicate(ctx):
        if not (await ctx.bot.is_owner(ctx.author)):
            raise commands.NotOwner("You do not own this bot.")
        return True
    return commands.check(predicate)


def is_admin():
    async def predicate(ctx):

        # check is the user is owner
        if await ctx.bot.is_owner(ctx.author):
            return True

        admin_roles = config.get('ADMIN_ROLES', guild_id=ctx.author.guild.id)
        author_roles = [role.name for role in ctx.author.roles]

        # if there is no admin role, returns True
        if admin_roles is None:
            return True

        if not set(author_roles) & set(admin_roles):
            raise NotAdmin("You do not have the admin rights.")

        return True
    return commands.check(predicate)
