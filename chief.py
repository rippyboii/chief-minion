import discord
from discord.ext import commands
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
logging.basicConfig(level=logging.CRITICAL)  # Minimize terminal logging to critical errors
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True
bot = commands.Bot(command_prefix='chief ', intents=intents)

# Replace literal '\\n' with actual newlines in the private key
private_key = os.getenv("PRIVATE_KEY").replace('\\n', '\n')

# Set the ID for the logging channel
LOGGING_CHANNEL_ID = 1241235207227445309
BOT_HELPER_ROLE_ID = 1232694582114783232
VERIFIED_ROLE_ID = 1232674785981628426

# Helper function to send log messages to the logging channel
async def log_to_channel(bot, message):
    channel = bot.get_channel(LOGGING_CHANNEL_ID)
    if channel:
        await channel.send(message)

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

async def setup_google_sheet():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Rolling Admission (Responses)").worksheet("Form Responses 1")
        # Log success of opening the Google Sheet
        await log_to_channel(bot, "Successfully accessed Google Sheet: Rolling Admission (Responses), Worksheet: Form Responses 1")
        
        # Log the headers or specific columns
        headers = sheet.row_values(1)
        await log_to_channel(bot, f"Headers in Google Sheet: {headers}")
        
        # Optionally, log specific columns or rows
        column_data = sheet.col_values(1)  # For example, accessing the first column
        await log_to_channel(bot, f"Data in first column: {column_data[:10]}")  # Log first 10 rows of the first column
        
        return sheet
    except gspread.exceptions.SpreadsheetNotFound:
        error_message = "Error: The spreadsheet 'Rolling Admission (Responses)' was not found."
        logging.error(error_message)
        await log_to_channel(bot, error_message)
    except gspread.exceptions.WorksheetNotFound:
        error_message = "Error: The worksheet 'Form Responses 1' was not found in the spreadsheet."
        logging.error(error_message)
        await log_to_channel(bot, error_message)
    except Exception as e:
        error_message = f"Error creating credentials or accessing the sheet: {e}"
        logging.error(error_message)
        await log_to_channel(bot, error_message)

sheet = None

@bot.event
async def on_ready():
    global sheet
    await log_to_channel(bot, f"We have logged in as {bot.user}")
    bot.loop.create_task(keep_alive())
    sheet = await setup_google_sheet()
    try:
        verification_channel = bot.get_channel(1232674931255414865)  # Your verification channel ID
        if verification_channel:
            # Delete bot's previous messages in the verification channel
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

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VerifyButton())
        self.add_item(SupportButton())

class VerifyButton(discord.ui.Button):
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
                    "You have not renamed in proper format. If you think I made a mistake, refer to manual verification.",
                    ephemeral=True)
                await log_to_channel(bot, f"Failed format check for {member.name}")
                with open("unverified_attempts.log", "a") as log_file:
                    log_file.write(f"{member.name} ({display_name}) - Failed format check\n")
                return

            # Check Google Sheets for Application ID
            application_id = display_name
            try:
                sheet_data = sheet.col_values(27)  # Assuming the Application ID is in the 27th column (AA)
                await log_to_channel(bot, f"Retrieved sheet data for verification: {sheet_data}")
                if application_id in sheet_data:
                    role = interaction.guild.get_role(1232674785981628426)  # Your Verified Applicant role ID
                    if role:
                        await member.add_roles(role)
                        await interaction.response.send_message("You have been verified and granted access to other channels.", ephemeral=True)
                        await log_to_channel(bot, f"Role {role.name} added to {member.name}")
                        welcome_channel = bot.get_channel(123456789012345678)  # Your welcome channel ID
                        if welcome_channel:
                            await welcome_channel.send(f"Welcome, {member.mention}! You have been verified and granted access to the server.")
                    else:
                        await interaction.response.send_message("Verification successful, but unable to grant role. Please contact support.", ephemeral=True)
                        await log_to_channel(bot, f"Role not found for {member.name}")
                else:
                    await interaction.response.send_message("I couldn't verify your identity. Please contact support for human help.", ephemeral=True)
                    await log_to_channel(bot, f"Application ID {application_id} not found in sheet for {member.name}")
                    with open("unverified_attempts.log", "a") as log_file:
                        log_file.write(f"{member.name} ({display_name}) - Application ID not found\n")
            except Exception as e:
                await interaction.response.send_message(f"Please request manual verification. An error occurred: {e}", ephemeral=True)
                await log_to_channel(bot, f"Error accessing Google Sheets for {member.name}: {e}")

        except discord.errors.NotFound:
            await log_to_channel(bot, f"Interaction not found for {member.name}, possibly expired.")
        except Exception as e:
            try:
                await interaction.response.send_message(f"An error occurred during verification: {e}", ephemeral=True)
            except discord.errors.NotFound:
                await log_to_channel(bot, f"Error responding to interaction for {member.name}: {e}")

class SupportButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Request Manual Verification", style=discord.ButtonStyle.red)
    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        await log_to_channel(bot, f" OI <@&{BOT_HELPER_ROLE_ID}>, \n \n {member.mention} has requested manual verification.")
        await interaction.response.send_message(
            f"Your request for manual verification has been sent. Please wait for <@&{BOT_HELPER_ROLE_ID}> to assist you. Stand by.",
            ephemeral=True
        )

async def keep_alive():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(3600)  # Run task every hour

bot.run(os.getenv("TOKEN"))
