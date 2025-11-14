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

def compute_rsi(data, window=14):
        delta = data['Close'].diff()
        print(delta)
        gain = delta.clip(lower=0)
        print("Gain: ", gain)
        loss = -delta.clip(upper=0)
        print("Loss: ", loss)

        avg_gain = gain.rolling(window=window, min_periods=window).mean()
        print("Avg_gain: ", avg_gain)
        avg_loss = loss.rolling(window=window, min_periods=window).mean()
        print("AVG_LOSS: ", avg_loss)

        rs = avg_gain / avg_loss
        print("RS: ", rs)
        data['RSI'] = 100 - (100 / (1 + rs))
        print("data[RSI]: ", data['RSI'])
        
        return data

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
        
        data['EMA20'] = data['Close'].ewm(span=20, min_periods=1).mean() #short term
        data['EMA50'] = data['Close'].ewm(span=50, min_periods=1).mean() #long term
        
        data.tail()

        data[['Close', 'MA20', 'MA50', 'EMA20', 'EMA50']].plot(figsize=(10,6))

        output_dir = f"temp/{ctx.author.id}"
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, "savings_boxplot.png")
        
        plt.savefig(save_path)
        await ctx.channel.send(content=f"Your analysis for {ticker}:", 
                         file = discord.File(f"temp/{ctx.author.id}/savings_boxplot.png"))
            
    @commands.hybrid_command(help="Analyze a ticker using rsi")
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @app_commands.describe(
        ticker="The ticker to analyze."
    )
    async def rsi(self, ctx: commands.Context, ticker:str):
        data = yf.download(ticker, start="2025-01-01", end="2025-10-01")
        data.head()

        compute_rsi(data)
        data.tail()

        data[['RSI']].plot(figsize=(10,6))

        output_dir = f"temp/{ctx.author.id}"
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, "savings_boxplot.png")
        
        plt.savefig(save_path)
        await ctx.channel.send(content=f"Your analysis for {ticker}:", 
                         file = discord.File(f"temp/{ctx.author.id}/savings_boxplot.png"))



async def setup(bot: commands.Bot):
    await bot.add_cog(Fin5Cog(bot))