import collections

from discord.ext import commands
from discord.ext.commands import converter

EXCLUDED_COMMANDS = ['help']


async def _can_run(ctx, cmd):
    try:
        return await cmd.can_run(ctx)
    except commands.CommandError:
        return False


class Help(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx, *, command_name=None):

        if not command_name:
            output = await self._help_global(ctx)
        else:
            cmd = self.bot.get_command(command_name)
            if not cmd or cmd.name in EXCLUDED_COMMANDS or cmd.hidden or not await _can_run(ctx, cmd):
                return
            if isinstance(cmd, commands.GroupMixin):
                output = await self._help_group(ctx, cmd)
            else:
                output = await self._help_command(ctx, cmd)

        if output:
            await ctx.send(output)

    async def _help_global(self, ctx):
        filtered_commands = [cmd for cmd in self.bot.commands
                             if cmd.name not in EXCLUDED_COMMANDS
                             and not cmd.hidden
                             and await _can_run(ctx, cmd)]

        command_tree = collections.defaultdict(list)

        for cmd in filtered_commands:
            cog_name = getattr(cmd.cog, "display_name", cmd.cog_name)
            command_tree[cog_name].append(cmd)

        output = ""
        for cog_name in sorted(command_tree):
            cmds = command_tree[cog_name]
            formatted_cmds = [f"`{cmd.name}`" for cmd in sorted(cmds, key=lambda cmd: cmd.name)]
            output += f"**{cog_name}**\n"
            output += ", ".join(formatted_cmds) + "\n\n"

        return output

    async def _help_group(self, ctx, cmd):
        output = getattr(cmd, 'help', "") + "\n\n"
        if getattr(cmd, 'invoke_without_command', False):
            usage = cmd.usage or f"{cmd.name} {cmd.signature}"
            output += f"**Usage:** `{ctx.prefix}{usage}`\n\n"
        output = await converter.clean_content().convert(ctx, output)

        formatted_cmds = [f"‣ `{cmd.name}`" for cmd in sorted(cmd.commands, key=lambda cmd: cmd.name)]
        output += f"**Commands** (_type `!{cmd.name} <command>` with `<command>` a command from the list_):\n"
        for formatted_cmd in formatted_cmds:
            output += formatted_cmd + "\n"

        return output

    async def _help_command(self, ctx, cmd):
        output = getattr(cmd, 'help', "") + "\n\n"
        usage = cmd.usage or f"{cmd.name} {cmd.signature}"
        output += f"**Usage:** `{ctx.prefix}{usage}`"
        output = await converter.clean_content().convert(ctx, output)
        return output


def setup(bot):
    bot.add_cog(Help(bot))
