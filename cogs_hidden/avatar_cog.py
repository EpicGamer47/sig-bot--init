import discord
from discord.ui import Label, View, Button, TextInput, Modal
from discord.ext import commands
from discord import app_commands
import json
import time
import functools
import math
import copy
from typing import Union

class AvatarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(help="Get someone's avatar")
    @app_commands.describe(
        user_fuck_gemini="The users whos avatar to get"
    )
    async def avatar2(self, ctx: commands.Context, user_fuck_gemini: discord.User):
        await ctx.reply(f"{user_fuck_gemini.mention}'s avatar: {user_fuck_gemini.display_avatar.url}",
                  ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AvatarCog(bot))