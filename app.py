import os
import threading
import requests
import discord

from flask import Flask, redirect, render_template, request
from discord.ext import commands
from dotenv import load_dotenv

# =========================================================
# LOAD ENV
# =========================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GUILD_ID = os.getenv("GUILD_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")

VERIFY_URL = os.getenv("VERIFY_URL")
VERIFY_CHANNEL_ID = os.getenv("VERIFY_CHANNEL_ID")

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
    "REDIRECT_URI": REDIRECT_URI,
    "VERIFY_URL": VERIFY_URL,
    "VERIFY_CHANNEL_ID": VERIFY_CHANNEL_ID,
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


@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not code:
        return "Verification cancelled.", 400

    # =====================================================
    # EXCHANGE CODE -> ACCESS TOKEN
    # =====================================================

    try:
        token = requests.post(
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
    except requests.RequestException:
        return "Could not connect to Discord.", 502

    if token.status_code != 200:
        print("OAuth token error:", token.status_code)
        print(token.text)

        return "OAuth2 authentication failed.", 400

    try:
        access_token = token.json()["access_token"]
    except (KeyError, ValueError):
        return "Invalid OAuth2 response.", 400

    # =====================================================
    # GET DISCORD USER
    # =====================================================

    try:
        user_request = requests.get(
            f"{DISCORD_API}/users/@me",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=15,
        )
    except requests.RequestException:
        return "Could not connect to Discord.", 502

    if user_request.status_code != 200:
        print("User request error:")
        print(user_request.status_code)
        print(user_request.text)

        return "Could not get Discord account.", 400

    user = user_request.json()
    user_id = user["id"]

    # =====================================================
    # ADD USER TO SERVER
    # =====================================================

    try:
        join = requests.put(
            f"{DISCORD_API}/guilds/{GUILD_ID}/members/{user_id}",
            headers={
                "Authorization": f"Bot {DISCORD_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "access_token": access_token
            },
            timeout=15,
        )
    except requests.RequestException:
        return "Could not connect to Discord.", 502

    if join.status_code not in (200, 201, 204):
        print("Guild join error:")
        print(join.status_code)
        print(join.text)

        return "Could not join Discord server.", 400

    # =====================================================
    # GIVE VERIFIED ROLE
    # =====================================================

    try:
        role = requests.put(
            f"{DISCORD_API}/guilds/{GUILD_ID}/members/"
            f"{user_id}/roles/{VERIFIED_ROLE_ID}",
            headers={
                "Authorization": f"Bot {DISCORD_TOKEN}"
            },
            timeout=15,
        )
    except requests.RequestException:
        return "Could not connect to Discord.", 502

    if role.status_code not in (200, 204):
        print("Role assignment error:")
        print(role.status_code)
        print(role.text)

        return "Verified, but role assignment failed.", 500

    # =====================================================
    # SUCCESS
    # =====================================================

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


class VerifyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="VERIFY",
                emoji="✅",
                style=discord.ButtonStyle.link,
                url=VERIFY_URL
            )
        )


@bot.event
async def on_ready():

    print(f"Discord bot logged in as {bot.user}")

    try:
        channel_id = int(VERIFY_CHANNEL_ID)
    except (TypeError, ValueError):
        print("VERIFY_CHANNEL_ID is invalid.")
        return

    channel = bot.get_channel(channel_id)

    if channel is None:
        print(
            f"Could not find verify channel: "
            f"{channel_id}"
        )
        return

    print(
        f"Found verify channel: "
        f"#{channel.name}"
    )

    embed = discord.Embed(
        title="🔐 Server Verification",
        description=(
            "Click the button below to verify your "
            "Discord account.\n\n"
            "After verification, you will automatically "
            "receive the **Verified** role."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Server Verification"
    )

    try:
        await channel.send(
            embed=embed,
            view=VerifyView()
        )

        print("Verification message sent.")

    except discord.Forbidden:
        print(
            "Bot does not have permission "
            "to send messages in this channel."
        )

    except discord.HTTPException as e:
        print(
            f"Discord API error while sending message: {e}"
        )


# =========================================================
# START DISCORD BOT IN BACKGROUND
# =========================================================

def start_discord_bot():

    if not DISCORD_TOKEN:
        print("DISCORD_TOKEN is missing.")
        return

    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Discord bot stopped: {e}")


bot_thread = threading.Thread(
    target=start_discord_bot,
    daemon=True
)

bot_thread.start()


# =========================================================
# FLASK ENTRY POINT
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
