import discord
from discord.ui import View, Button, Modal, TextInput, RoleSelect, UserSelect
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import random
from sheet_updater import update_sheet

import functools

load_dotenv()

# save json file & handle races
def save_json(filename: str, data: dict):
    unfinished = True
    delay = 1
    while unfinished and delay < 10:
        try:
            with open(filename, 'w') as f: 
                f.write(json.dumps(data))
            unfinished = False
        except IOError as e:
            time.sleep(2 + 3 * random.random())
            delay += 1
    
    if unfinished:
        print(f"Failed to save at {filename}")

def get_keys(sig: discord.Role, meeting: datetime):
    def get_ordinal_suffix(day): # we love stackoverflow
        if 4 <= day <= 20 or 24 <= day <= 30:
            return "th"
        else:
            return ["st", "nd", "rd"][day % 10 - 1]

    sig_key = str(sig.name)

    meeting = meeting.astimezone(ZoneInfo("America/New_York"))
    date = str(meeting.day) + get_ordinal_suffix(meeting.day)
    meeting_key = str(meeting.strftime(f"%a %b {date} %I:%M%p"))
    
    return (sig_key, meeting_key)

async def register(bot, sig: discord.Role, ucid: str, meeting: datetime):
    sig_key, meeting_key = get_keys(sig, meeting)

    if not ucid in bot.attendance[sig_key][meeting_key]:
        bot.attendance[sig_key][meeting_key].append(ucid)
    
    save_json("data/attendance.json", bot.attendance)

    ''''''

class UCIDModal(Modal, title="Check into your meeting!"):
    def __init__(self, bot: commands.Bot, ctx: commands.Context, sig: discord.Role, checkingIn=True):
        super().__init__()
        self.bot = bot
        self.ctx = ctx
        self.sig = sig
        self.checkingIn = checkingIn

    message_input = TextInput(
        label="Enter your UCID",
        placeholder='Example: "clb46"',
        style=discord.TextStyle.short,
        required=True,
        max_length=10,
    )

    async def check_in(self, interaction: discord.Interaction):
        ucid = self.bot.bot_data["ucids"][str(interaction.user.id)]
        
        await register(self.bot, self.sig, ucid, self.ctx.message.created_at)

        await interaction.response.send_message(
            f"Successfully registered user {ucid}!", ephemeral=True
        )

    async def on_submit(self, interaction: discord.Interaction):
        ucid = self.message_input.value
        ucid = ucid.lower()
        
        self.bot.bot_data["ucids"][str(interaction.user.id)] = ucid
        self.bot.bot_data["rev_ucids"][ucid] = str(interaction.user.id)

        if self.checkingIn:
            await self.check_in(interaction)
        else:
            await interaction.response.send_message(
                f"Successfully changed!", ephemeral=True
            )

        save_json("data/data.json", self.bot.bot_data)

        # with open("data/data.json", 'w') as f: 
        #     f.write(json.dumps(self.bot.bot_data))
        
class AttendanceView(View):
    def __init__(self, bot, ctx: commands.Context, sig: discord.Role, *, timeout=60*90):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.sig = sig
        self.ctx = ctx

        self.check_in_button = Button(
            label=f"Check into {self.sig.name}",  # only way to add signame into button
            style=discord.ButtonStyle.green,
            emoji=f"<{os.getenv('CHECK_IN_EMOJI')}>"
        )
        self.check_in_button.callback = self.check_in_callback
        
        self.get_attendance_button = Button(
            label=f"Get Attendance",
            style=discord.ButtonStyle.gray,
            emoji="📜"
        )
        self.get_attendance_button.callback = self.get_attendance_callback
        
        self.close_meeting_button= Button(
            label=f"Close Meeting",
            style=discord.ButtonStyle.red,
            emoji="🛑"
        )
        self.close_meeting_button.callback = self.close_meeting_callback

        self.add_item(self.check_in_button)
        self.add_item(self.get_attendance_button)
        self.add_item(self.close_meeting_button)

    # technically repeated method but this my makes life easier
    async def check_in(self, interaction: discord.Interaction):
        ucid = self.bot.bot_data["ucids"][str(interaction.user.id)]

        await register(self.bot, self.sig, ucid, self.ctx.message.created_at)

        await interaction.response.send_message(
            f"Successfully registered user {ucid}!", ephemeral=True
        )

    async def check_in_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) in self.bot.bot_data["ucids"]:
            await self.check_in(interaction)
        else:
            await interaction.response.send_modal(UCIDModal(self.bot, self.ctx, self.sig, True))
            
    async def close_meeting_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Closed registration!", ephemeral=True
        )
        
        await self.on_timeout()
            
    async def get_attendance_callback(self, interaction: discord.Interaction):
        sig_key, meeting_key = get_keys(self.sig, self.ctx.message.created_at)
        
        if not self.bot.attendance[sig_key][meeting_key]:
            await interaction.response.send_message(
                f"No one has attended the **{meeting_key}** meeting of {self.sig.mention} yet. Why don't you be the first?", 
                ephemeral=True
            )
            
            return
        
        result = f"The attendees for the **{meeting_key}** meeting of {self.sig.mention} are:"
        
        for ucid in self.bot.attendance[sig_key][meeting_key]:
            user_id = self.bot.bot_data["rev_ucids"][ucid]
            result += f"\n<@!{user_id}>, {ucid}"
        
        await interaction.response.send_message(
            result, 
            ephemeral=True
        )
        
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
            
            if item is discord.ui.Button:   
                item.style = discord.ButtonStyle.gray 

        # i dont want to clog my error stream
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            
class RoleSelectView(View):
    def __init__(self, callback):
        super().__init__(timeout=180)

        self.role_select = RoleSelect(
            placeholder="Select roles...",
            min_values=1,
            max_values=10
        )

        self.on_submit_callback = callback
        self.role_select.callback = self.internal_callback
        
        self.add_item(self.role_select)
        
    async def internal_callback(self, interaction: discord.Interaction):
        selected_roles = self.role_select.values
        
        self.role_select.disabled = True
        self.stop()
        
        await self.on_submit_callback(interaction, selected_roles, self)
        
    async def on_timeout(self): 
        self.role_select.disabled = True
        
        original_response = self.message
        if original_response:
            await original_response.edit(content="This command has expired.", view=self)
        
class UserSelectView(View):
    def __init__(self, callback):
        super().__init__(timeout=180)

        self.user_select = UserSelect(
            placeholder="Select users...",
            min_values=1,
            max_values=25
        )

        self.on_submit_callback = callback
        self.user_select.callback = self.internal_callback
        
        self.add_item(self.user_select)
        
    async def internal_callback(self, interaction: discord.Interaction):
        selected_users = self.user_select.values
        
        self.user_select.disabled = True
        self.stop()
        
        await self.on_submit_callback(interaction, selected_users, self)
        
    async def on_timeout(self): 
        self.user_select.disabled = True
        
        original_response = self.message
        if original_response:
            await original_response.edit(content="This command has expired.", view=self)

def generate_embed(ctx: commands.Context, sig: discord.Role):
    embed = discord.Embed(title=f"Meeting started for {sig.name}!",
                    description="**Click the button to register your attendance!**",
                    color=sig.color)

    embed.set_author(name=ctx.author.display_name,
                    icon_url=ctx.author.display_avatar.url)

    embed.add_field(name="",
                    value=f"Meeting started <t:{int(ctx.message.created_at.timestamp())}:R>\n" +
                        f"Registration ends <t:{int(ctx.message.created_at.timestamp()) + 60 * 60}:R>",
                    inline=False)
    
    return embed

def run_if(condition_check_func):
    def decorator(func_to_run):
        @functools.wraps(func_to_run)
        async def wrapper(*args, **kwargs):
            if await condition_check_func(*args, **kwargs):
                return await func_to_run(*args, **kwargs)
            else:
                raise PermissionError("User needs `manage_guild` permissions or bot admin role to use this command!")
        
        return wrapper
    return decorator

class AttendanceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    async def has_admin_perms(self, ctx: commands.Context, *args, **kwargs):
        bot_admins = [
            717451031897833512 # Chris B
        ]
        
        if ctx.author.id in bot_admins:
            return True
        
        if ctx.author.guild_permissions.manage_guild:   
            return True
        
        if not str(ctx.guild.id) in self.bot.bot_data["admin_roles"]:
            self.bot.bot_data["admin_roles"][str(ctx.guild.id)] = []
        
        for role in ctx.author.roles:
            if str(role.id) in self.bot.bot_data["admin_roles"][str(ctx.guild.id)]:
                return True
            
        return False
    
    
    @commands.hybrid_command(help="Start a SIG meeting!")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    @app_commands.describe(
        sig = "The SIG to make a meeting for."
    )
    async def start_meeting(self, ctx: commands.Context, sig: discord.Role):
        if not str(ctx.guild.id) in self.bot.bot_data["sig_roles"]:
            self.bot.bot_data["sig_roles"][str(ctx.guild.id)] = []
            
        if not str(sig.id) in self.bot.bot_data["sig_roles"][str(ctx.guild.id)]:
            await ctx.reply(
                f"{sig.mention} is not a valid sig! Please register this as a sig if you would like to start meetings with it.",
                ephemeral=True
            )
            return
        
        sig_key, meeting_key = get_keys(sig, ctx.message.created_at)
        
        if not sig_key in self.bot.attendance:
            self.bot.attendance[sig_key] = {}

        if not meeting_key in self.bot.attendance[sig_key]:
            self.bot.attendance[sig_key][meeting_key] = []
            
        save_json("data/attendance.json", self.bot.attendance)
        
        embed = generate_embed(ctx, sig)
        view = AttendanceView(self.bot, ctx, sig)
        
        view.message = await ctx.send(
            embed=embed,
            view=view
        )

    @commands.hybrid_command(help="Change your UCID")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @app_commands.describe(
        ucid = "Your new UCID"
    )
    async def change_ucid(self, ctx: commands.Context, ucid: str):
        ucid = ucid.lower()
        
        if str(ctx.author.id) in self.bot.bot_data["banned"]:
            await ctx.reply(
                f"You have been banned from changing your UCID! Contact a moderator to fix this.",
                ephemeral=True
            )
            
            return
        elif ucid in self.bot.bot_data["rev_ucids"]:
            user_id = self.bot.bot_data["rev_ucids"][ucid]
            
            await ctx.reply(
                f"<@!{user_id}> already has **{ucid}** as their UCID! If you believe they are impersonating you, please contact a moderator to fix this.",
                ephemeral=True,
                silent=True
            )
            
            return
        elif str(ctx.author.id) in self.bot.bot_data["ucids"]:
            old_ucid = self.bot.bot_data["ucids"][str(ctx.author.id)] 
            del self.bot.bot_data["rev_ucids"][old_ucid]

            await ctx.reply(
                f"Sucessfully changed UCID from **{old_ucid}** to **{ucid}**!",
                ephemeral=True
            )
        else:
            await ctx.reply(
                f"Sucessfully set UCID to **{ucid}**!",
                ephemeral=True
            )

        self.bot.bot_data["ucids"][str(ctx.author.id)] = ucid
        self.bot.bot_data["rev_ucids"][ucid] = str(ctx.author.id)
        
        save_json("data/data.json", self.bot.bot_data)

    @commands.hybrid_command(help="Change someone else's UCID")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    @app_commands.describe(
        user = "The member whose UCID is being changed",
        ucid = "The member's new UCID"
    )
    async def alter_ucid(self, ctx: commands.Context, user: discord.User, ucid: str):
        ucid = ucid.lower()
        
        if ucid in self.bot.bot_data["rev_ucids"]:
            user_id = self.bot.bot_data["rev_ucids"][ucid]
            
            await ctx.reply(
                f"<@!{user_id}> already has **{ucid}** as their UCID! Please change their ID first to continue",
                ephemeral=True,
                silent=True
            )
            
            return
        if str(user.id) in self.bot.bot_data["ucids"]:
            old_ucid = self.bot.bot_data["ucids"][str(user.id)] 
            del self.bot.bot_data["rev_ucids"][old_ucid]

            await ctx.reply(
                f"Sucessfully changed {user.mention}'s UCID from **{old_ucid}** to **{ucid}**!",
                ephemeral=True
            )
        else:
            await ctx.reply(
                f"Sucessfully set {user.mention}'s UCID to **{ucid}**!",
                ephemeral=True
            )

        self.bot.bot_data["ucids"][str(user.id)] = ucid
        self.bot.bot_data["rev_ucids"][ucid] = str(ctx.author.id)
        save_json("data/data.json", self.bot.bot_data)
        
    async def ban_ucid_callback(self, interaction: discord.Interaction, users: list[discord.User], view: discord.ui.View):
        result = f"Sucessfully banned "
        for user in users:
            if str(user.id) in self.bot.bot_data["banned"]:
                self.bot.bot_data["banned"].remove(str(user.id))
            result += f"{user.mention}, "
        result = result[:-2]
        result += " from changing their UCID!"
        
        await interaction.response.edit_message(
            content=result,
            view=view)

        save_json("data/data.json", self.bot.bot_data)

    @commands.hybrid_command(help="Ban someone from changing their UCID")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    async def ban_ucid(self, ctx: commands.Context):
        await ctx.reply(
            "Select users to ban:",
            view = UserSelectView(self.ban_ucid_callback),
            ephemeral=True
        )

    async def unban_ucid_callback(self, interaction: discord.Interaction, users: list[discord.User], view: discord.ui.View):
        result = f"Sucessfully unbanned "
        for user in users:
            if str(user.id) in self.bot.bot_data["banned"]:
                self.bot.bot_data["banned"].remove(str(user.id))
            result += f"{user.mention}, "
        result = result[:-2]
        result += " from changing their UCID!"
        
        await interaction.response.edit_message(
            content=result,
            view=view)

        save_json("data/data.json", self.bot.bot_data)

    @commands.hybrid_command(help="Unban someone from changing their UCID")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    async def unban_ucid(self, ctx: commands.Context):
        await ctx.reply(
            "Select users to unban:",
            view = UserSelectView(self.unban_ucid_callback),
            ephemeral=True
        )
        
    @commands.hybrid_command(help="Update the sheet")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    async def update_sheet(self, ctx: commands.Context):
        update_sheet()
        link = f"https://docs.google.com/spreadsheets/d/{os.getenv('SPREADSHEET_ID')}/edit?gid=663704479"
        
        await ctx.reply(
            f"Sheet updated! As always, you can view the sheet [here]({link})",
            ephemeral=True)
    
    async def add_bot_admin_callback(self, interaction: discord.Interaction, roles: list[discord.Role], view: discord.ui.View):
        if not str(interaction.guild.id) in self.bot.bot_data["admin_roles"]:
            self.bot.bot_data["admin_roles"][str(interaction.guild.id)] = []
            
        result = f"Sucessfully added "
        for role in roles:
            if not str(role.id) in self.bot.bot_data["admin_roles"][str(interaction.guild.id)]:
                self.bot.bot_data["admin_roles"][str(interaction.guild.id)].append(str(role.id))
            result += f"{role.mention}, "
        result = result[:-2]
        result += " to the bot admin list!"
        
        await interaction.response.edit_message(
            content=result,
            view=view)

        save_json("data/data.json", self.bot.bot_data)

    @commands.hybrid_command(help="Add a bot admin role to your server")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    async def add_bot_admin(self, ctx: commands.Context):
        await ctx.reply(
            "Select roles to add:",
            view = RoleSelectView(self.add_bot_admin_callback),
            ephemeral=True
        )
        
    async def remove_bot_admin_callback(self, interaction: discord.Interaction, roles: list[discord.Role], view: discord.ui.View):
        if not str(interaction.guild.id) in self.bot.bot_data["admin_roles"]:
            self.bot.bot_data["admin_roles"][str(interaction.guild.id)] = []
        
        result = f"Sucessfully removed "
        for role in roles:
            if str(role.id) in self.bot.bot_data["admin_roles"][str(interaction.guild.id)]:
                self.bot.bot_data["admin_roles"][str(interaction.guild.id)].remove(str(role.id))
            result += f"{role.mention}, "
        result = result[:-2]
        result += " from the bot admin list!"
        
        await interaction.response.edit_message(
            content=result,
            view=view)

        save_json("data/data.json", self.bot.bot_data)
    
    @commands.hybrid_command(help="Remove a bot admin role from your server")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    async def remove_bot_admin(self, ctx: commands.Context):
        await ctx.reply(
            "Select roles to remove:",
            view = RoleSelectView(self.remove_bot_admin_callback),
            ephemeral=True
        )
        
    async def add_sig_callback(self, interaction: discord.Interaction, roles: list[discord.Role], view: discord.ui.View):
        if not str(interaction.guild.id) in self.bot.bot_data["sig_roles"]:
            self.bot.bot_data["sig_roles"][str(interaction.guild.id)] = []
            
        result = f"Sucessfully added "
        for role in roles:
            if not str(role.id) in self.bot.bot_data["sig_roles"][str(interaction.guild.id)]:
                self.bot.bot_data["sig_roles"][str(interaction.guild.id)].append(str(role.id))
            result += f"{role.mention}, "
        result = result[:-2]
        result += " to the sig list!"
        
        await interaction.response.edit_message(
            content=result,
            view=view)

        save_json("data/data.json", self.bot.bot_data)
                
    @commands.hybrid_command(help="Add valid sig roles to your server")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    async def add_sig(self, ctx: commands.Context):
        await ctx.reply(
            "Select roles to add:",
            view = RoleSelectView(self.add_sig_callback),
            ephemeral=True
        )

    async def remove_sig_callback(self, interaction: discord.Interaction, roles: list[discord.Role], view: discord.ui.View):
        if not str(interaction.guild.id) in self.bot.bot_data["sig_roles"]:
            self.bot.bot_data["sig_roles"][str(interaction.guild.id)] = []
        
        result = f"Sucessfully removed "
        for role in roles:
            if str(role.id) in self.bot.bot_data["sig_roles"][str(interaction.guild.id)]:
                self.bot.bot_data["sig_roles"][str(interaction.guild.id)].remove(str(role.id))
            result += f"{role.mention}, "
        result = result[:-2]
        result += " from the sig list!"
        
        await interaction.response.edit_message(
            content=result,
            view=view)

        save_json("data/data.json", self.bot.bot_data)

    @commands.hybrid_command(help="Remove sig roles to your server")
    # @commands.cooldown(1, 15, commands.BucketType.guild)
    @run_if(has_admin_perms)
    async def remove_sig(self, ctx: commands.Context):
        await ctx.reply(
            "Select roles to remove:",
            view = RoleSelectView(self.remove_sig_callback),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AttendanceCog(bot))