import os
import threading
import requests
import discord

from flask import Flask, redirect, render_template, request
from discord.ext import commands
from dotenv import load_dotenv


# =========================================================
# LOAD .ENV
# =========================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GUILD_ID = os.getenv("GUILD_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
VERIFY_CHANNEL_ID = os.getenv("VERIFY_CHANNEL_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
VERIFY_URL = os.getenv("VERIFY_URL")

DISCORD_API = "https://discord.com/api/v10"


# =========================================================
# CHECK ENV
# =========================================================

required_vars = {
    "DISCORD_TOKEN": DISCORD_TOKEN,
    "CLIENT_ID": CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET,
    "GUILD_ID": GUILD_ID,
    "VERIFIED_ROLE_ID": VERIFIED_ROLE_ID,
    "VERIFY_CHANNEL_ID": VERIFY_CHANNEL_ID,
    "REDIRECT_URI": REDIRECT_URI,
    "VERIFY_URL": VERIFY_URL,
}

missing = [
    name
    for name, value in required_vars.items()
    if not value
]

if missing:
    print("Missing environment variables:")
    for name in missing:
        print(f" - {name}")


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# VERIFY
# =========================================================

@app.route("/verify")
def verify():

    if not CLIENT_ID or not REDIRECT_URI:
        return "OAuth configuration is missing.", 500

    url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={requests.utils.quote(REDIRECT_URI, safe='')}"
        "&scope=identify%20guilds.join"
    )

    return redirect(url)


# =========================================================
# CALLBACK
# =========================================================

@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return "Verification cancelled.", 400

    # -----------------------------------------------------
    # Exchange OAuth code -> access token
    # -----------------------------------------------------

    try:
        token_response = requests.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            timeout=15,
        )

    except requests.RequestException as e:
        print("Token request error:", e)
        return "Could not connect to Discord.", 502

    if token_response.status_code != 200:

        print(
            "OAuth token error:",
            token_response.status_code,
            token_response.text
        )

        return "OAuth2 authentication failed.", 400

    try:
        access_token = token_response.json()["access_token"]

    except (KeyError, ValueError):
        return "Invalid OAuth2 response.", 400


    # -----------------------------------------------------
    # Get Discord user
    # -----------------------------------------------------

    try:
        user_response = requests.get(
            f"{DISCORD_API}/users/@me",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=15,
        )

    except requests.RequestException as e:
        print("User request error:", e)
        return "Could not connect to Discord.", 502

    if user_response.status_code != 200:

        print(
            "Discord user error:",
            user_response.status_code,
            user_response.text
        )

        return "Could not get Discord account.", 400

    user = user_response.json()

    user_id = user["id"]


    # -----------------------------------------------------
    # Add user to server
    # -----------------------------------------------------

    try:
        join_response = requests.put(
            f"{DISCORD_API}/guilds/"
            f"{GUILD_ID}/members/{user_id}",

            headers={
                "Authorization": f"Bot {DISCORD_TOKEN}",
                "Content-Type": "application/json",
            },

            json={
                "access_token": access_token
            },

            timeout=15,
        )

    except requests.RequestException as e:
        print("Guild join error:", e)
        return "Could not connect to Discord.", 502

    if join_response.status_code not in (200, 201, 204):

        print(
            "Guild join error:",
            join_response.status_code,
            join_response.text
        )

        return "Could not join Discord server.", 400


    # -----------------------------------------------------
    # Give Verified role
    # -----------------------------------------------------

    try:
        role_response = requests.put(
            f"{DISCORD_API}/guilds/"
            f"{GUILD_ID}/members/"
            f"{user_id}/roles/"
            f"{VERIFIED_ROLE_ID}",

            headers={
                "Authorization": f"Bot {DISCORD_TOKEN}"
            },

            timeout=15,
        )

    except requests.RequestException as e:
        print("Role request error:", e)
        return "Could not connect to Discord.", 502

    if role_response.status_code not in (200, 204):

        print(
            "Role assignment error:",
            role_response.status_code,
            role_response.text
        )

        return "Verified, but role assignment failed.", 500


    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    username = (
        user.get("global_name")
        or user.get("username")
        or "User"
    )

    return render_template(
        "success.html",
        username=username
    )


# =========================================================
# DISCORD BOT
# =========================================================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# VERIFY BUTTON
# =========================================================

class VerifyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="VERIFY (Ấn vào đây để xác minh)",
                emoji="✅",
                style=discord.ButtonStyle.link,
                url=VERIFY_URL
            )
        )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"Discord bot logged in as "
        f"{bot.user} ({bot.user.id})"
    )

    try:
        channel_id = int(VERIFY_CHANNEL_ID)

    except (TypeError, ValueError):

        print(
            "VERIFY_CHANNEL_ID is invalid:"
            f" {VERIFY_CHANNEL_ID}"
        )

        return


    channel = bot.get_channel(channel_id)

    if channel is None:

        print(
            "Could not find verify channel: "
            f"{channel_id}"
        )

        return


    print(
        f"Found verify channel: "
        f"#{channel.name}"
    )


    # -----------------------------------------------------
    # Send verification message
    # -----------------------------------------------------

    embed = discord.Embed(
        title="🔐 Xác Minh",

        description=(
            "Hãy click vào nút VERIFY bên dưới để chúng tôi xác minh bạn có phải là robot hay không." "\n"
            "Có thắc mắc xin liên hệ @8zpc ." "\n"
            "Trân trọng !"
        ),

        color=discord.Color.blurple()
    )
    embed.set_image(
    url="https://cdn.discordapp.com/attachments/1539512033353928759/1539540467572809759/Wallpaper_Alchemy_-_Hinh_Nen_4K_Co_Gai_Anime_Haimiya_Mio.jpg?ex=6a89fc0a&is=6a88aa8a&hm=b07f1f1eea99af2c24d851b6f3d4eba79d42ad3844c626fc7813ff4ac52e39ca&"
    )
    embed.set_footer(
        text="Make by 8zpc with love"
    )


    try:

        await channel.send(
            embed=embed,
            view=VerifyView()
        )

        print(
            "Verification message sent successfully."
        )

    except discord.Forbidden:

        print(
            "Bot does not have permission "
            "to send messages in this channel."
        )

    except discord.HTTPException as e:

        print(
            "Discord API error while sending "
            f"verification message: {e}"
        )


# =========================================================
# START DISCORD BOT
# =========================================================

def start_discord_bot():

    if not DISCORD_TOKEN:

        print(
            "DISCORD_TOKEN is missing. "
            "Discord bot will not start."
        )

        return

    try:

        bot.run(DISCORD_TOKEN)

    except Exception as e:

        print(
            f"Discord bot stopped: {e}"
        )


bot_thread = threading.Thread(
    target=start_discord_bot,
    daemon=True
)

bot_thread.start()


# =========================================================
# FLASK START
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
