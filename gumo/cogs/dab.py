import collections
from concurrent import futures
import logging
import random

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from discord import utils as discord_utils

from gumo.cogs.utils import role
from gumo import config
from gumo import db
from gumo import emoji
from gumo import utils

LOG = logging.getLogger(__name__)

DAB_COOLDOWN = 180
DEFAULT_SWITCH_COOLDOWN = 600

SWITCH_COOLDOWN = commands.CooldownMapping.from_cooldown(1, DEFAULT_SWITCH_COOLDOWN, commands.BucketType.member)


async def trigger_switch_cooldown(ctx):
    if ctx.invoked_with == 'help':
        return True

    bucket = SWITCH_COOLDOWN.get_bucket(ctx.message)
    retry_after = bucket.update_rate_limit()
    if retry_after:
        raise commands.CommandOnCooldown(cooldown=bucket, retry_after=retry_after)
    return True


def check_undabbable_role(ctx):
    role_name = config.get('UNDABBABLE_ROLE', guild_id=ctx.guild.id)
    return role_name and discord_utils.get(ctx.guild.roles, name=role_name)


def _has_undabbable_role(ctx):
    role_name = config.get('UNDABBABLE_ROLE', guild_id=ctx.guild.id)
    role = discord_utils.get(ctx.guild.roles, name=role_name)
    return role in ctx.author.roles


def has_undabbable_role(ctx):
    return _has_undabbable_role(ctx)


def has_not_undabbable_role(ctx):
    return not _has_undabbable_role(ctx)


class DabCommands(commands.Cog, role.RoleCommands):

    def __init__(self, bot):
        super().__init__()
        self.display_name = "Dab"
        self.bot = bot
        self.driver = db.DabDBDriver(bot)
        self.role = None

        bot.loop.create_task(self.driver.init())

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @commands.check(has_not_undabbable_role)
    @commands.cooldown(1, DAB_COOLDOWN, BucketType.member)
    async def dab(self, ctx, *, dabbed):
        """Disrespect someone"""

        undabbable_role = discord_utils.get(ctx.guild.roles, name=config.get('UNDABBABLE_ROLE', guild_id=ctx.guild.id))
        target_members = [m for m in ctx.message.mentions]
        cls = commands.clean_content()

        if undabbable_role:
            for target_member in target_members[:]:
                if undabbable_role in target_member.roles:
                    cleaned_target_member_name = await cls.convert(ctx, target_member.display_name)
                    dabbed = dabbed.replace(target_member.mention, f"~~@{cleaned_target_member_name}~~")
                    target_members.remove(target_member)

        amount = random.randint(0, 100)
        cleaned_author_name = await cls.convert(ctx, ctx.author.display_name)
        answer = f"{cleaned_author_name} dabs on {dabbed} **{amount}** times!"
        LOG.debug(f"{answer}")
        message = await ctx.send(f"{cleaned_author_name} dabs on {dabbed} **{amount}** times!")
        await message.add_reaction(emoji.RECYCLING)
        await self.driver.insert_dabs(ctx.guild.id, ctx.author, amount, ctx.message.created_at, *target_members)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == emoji.RECYCLING

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)
        except futures.TimeoutError:
            LOG.debug(f"{ctx.author} did not reroll his last dab")
            return
        else:
            new_amount = random.randint(0, 100)
            LOG.debug(f"{ctx.author} has rerolled his/her last dab {amount} -> {new_amount}")
            await message.edit(content=f"{cleaned_author_name} dabs on {dabbed} ~~{amount}~~ **{new_amount}** times!")
            await self.driver.reroll_dabs(ctx.guild.id, ctx.author, new_amount, ctx.message.created_at,
                                          reaction.message.created_at)

    @dab.command()
    @commands.cooldown(1, DAB_COOLDOWN, BucketType.member)
    async def stats(self, ctx, *, member: discord.Member=None):

        author = member or ctx.author
        records = await self.driver.get_user_data(ctx.guild.id, author.id)

        nemesis = collections.defaultdict(lambda: 0)
        victims = collections.defaultdict(lambda: 0)
        total_sum = 0

        unique_dates = []

        for r in records:

            amount = r['rerolled_amount'] or r['amount']

            if r['author_id'] == author.id:

                if r['created_at'] not in unique_dates:
                    total_sum += amount
                    unique_dates.append(r['created_at'])

                victims[r['target_id']] += amount

            if r['target_id'] == author.id:
                nemesis[r['author_id']] += amount

        output = f"Stats for **{author}**\n\n"
        output += f"Global number of dabs: {total_sum}\n"

        if nemesis:
            n_amount, nemesis_id = max(zip(nemesis.values(), nemesis.keys()) or 0)
            output += f"Nemesis: `{ctx.guild.get_member(nemesis_id)}` ({n_amount})\n"

        if victims:
            v_amount, victim_id = max(zip(victims.values(), victims.keys()) or 0)
            output += f"Victim: `{ctx.guild.get_member(victim_id)}` ({v_amount})\n"

        await ctx.send(output)

    @commands.command()
    @commands.guild_only()
    @commands.check(check_undabbable_role)
    @commands.check(has_undabbable_role)
    @commands.check(trigger_switch_cooldown)
    async def dabbable(self, ctx):
        """ALlow people to dab on you (default)"""
        self.role = config.get('UNDABBABLE_ROLE', guild_id=ctx.guild.id)
        await self.remove_roles(ctx, self.role)

    @commands.command()
    @commands.guild_only()
    @commands.check(check_undabbable_role)
    @commands.check(has_not_undabbable_role)
    @commands.check(trigger_switch_cooldown)
    async def undabbable(self, ctx):
        """Prevent people from dabbing on you"""
        self.role = config.get('UNDABBABLE_ROLE', guild_id=ctx.guild.id)
        await self.add_roles(ctx, self.role)


def setup(bot):
    bot.add_cog(DabCommands(bot))
