import os
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
    "REDIRECT_URI": REDIRECT_URI,
    "VERIFY_URL": VERIFY_URL,
}


missing = [
    name
    for name, value in required_vars.items()
    if not value
]


if missing:

    print("=" * 60)
    print("MISSING ENVIRONMENT VARIABLES")
    print("=" * 60)

    for name in missing:
        print(f" - {name}")

    print("=" * 60)


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# VERIFY
# =========================================================

@app.route("/verify")
def verify():

    if not CLIENT_ID:

        return (
            "CLIENT_ID is missing.",
            500
        )


    if not REDIRECT_URI:

        return (
            "REDIRECT_URI is missing.",
            500
        )


    # Discord OAuth URL

    oauth_url = (

        "https://discord.com/oauth2/authorize"

        f"?client_id={CLIENT_ID}"

        "&response_type=code"

        f"&redirect_uri="
        f"{requests.utils.quote(REDIRECT_URI, safe='')}"

        "&scope=identify%20guilds.join"

    )


    return redirect(
        oauth_url
    )


# =========================================================
# CALLBACK
# =========================================================

@app.route("/callback")
def callback():

    code = request.args.get(
        "code"
    )


    if not code:

        return (
            "Verification cancelled.",
            400
        )


    # =====================================================
    # EXCHANGE CODE -> ACCESS TOKEN
    # =====================================================

    try:

        token_response = requests.post(

            f"{DISCORD_API}/oauth2/token",

            data={

                "client_id":
                    CLIENT_ID,

                "client_secret":
                    CLIENT_SECRET,

                "grant_type":
                    "authorization_code",

                "code":
                    code,

                "redirect_uri":
                    REDIRECT_URI,

            },

            headers={

                "Content-Type":
                    "application/x-www-form-urlencoded"

            },

            timeout=15,

        )


    except requests.RequestException as e:

        print(
            "Token request error:",
            e
        )

        return (
            "Could not connect to Discord.",
            502
        )


    # =====================================================
    # CHECK TOKEN RESPONSE
    # =====================================================

    if token_response.status_code != 200:

        print(
            "OAuth token error:",
            token_response.status_code,
            token_response.text
        )

        return (
            "OAuth2 authentication failed.",
            400
        )


    try:

        token_data = (
            token_response.json()
        )

        access_token = (
            token_data["access_token"]
        )


    except (
        KeyError,
        ValueError
    ):

        print(
            "Invalid OAuth2 response."
        )

        return (
            "Invalid OAuth2 response.",
            400
        )


    # =====================================================
    # GET DISCORD USER
    # =====================================================

    try:

        user_response = requests.get(

            f"{DISCORD_API}/users/@me",

            headers={

                "Authorization":
                    f"Bearer {access_token}"

            },

            timeout=15,

        )


    except requests.RequestException as e:

        print(
            "User request error:",
            e
        )

        return (
            "Could not connect to Discord.",
            502
        )


    # =====================================================
    # CHECK USER RESPONSE
    # =====================================================

    if user_response.status_code != 200:

        print(
            "Discord user error:",
            user_response.status_code,
            user_response.text
        )

        return (
            "Could not get Discord account.",
            400
        )


    try:

        user = user_response.json()

        user_id = user["id"]


    except (
        KeyError,
        ValueError
    ):

        return (
            "Invalid Discord user response.",
            400
        )


    # =====================================================
    # ADD USER TO SERVER
    # =====================================================

    try:

        join_response = requests.put(

            f"{DISCORD_API}/guilds/"
            f"{GUILD_ID}/members/"
            f"{user_id}",

            headers={

                "Authorization":
                    f"Bot {DISCORD_TOKEN}",

                "Content-Type":
                    "application/json",

            },

            json={

                "access_token":
                    access_token

            },

            timeout=15,

        )


    except requests.RequestException as e:

        print(
            "Guild join error:",
            e
        )

        return (
            "Could not connect to Discord.",
            502
        )


    # =====================================================
    # CHECK JOIN
    # =====================================================

    if join_response.status_code not in (
        200,
        201,
        204
    ):

        print(
            "Guild join error:",
            join_response.status_code,
            join_response.text
        )

        return (
            "Could not join Discord server.",
            400
        )


    # =====================================================
    # GIVE VERIFIED ROLE
    # =====================================================

    try:

        role_response = requests.put(

            f"{DISCORD_API}/guilds/"
            f"{GUILD_ID}/members/"
            f"{user_id}/roles/"
            f"{VERIFIED_ROLE_ID}",

            headers={

                "Authorization":
                    f"Bot {DISCORD_TOKEN}"

            },

            timeout=15,

        )


    except requests.RequestException as e:

        print(
            "Role request error:",
            e
        )

        return (
            "Could not connect to Discord.",
            502
        )


    # =====================================================
    # CHECK ROLE
    # =====================================================

    if role_response.status_code not in (
        200,
        204
    ):

        print(
            "Role assignment error:",
            role_response.status_code,
            role_response.text
        )

        return (
            "Verified, but role assignment failed.",
            500
        )


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


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"Discord bot logged in as "
        f"{bot.user} ({bot.user.id})"
    )

    print(
        "Verify message sending is DISABLED."
    )

    print(
        "Bot will NOT send messages to any channel."
    )


# =========================================================
# START DISCORD BOT
# =========================================================

def start_discord_bot():

    if not DISCORD_TOKEN:

        print(
            "DISCORD_TOKEN is missing."
        )

        return


    try:

        bot.run(
            DISCORD_TOKEN
        )


    except discord.LoginFailure:

        print(
            "Invalid Discord bot token."
        )


    except Exception as e:

        print(
            f"Discord bot stopped: {e}"
        )


# =========================================================
# START BOT
# =========================================================

bot_thread = __import__(
    "threading"
).Thread(

    target=start_discord_bot,

    daemon=True

)


bot_thread.start()


# =========================================================
# START FLASK
# =========================================================

if __name__ == "__main__":

    port = int(

        os.getenv(
            "PORT",
            "10000"
        )

    )


    print(
        f"Flask starting on port {port}"
    )


    app.run(

        host="0.0.0.0",

        port=port

    )
    
    
    
