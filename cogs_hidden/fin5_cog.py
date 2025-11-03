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
import yfinance as yf
import pandas as pd

class Fin5Cog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.hybrid_command(help="Analyze a ticker using moving averages")
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @app_commands.describe(
        ticker="The ticker to analyze."
    )
    async def moving_average(self, ctx: commands.Context, ticker:str):
        data = yf.download(ticker, start="2025-01-01", end="2025-10-01")
        data.head()

        data['MA20'] = data['Close'].rolling(window=20, min_periods=1).mean() #short term
        data['MA50'] = data['Close'].rolling(window=50, min_periods=1).mean() #long term
        data.tail()

        data[['Close', 'MA20', 'MA50']].plot(figsize=(10,6))

        output_dir = f"temp/{ctx.author.id}"
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, "savings_boxplot.png")
        
        plt.savefig(save_path)
        await ctx.channel.send(content=f"Your analysis for {ticker}:", 
                         file = discord.File(f"temp/{ctx.author.id}/savings_boxplot.png"))



async def setup(bot: commands.Bot):
    await bot.add_cog(Fin5Cog(bot))