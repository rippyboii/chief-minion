import discord
from discord.ext import commands
from discord.ui import Button, View
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from dotenv import load_dotenv
import os
import logging
import asyncio

# Loading env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix='chief ', intents=intents)

# Replace literal '\\n' with actual newlines in the private key
private_key = os.getenv("PRIVATE_KEY").replace('\\n', '\n')

# Set up Google Sheets API credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = {
    "type": "service_account",
    "project_id": "rolling-admission",
    "private_key_id": os.getenv("PRIVATE_KEY_ID"),
    "private_key": private_key,
    "client_email": os.getenv("CLIENT_EMAIL"),
    "client_id": os.getenv("CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/minion-bot@rolling-admission.iam.gserviceaccount.com"
}

try:
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Rolling Admission (Responses)").worksheet("Form Responses 1")
    logging.debug("Google Sheets connection established successfully.")
except Exception as e:
    logging.error(f"Error creating credentials: {e}")
    sheet = None

# Set the ID for the logging channel
LOGGING_CHANNEL_ID = 1241235207227445309
BOT_HELPER_ROLE_ID = 1232694582114783232
VERIFIED_ROLE_ID = 1232674785981628426

# Helper function to send log messages to the logging channel
async def log_to_channel(bot, message):
    channel = bot.get_channel(LOGGING_CHANNEL_ID)
    if channel:
        await channel.send(message)

# Verification view and button
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Disable timeout
        self.add_item(VerifyButton())
        self.add_item(SupportButton())

class VerifyButton(Button):
    def __init__(self):
        super().__init__(label="Verify", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        display_name = member.display_name

        try:
            await log_to_channel(bot, f"Starting verification for {member.name} with display name {display_name}")
            # Check display name format
            match = re.match(r"RA_\d+_.+", display_name)
            if not match:
                await interaction.response.send_message(
                    "You have not renamed in proper format. If you think I made a mistake, refer to manual verification.", ephemeral=True)
                await log_to_channel(bot, f"Failed format check for {member.name}")
                # Log unverified attempt
                with open("unverified_attempts.log", "a") as log_file:
                    log_file.write(f"{member.name} ({display_name}) - Failed format check\n")
                return

            # Check Google Sheets for Application ID
            application_id = display_name
            try:
                if sheet is None:
                    raise Exception("Google Sheets not initialized")

                sheet_data = sheet.col_values(27)  # Assuming the Application ID is in the 27th column (AA)
                await log_to_channel(bot, f"Retrieved sheet data for verification: {sheet_data}")

                if application_id in sheet_data:
                    # Grant access to other channels
                    role = interaction.guild.get_role(VERIFIED_ROLE_ID)  # Your Verified Applicant role ID
                    if role:
                        await member.add_roles(role)
                        await interaction.response.send_message("You have been verified and granted access to other channels.", ephemeral=True)
                        await log_to_channel(bot, f"Role {role.name} added to {member.name}")

                        # Send a welcome message
                        welcome_channel = bot.get_channel(123456789012345678)  # Your welcome channel ID
                        if welcome_channel:
                            await welcome_channel.send(f"Welcome, {member.mention}! You have been verified and granted access to the server.")
                    else:
                        await interaction.response.send_message("Verification successful, but unable to grant role. Please contact support.", ephemeral=True)
                        await log_to_channel(bot, f"Role not found for {member.name}")
                else:
                    await interaction.response.send_message("I couldn't verify your identity. Please contact support for human help.", ephemeral=True)
                    await log_to_channel(bot, f"Application ID {application_id} not found in sheet for {member.name}")
                    # Log unverified attempt
                    with open("unverified_attempts.log", "a") as log_file:
                        log_file.write(f"{member.name} ({display_name}) - Application ID not found\n")
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
                await log_to_channel(bot, f"Error accessing Google Sheets for {member.display_name}: {e}")

        except Exception as e:
            await interaction.response.send_message(f"An error occurred during verification: {e}", ephemeral=True)
            await log_to_channel(bot, f"Unexpected error during verification for {member.display_name}: {e}")

class SupportButton(Button):
    def __init__(self):
        super().__init__(label="Request Manual Verification", style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        await log_to_channel(bot, f" OI <@&{BOT_HELPER_ROLE_ID}>, \n \n {member.mention} has requested manual verification.")
        await interaction.response.send_message(
            f"Your request for manual verification has been sent. Please wait for <@&{BOT_HELPER_ROLE_ID}> to assist you. Stand by.",
            ephemeral=True
        )

@bot.event
async def on_ready():
    print(f"We have logged in {bot.user}")
    await log_to_channel(bot, f"We have logged in as {bot.user}")

    async def keep_alive():
        while True:
            await asyncio.sleep(300)  # Sleep for 5 minutes
            try:
                await log_to_channel(bot, "Keep-alive check")
            except Exception as e:
                logging.error(f"Error in keep-alive check: {e}")
                await log_to_channel(bot, f"Error in keep-alive check: {e}")

    bot.loop.create_task(keep_alive())

    try:
        verification_channel = bot.get_channel(1232674931255414865)  # Your verification channel ID
        if verification_channel:
            async for message in verification_channel.history(limit=100):
                if message.author == bot.user:
                    await message.delete()

            await verification_channel.send(
                "📣 Attention, Applicant! Listen up! 🚨\n \n"
                "**Step One:** Identify your Application ID. Format: RA_number_YourName. Ensure your ID matches precisely with the email we sent upon your registration.\n \n"
                "**Step Two:** Rename yourself to match your Application ID exactly. Refer to the video above if you need assistance with renaming.\n \n"
                "**Step Three:** Click the verify button below. If you encounter any issues or fail to get verified, hit the support button for human assistance.\n \n"
                "Upon successful verification, you will gain access to additional channels. Move with precision and follow these instructions to the letter!\n",
                view=VerificationView()
            )
    except Exception as e:
        await log_to_channel(bot, f"Error in on_ready: {e}")

def has_bot_helper_role():
    def predicate(ctx):
        bot_helper_role = discord.utils.get(ctx.guild.roles, id=BOT_HELPER_ROLE_ID)
        return bot_helper_role in ctx.author.roles
    return commands.check(predicate)

@bot.command(name="ban")
@has_bot_helper_role()
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} has been banned for: {reason}")
        await log_to_channel(bot, f"{member.mention} was banned by {ctx.author} for: {reason}")
    except Exception as e:
        await log_to_channel(bot, f"Error in ban command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="kick")
@has_bot_helper_role()
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} has been kicked for: {reason}")
        await log_to_channel(bot, f"{member.mention} was kicked by {ctx.author} for: {reason}")
    except Exception as e:
        await log_to_channel(bot, f"Error in kick command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="unverify")
@has_bot_helper_role()
async def unverify(ctx, member: discord.Member):
    try:
        role = discord.utils.get(ctx.guild.roles, id=VERIFIED_ROLE_ID)
        if role in member.roles:
            await member.remove_roles(role)
            await ctx.send(f"{member.mention} has been unverified.")
            await log_to_channel(bot, f"{member.mention} was unverified by {ctx.author}")
        else:
            await ctx.send(f"{member.mention} does not have the Verified role.")
            await log_to_channel(bot, f"{member.mention} does not have the Verified role.")
    except Exception as e:
        await log_to_channel(bot, f"Error in unverify command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="mute")
@has_bot_helper_role()
async def mute(ctx, member: discord.Member, duration: int):
    try:
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role:
            mute_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(mute_role, send_messages=False, speak=False)
        await member.add_roles(mute_role)
        await ctx.send(f"{member.mention} has been muted for {duration} minutes.")
        await log_to_channel(bot, f"{member.mention} was muted by {ctx.author} for {duration} minutes.")
        await asyncio.sleep(duration * 60)
        await member.remove_roles(mute_role)
        await ctx.send(f"{member.mention} has been unmuted.")
        await log_to_channel(bot, f"{member.mention} was unmuted.")
    except Exception as e:
        await log_to_channel(bot, f"Error in mute command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="warn")
@has_bot_helper_role()
async def warn(ctx, member: discord.Member, *, reason=None):
    try:
        await member.send(f"You have been warned for: {reason}")
        await ctx.send(f"{member.mention} has been warned for: {reason}")
        await log_to_channel(bot, f"{member.mention} was warned by {ctx.author} for: {reason}")
    except Exception as e:
        await log_to_channel(bot, f"Error in warn command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="clear")
@has_bot_helper_role()
async def clear(ctx, amount: int):
    try:
        await ctx.channel.purge(limit=amount)
        await ctx.send(f"Cleared {amount} messages.", delete_after=5)
        await log_to_channel(bot, f"{ctx.author} cleared {amount} messages in {ctx.channel.name}")
    except Exception as e:
        await log_to_channel(bot, f"Error in clear command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="lock")
@has_bot_helper_role()
async def lock(ctx):
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"{ctx.channel.name} has been locked.")
        await log_to_channel(bot, f"{ctx.author} locked {ctx.channel.name}")
    except Exception as e:
        await log_to_channel(bot, f"Error in lock command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="unlock")
@has_bot_helper_role()
async def unlock(ctx):
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(f"{ctx.channel.name} has been unlocked.")
        await log_to_channel(bot, f"{ctx.author} unlocked {ctx.channel.name}")
    except Exception as e:
        await log_to_channel(bot, f"Error in unlock command: {e}")
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="userinfo")
@has_bot_helper_role()
async def userinfo(ctx, member: discord.Member):
    try:
        roles = [role.mention for role in member.roles if role != ctx.guild.default_role]
        embed = discord.Embed(title=f"User Info - {member}", color=member.color)
        embed.add_field(name="ID", value=member.id, inline=False)
        embed.add_field(name="Display Name", value=member.display_name, inline=False)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
        embed.add_field(name="Roles", value=" ".join(roles), inline=False)
        await ctx.send(embed=embed)
        await log_to_channel(bot, f"{ctx.author} requested info for {member}")
    except Exception as e:
        await log_to_channel(bot, f"Error in userinfo command: {e}")
        await ctx.send(f"An error occurred: {e}")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
