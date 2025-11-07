import discord
from discord.ui import Label, View, Button, Modal, TextInput, Thumbnail
from discord.ext import commands

class Questionnaire(Modal, title='Questionnaire Response'):
    answer = Label(text='Answer', component=TextInput(style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Thanks for your response, {self.name.component.value}!', ephemeral=True)

class MessageModal(Modal, title="Send a Message to Yourself"):
    message_input = TextInput(
        label="Your Message",
        placeholder="Type what you want me to send back to you in a DM...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_message = self.message_input.value
        try:
            await interaction.user.send(
                f"Echoing:\n\n> {user_message}"
            )
            await interaction.response.send_message(
                "Sent DM", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "DM unsent due to user settings", ephemeral=True
            )

class InteractiveView(View):
    def __init__(self, *, timeout=180):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Say Hello", style=discord.ButtonStyle.success, emoji="👋")
    async def hello_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(
            f"Hello, {interaction.user.mention}!", ephemeral=True
        )

    @discord.ui.button(label="Send me a DM", style=discord.ButtonStyle.secondary, emoji="✉️")
    async def open_modal_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(MessageModal())

# --- Define the Cog ---
class ModalCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="modal", description="Modal menu")
    async def menu(self, ctx: commands.Context):
        """Sends a message with a View that includes a button to open a modal."""
        view = InteractiveView()
        await ctx.send(
            "This is an interactive menu. Try sending yourself a DM!",
            view=view
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(ModalCog(bot))