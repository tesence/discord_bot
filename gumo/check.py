from discord.ext import commands

from gumo import config


class NotAdmin(commands.CheckFailure):
    """Exception when someone uses an admin command without being admin"""


async def is_owner(ctx):
    if not (await ctx.bot.is_owner(ctx.author)):
        raise commands.NotOwner("You do not own this bot.")
    return True


async def is_admin(ctx):

    # check is the user is owner
    if await ctx.bot.is_owner(ctx.author):
        return True

    admin_roles = [role.id for role in await ctx.bot.admin_role_db_driver.list(guild_id=ctx.guild.id)]
    author_roles = [role.id for role in ctx.author.roles]

    # if there is no admin role, returns True
    if admin_roles is None:
        return True

    if not set(author_roles) & set(admin_roles):
        raise NotAdmin("You do not have the admin rights.")

    return True
