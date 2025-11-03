import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import google.genai as genai
from google.genai import types

class GeminiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        load_dotenv()
        self.gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY')) 
    
    @commands.hybrid_command(help="Send a prompt to the almighty Gemini.")
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @app_commands.describe(
        prompt = "The prompt to send Gemini"
    )
    async def prompt(self, ctx: commands.Context, *, prompt: str):
        response = self.gemini.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
            ),
        )

        await ctx.reply(response.candidates[0].content.parts[0].text)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeminiCog(bot))