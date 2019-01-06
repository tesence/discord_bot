import collections

import discord
from discord.ext import commands
from discord.ext.commands import converter

EXCLUDED_COMMANDS = ['help']


async def _can_run(ctx, cmd):
    try:
        return await cmd.can_run(ctx)
    except commands.CommandError:
        return False


class Help:

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx, *, command_name=None):

        if not command_name:
            embed = await self._help_global(ctx)
        else:
            cmd = self.bot.get_command(command_name)
            if not cmd or cmd.name in EXCLUDED_COMMANDS or cmd.hidden or not await _can_run(ctx, cmd):
                return
            if isinstance(cmd, commands.GroupMixin):
                embed = await self._help_group(ctx, cmd)
            else:
                embed = await self._help_command(ctx, cmd)

        if ctx.guild.me.color.value:
            embed.colour = ctx.guild.me.color
        embed.set_author(name="Gumo's help")
        await self.bot.send(ctx.channel, embed=embed)

    async def _help_global(self, ctx):
        filtered_commands = [cmd for cmd in self.bot.commands
                             if cmd.name not in EXCLUDED_COMMANDS
                             and not cmd.hidden
                             and await _can_run(ctx, cmd)]

        command_tree = collections.defaultdict(list)

        for cmd in filtered_commands:
            cog_name = getattr(cmd.instance, "display_name", cmd.cog_name)
            command_tree[cog_name].append(cmd)

        embed = discord.Embed()

        for cog_name in sorted(command_tree):
            cmds = command_tree[cog_name]
            formatted_cmds = [f"`{cmd.name}`" for cmd in sorted(cmds, key=lambda cmd: cmd.name)]
            embed.add_field(name=cog_name, value=", ".join(formatted_cmds), inline=False)
        embed.set_footer(text="Use '!help <command>' for more info on a command")

        return embed

    async def _help_group(self, ctx, cmd):
        desc = getattr(cmd, 'help', "")
        if getattr(cmd, 'invoke_without_command', False):
            desc += f"\n\n`{ctx.prefix}{cmd.usage or cmd.signature}`"
        desc = await converter.clean_content().convert(ctx, desc)
        embed = discord.Embed(description=desc)

        formatted_cmds = [f" ‣ `{cmd.name}`" for cmd in sorted(cmd.commands, key=lambda cmd: cmd.name)]
        embed.add_field(name="Commands", value="\n".join(formatted_cmds), inline=False)
        embed.set_footer(text="Use '!help <command>' for more info on a command")
        return embed

    async def _help_command(self, ctx, cmd):
        desc = getattr(cmd, 'help', "")
        desc += f"\n\n**Usage:** `{ctx.prefix}{cmd.usage or cmd.signature}`"
        desc = await converter.clean_content().convert(ctx, desc)
        embed = discord.Embed(description=desc)
        return embed


def setup(bot):
    bot.add_cog(Help(bot))
