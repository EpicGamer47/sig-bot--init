import discord
import json
from discord.ext import commands
from discord import app_commands
import json
from dotenv import load_dotenv
import os

load_dotenv()

# dont even try to understand this code
class MyHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="Help",
            description="Here are all the commands:",
            color=discord.Color.blurple()
        )

        # Prefix + hybrid commands
        for cog, cmds in mapping.items():
            filtered = await self.filter_commands(cmds, sort=True)
            if filtered:
                cog_name = getattr(cog, "qualified_name", "No Category")
                command_list = ", ".join([cmd.name for cmd in filtered])
                embed.add_field(name=cog_name, value=command_list, inline=False)

        # Slash-only commands (not hybrids)
        bot = self.context.bot
        slash_cmds = [cmd for cmd in bot.tree.get_commands() if cmd.name not in bot.commands]
        if slash_cmds:
            embed.add_field(
                name="Slash Commands (only)",
                value=", ".join([cmd.name for cmd in slash_cmds]),
                inline=False
            )

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"Help for `{command.name}`",
            description=command.help or "No description provided.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Usage",
            value=self.get_command_signature(command),
            inline=False
        )
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = discord.Embed(
            title=f"Help for group `{group.name}`",
            description=group.help or "No description provided.",
            color=discord.Color.orange()
        )
        subcommands = ", ".join([cmd.name for cmd in group.commands])
        if subcommands:
            embed.add_field(name="Subcommands", value=subcommands)
        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog):
        embed = discord.Embed(
            title=f"Help for cog `{cog.qualified_name}`",
            description=cog.description or "No description provided.",
            color=discord.Color.purple()
        )
        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        if filtered:
            embed.add_field(
                name="Commands",
                value=", ".join([cmd.name for cmd in filtered])
            )
        await self.get_destination().send(embed=embed)

with open("data/prefixes.json", "r") as p:
    prefixes = json.load(p)

with open("data/data.json", "r") as f:
    bot_data = json.load(f)

with open("data/attendance.json", "r") as f:
    attendance = json.load(f)
    
with open("data/stats2.json", "r", encoding="utf-8") as f:
    stats2 = json.load(f)

default_prefix = ">"

def prefix(bot, message):
    if message.guild is None:
        id = message.author.id
    else:
        id = message.guild.id
    return prefixes.get(f"{id}", default_prefix)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=prefix, 
                   intents=intents, 
                   help_command=MyHelpCommand())

# easiest way to gives cogs access
bot.prefixes = prefixes
bot.bot_data = bot_data
bot.attendance = attendance
bot.stats2 = stats2

async def setup_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"Loaded cog: {filename}")
            except Exception as e:
                print(f"Failed to load cog {filename}: {e}")

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    await setup_cogs()
    await bot.tree.sync(guild=discord.Object(id=os.getenv('TEST_GUILD_ID')))
    await bot.tree.sync()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

# no need for cleanup rn
# @bot.event
# async def on_disconnect():

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        missing = ", ".join([perm.replace("_", " ").title() for perm in error.missing_permissions])
        await ctx.send(
            f"You don’t have permission to use this command.\n"
            f"Required permissions: **{missing}**"
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`.")
    elif isinstance(error, commands.errors.CommandNotFound):
        '''do nothing'''
    else:
        await ctx.send(f"An unexpected error occurred: {error}")
        raise error

@commands.hybrid_command(help="Change the prefix the bot uses, for the whole server")
@commands.cooldown(1, 15, commands.BucketType.guild) # dont spam this please u will cause errors
@commands.has_permissions(manage_guild=True)
@app_commands.describe(
    prefix="The requested prefix",
)
async def change_prefix(ctx, prefix: str):
    id = ctx.guild.id
    prefixes[f"{id}"] = prefix
    with open("data/prefixes.json", 'w') as p:
        p.write(json.dumps(prefixes))
    await ctx.reply("Success!")
    
@bot.tree.command(description="Displays a list of all Commands")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message(bot.help_command.send_bot_help())
    
bot.add_command(change_prefix)
# bot.add_command(help)

bot.run(os.getenv('DISCORD_BOT_TOKEN'))