from concurrent import futures
import logging
import random

from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from discord import utils as discord_utils

from gumo.cogs.utils import role
from gumo import config
from gumo import db
from gumo import utils

LOG = logging.getLogger('bot')

DAB_COOLDOWN = 180
DEFAULT_SWITCH_COOLDOWN = 600


def check_undabable_role(ctx):
    role_name = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
    return role_name and discord_utils.get(ctx.guild.roles, name=role_name)


def _has_undabable_role(ctx):
    role_name = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
    role = discord_utils.get(ctx.guild.roles, name=role_name)
    return role in ctx.author.roles


def has_undabable_role(ctx):
    return _has_undabable_role(ctx)


def has_not_undabable_role(ctx):
    return not _has_undabable_role(ctx)


class DabCommands(role.RoleCommands):

    def __init__(self, bot):
        super(DabCommands, self).__init__()
        self.display_name = "Dab"
        self.bot = bot
        self.driver = db.DabDBDriver(bot)
        self.switch_cd = commands.CooldownMapping.from_cooldown(1, DEFAULT_SWITCH_COOLDOWN, commands.BucketType.member)
        self.role = None

    async def on_ready(self):
        await self.driver.init()

    async def __local_check(self, ctx):
        cmd = ctx.command

        if cmd.name not in ('dabable', 'undabable'):
            return True

        bucket = self.switch_cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(cooldown=bucket, retry_after=retry_after)

        return True

    @commands.command()
    @commands.guild_only()
    @commands.check(has_not_undabable_role)
    @commands.cooldown(1, DAB_COOLDOWN, BucketType.member)
    async def dab(self, ctx, *, dabbed):
        """Disrespect someone"""

        channel_repr = utils.get_channel_repr(ctx.channel)
        undabable_role = discord_utils.get(ctx.guild.roles, name=config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id))
        target_members = [m for m in ctx.message.mentions]
        cls = commands.clean_content()

        if undabable_role:
            for target_member in target_members[:]:
                if undabable_role in target_member.roles:
                    cleaned_target_member_name = await cls.convert(ctx, target_member.display_name)
                    dabbed = dabbed.replace(target_member.mention, f"~~@{cleaned_target_member_name}~~")
                    target_members.remove(target_member)

        amount = random.randint(0, 100)
        cleaned_author_name = await cls.convert(ctx, ctx.author.display_name)
        answer = f"{cleaned_author_name} dabs on {dabbed} **{amount}** times!"
        LOG.debug(f"[{channel_repr}] {answer}")
        message = await self.bot.send(ctx.channel, f"{cleaned_author_name} dabs on {dabbed} **{amount}** times!")
        await self.driver.insert_dabs(ctx.guild.id, ctx.author, amount, ctx.message.created_at, *target_members)

        def check(m):
            return m.author.id == ctx.author.id and m.content.replace(ctx.prefix, '') == "reroll"
        try:
            reroll = await self.bot.wait_for('message', check=check, timeout=30.0)
        except futures.TimeoutError:
            LOG.debug(f"[{channel_repr}] {ctx.author} did not reroll his last dab")
            return
        else:
            new_amount = random.randint(0, 100)
            LOG.debug(f"[{channel_repr}] {ctx.author} has rerolled his/her last dab {amount} -> {new_amount}")
            await message.edit(content=f"{cleaned_author_name} dabs on {dabbed} ~~{amount}~~ **{new_amount}** times!")
            await self.driver.reroll_dabs(ctx.guild.id, ctx.author, new_amount, ctx.message.created_at, reroll.created_at)

    @commands.command()
    @commands.guild_only()
    @commands.check(check_undabable_role)
    @commands.check(has_undabable_role)
    async def dabable(self, ctx):
        """ALlow people to dab on you (default)"""
        self.role = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
        await self.remove_roles(ctx, self.role)

    @commands.command()
    @commands.guild_only()
    @commands.check(check_undabable_role)
    @commands.check(has_not_undabable_role)
    async def undabable(self, ctx):
        """Prevent people from dabbing on you"""
        self.role = config.get('UNDABABLE_ROLE', guild_id=ctx.guild.id)
        await self.add_roles(ctx, self.role)


def setup(bot):
    bot.add_cog(DabCommands(bot))
