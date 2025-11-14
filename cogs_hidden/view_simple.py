import discord
from discord.ui import View, Button
from discord.ext import commands
import json

class SimpleView(View):
    def __init__(self, *, timeout=60):
        super().__init__(timeout=timeout)
        self.click_count = 0

    @discord.ui.button(label="Click Me!", style=discord.ButtonStyle.green, emoji="👋")
    async def hello_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"Hello, {interaction.user.mention}!",
            ephemeral=True # only visible to button presser
        )

    @discord.ui.button(label="Count: 0", style=discord.ButtonStyle.blurple, emoji="🔢")
    async def count_button(self, interaction: discord.Interaction, button: Button):
        self.click_count += 1
        button.label = f"Count: {self.click_count}"
        
        await interaction.response.edit_message(view=self)
        
    async def on_timeout(self):
        for item in self.children:
            if item is discord.Button:
                item.style = discord.ButtonStyle.gray 
                
            item.disabled = True 
        
        # checks if message was deleted before trying to update it
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            
class ViewsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="menu", description="Displays a message with buttons.")
    async def menu(self, ctx: commands.Context):
        view = SimpleView()
        
        await ctx.send(
            "Click a button!",
            view=view
        )