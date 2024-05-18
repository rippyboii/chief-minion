import discord
from discord.ext import commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from dotenv import load_dotenv
import os
import logging

# Load environment variables from .env file
load_dotenv()

# Set up logging to display debug information
logging.basicConfig(level=logging.DEBUG)

# Print environment variables to verify they are loaded correctly
print("Private Key ID:", os.getenv("PRIVATE_KEY_ID"))
print("Client Email:", os.getenv("CLIENT_EMAIL"))
print("Client ID:", os.getenv("CLIENT_ID"))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Replace literal '\\n' with actual newlines in the private key
private_key = os.getenv("PRIVATE_KEY").replace('\\n', '\n')

# Print the private key to debug
print("Private Key:", private_key)

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
except Exception as e:
    logging.error(f"Error creating credentials: {e}")

# Verification view and button
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(VerifyButton())

class VerifyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Verify", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        display_name = member.display_name

        try:
            logging.info(f"Starting verification for {member.name} with display name {display_name}")
            # Check display name format
            match = re.match(r"RA_\d+_.+", display_name)
            if not match:
                await interaction.response.send_message(
                    "You have not renamed in proper format. If you think I made a mistake, please contact support.", ephemeral=True)
                logging.info(f"Failed format check for {member.name}")
                return

            # Check Google Sheets for Application ID
            application_id = display_name
            try:
                sheet_data = sheet.col_values(27)  # Assuming the Application ID is in the 27th column (AA)
                logging.info(f"Retrieved sheet data for verification: {sheet_data}")

                if application_id in sheet_data:
                    # Grant access to other channels
                    role = interaction.guild.get_role(1232674785981628426)  # Your Verified Applicant role ID
                    if role:
                        await member.add_roles(role)
                        await interaction.response.send_message("You have been verified and granted access to other channels.", ephemeral=True)
                        logging.info(f"Role {role.name} added to {member.name}")
                    else:
                        await interaction.response.send_message("Verification successful, but unable to grant role. Please contact support.", ephemeral=True)
                        logging.error(f"Role not found for {member.name}")
                else:
                    await interaction.response.send_message("I couldn't verify your identity. Please contact support for human help.", ephemeral=True)
                    logging.info(f"Application ID {application_id} not found in sheet for {member.name}")
            except Exception as e:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
                logging.error(f"Error accessing Google Sheets for {member.name}: {e}")

        except Exception as e:
            await interaction.response.send_message(f"An error occurred during verification: {e}", ephemeral=True)
            logging.error(f"Unexpected error during verification for {member.name}: {e}")

@bot.event
async def on_ready():
    logging.info(f"We have logged in as {bot.user}")
    try:
        verification_channel = bot.get_channel(1232674931255414865)  # Your verification channel ID
        if verification_channel:
            # Delete bot's previous messages in the verification channel
            async for message in verification_channel.history(limit=100):
                if message.author == bot.user:
                    await message.delete()

            await verification_channel.send(
                "Let's get you verified first.\n"
                "Step one: Know your Application ID (ID Format: RA_number_Your name. Make sure your ID is exactly as it appeared in your email that we sent earlier upon registration)\n"
                "Step two: Rename yourself as the same as that application ID. Check the video above if you have any confusion on renaming yourself.\n"
                "Step three: Click the verify button below. If you have any problem or you are not being verified, click the support button for human help.\n"
                "Once you are verified, you will get access to other channels.",
                view=VerificationView()
            )
    except Exception as e:
        logging.error(f"Error in on_ready: {e}")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
