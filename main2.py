import discord
import requests
import json
from discord.ui import View, Button
from discord.ext import commands
from discord import app_commands
import json
from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt
import numpy as np
import random

load_dotenv()

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

with open("data/prefixes.json") as p:
    prefixes = json.load(p)

with open("data/data.json") as p:
    bot_data = json.load(p)

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

bot.prefixes = prefixes
bot.bot_data = bot_data

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
    elif isinstance(error, commands.CommandOnCooldown):
        '''do nothing'''
    else:
        await ctx.send(f"An unexpected error occurred: {error}")
        raise error

@commands.hybrid_command(help="Ban a user by mention, ID, or selection. Optionally add a reason.")
@commands.has_permissions(ban_members=True)
@app_commands.describe(
    user="The user to ban (mention, ID, or pick from menu)",
    reason="Optional reason for the ban"
)
async def ban(ctx: commands.Context, user: discord.User, *, reason: str = None):
    try:
        reason = f"Banned by {ctx.author}: {reason}"
        await ctx.guild.ban(user, reason=reason)
        await ctx.send(f"Banned **{user.name}**. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"Error: Could not ban user because `{e}`")

@commands.hybrid_command(help="Unban a user by ID. Optionally add a reason.")
@commands.has_permissions(ban_members=True)
@app_commands.describe(
    user_id="The ID of the user to unban",
    reason="Optional reason for the unban"
)
async def unban(ctx: commands.Context, user_id: str, *, reason: str = None):
    try:
        user = await bot.fetch_user(int(user_id.strip('<@!>')))
        reason = f"Unbanned by {ctx.author}: {reason}"
        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f"Unbanned **{user.name}**. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"Error: Could not unban user because `{e}`")

@commands.hybrid_command(help="Change the prefix the bot uses, for the whole server")
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

@commands.hybrid_command(help="React to a message")
@app_commands.describe(
    emoji="The emoji to react with"
)
async def react(ctx: commands.Context, emoji: str):
    try:
        await ctx.message.add_reaction(emoji)
    except Exception as e:
        await ctx.send(f"Error: Could not react to the message because `{e}`")


@commands.hybrid_command(name="repeat", 
                         help="send message on webhook")
@app_commands.describe(
    message="Optional reason for the unban"
)
async def echo(ctx: commands.Context, *, message: str = ""):
    try:
        payload = {
            "content": message
        }
        
        url = "https://discord.com/api/webhooks/1422301965861523487/pNNLM_To92uE3G9pu6lUqAXy5oTl2sN38qvkC4tl_us5Y7PUB9qftgsMuMFxzoJSHyY3"
        response = requests.post(url, json=payload)

        await ctx.reply(response)
    except Exception as e:
        await ctx.send(f"Error: Could not unban user because `{e}`")

@commands.hybrid_command(help="get a dog")
async def dog(ctx: commands.Context):
    try:
        url = "https://dog.ceo/api/breeds/image/random"
        response = requests.get(url)

        await ctx.reply(response.json()["message"])
    except Exception as e:
        await ctx.send(f"Error: Could not unban user because `{e}`")

MAX_FILES = 1

def savefig(save_path):
    if (len(bot_data["images"]) >= MAX_FILES):
        recent = bot_data["images"].pop(0)
        os.remove(recent)    
        print('delted file at: ' + recent)

    plt.savefig(save_path)

    if save_path in bot_data["images"]:
        bot_data["images"].remove(save_path)
        
    bot_data["images"].append(save_path)

    with open("data/data.json", 'w') as p:
        p.write(json.dumps(bot_data))

def dogeplot(ctx, savings_values):
    # --- Plotting ---
        # Using subplots is good practice as it gives direct access to the axes object `ax`
        fig, ax = plt.subplots()

        # Create the horizontal box plot
        # vert=False makes it horizontal
        # patch_artist=True is required to fill the box with color
        bplot = ax.boxplot(savings_values, vert=False, patch_artist=True)

        # --- Apply Rainbow Coloring Scheme ---
        # Get a rainbow colormap ('jet' is a classic rainbow)
        cmap = plt.get_cmap('jet')
        # Create a list of 5 evenly spaced colors from the colormap
        colors = cmap(np.linspace(0, 1, 5))

        # Set the colors for each part of the box plot
        bplot['boxes'][0].set_facecolor(colors[0])      # Box fill
        bplot['medians'][0].set_color(colors[4])         # Median line
        bplot['fliers'][0].set_markerfacecolor(colors[2]) # Outliers
        bplot['fliers'][0].set_markeredgecolor(colors[2])
        
        # Whiskers and caps come in pairs, so we loop through them
        for whisker in bplot['whiskers']:
            whisker.set_color(colors[1])
        for cap in bplot['caps']:
            cap.set_color(colors[3])

        # --- Apply Exponential (Log) Scale and Labels ---
        # Set the x-axis to a logarithmic scale
        ax.set_xscale('log')
        
        # Add title and new horizontal label
        ax.set_title("Box Plot of Savings (Log Scale)")
        ax.set_xlabel("Savings")

        # --- Save the Plot ---
        output_dir = f"temp/{ctx.author.id}"
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, "savings_boxplot.png")
        
        savefig(save_path)
        print(f"Plot successfully saved to: {save_path}")

        # Close the figure to free up memory
        plt.close(fig)

@commands.hybrid_command(help="get a dog")
@commands.cooldown(1, 15,
                   commands.BucketType.guild)
@app_commands.describe(
    endpoint="Choose between grants, contracts and leases",
    sort_by="The field to sort by",
    sort_order="The order to sort by, Available values: asc, desc",
    page="The page number to check",
    per_page="The number of items per page from 1 to 500"
)
async def doge(ctx: commands.Context, 
               endpoint: str,
               sort_by="savings", 
               sort_order="desc", 
               page=1, 
               per_page=10):
    # try:
        if not endpoint in ['grants', 'contracts', 'leases']:
            raise ValueError("endpoint was not grants, contracts or leases")

        payload = {
            "sort_by": sort_by,
            "sort_order": sort_order, 
            "page": page,
            "per_page": per_page
        }

        print(payload)
        
        url = "https://api.doge.gov/savings/" + endpoint
        response = requests.get(url, params=payload)
        data = response.json()

        print(response)
        print(response.url)

        savings_values = [v["savings"] for v in data["result"][endpoint]] 

        print(savings_values)

        dogeplot(ctx, savings_values)

        await ctx.channel.send(content="Your analysis here:", 
                         file = discord.File(f"temp/{ctx.author.id}/savings_boxplot.png"))
        
        output = [v["savings"] for v in data["result"][endpoint]] 

        await ctx.channel.send(f"Top 10 resutls on page:")

        # with open(f"temp/{ctx.author.id}/data.txt")) as p:
        #     p.write(json.dumps(data))

        # await ctx.reply("full results",
                        # file = discord.File(f"temp/{ctx.author.id}/data.txt"))
    # except Exception as e:
    #     await ctx.send(f"Error: Could not unban user because `{e}`")


# Register all commands
# Must be done manually -_-
bot.add_command(ban)
bot.add_command(unban)
bot.add_command(change_prefix)
bot.add_command(echo)
bot.add_command(dog)
bot.add_command(react)
bot.add_command(doge)

bot.run(os.getenv('DISCORD_BOT_TOKEN'))
