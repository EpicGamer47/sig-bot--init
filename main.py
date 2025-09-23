import discord
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
clientG = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    if message.content.startswith('$prompt'):
        response = clientG.models.generate_content(
            model="gemini-2.5-flash", 
            contents=message.content.split(' ', 1)[1],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
            ),
        )

        await message.reply(response.candidates[0].content.parts[0].text)
        
client.run(os.getenv('DISCORD_BOT_TOKEN'))
