import os
import threading
from urllib.parse import urlencode

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
VERIFY_CHANNEL_ID = os.getenv("VERIFY_CHANNEL_ID")

REDIRECT_URI = os.getenv("REDIRECT_URI")
VERIFY_URL = os.getenv("VERIFY_URL")

# Optional:
# Nếu có thì bot sẽ không gửi lại message mỗi lần restart.
VERIFY_MESSAGE_ID = os.getenv("VERIFY_MESSAGE_ID")


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
}


missing = [
    name
    for name, value in required_vars.items()
    if not value
]


if missing:

    print("=" * 60)
    print("❌ MISSING ENVIRONMENT VARIABLES")
    print("=" * 60)

    for name in missing:
        print(f" - {name}")

    print("=" * 60)


# =========================================================
# VERIFY URL
# =========================================================

if not VERIFY_URL and REDIRECT_URI:

    VERIFY_URL = REDIRECT_URI.rsplit("/", 1)[0] + "/verify"

    print(
        f"VERIFY_URL was not found. "
        f"Using: {VERIFY_URL}"
    )


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

    if not CLIENT_ID:
        return "CLIENT_ID is missing.", 500

    if not REDIRECT_URI:
        return "REDIRECT_URI is missing.", 500

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds.join",
    }

    oauth_url = (
        "https://discord.com/oauth2/authorize?"
        + urlencode(params)
    )

    return redirect(oauth_url)


# =========================================================
# CALLBACK
# =========================================================

@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return "Verification cancelled.", 400


    # =====================================================
    # EXCHANGE CODE -> ACCESS TOKEN
    # =====================================================

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

            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },

            timeout=15,
        )

    except requests.RequestException as e:

        print(
            f"❌ Token request error: {e}"
        )

        return (
            "Could not connect to Discord.",
            502
        )


    if token_response.status_code != 200:

        print(
            "❌ OAuth token error:",
            token_response.status_code,
            token_response.text
        )

        return (
            "OAuth2 authentication failed.",
            400
        )


    try:

        token_data = token_response.json()

        access_token = token_data["access_token"]

    except (ValueError, KeyError):

        print(
            "❌ Invalid OAuth2 response:",
            token_response.text
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
            f"❌ User request error: {e}"
        )

        return (
            "Could not connect to Discord.",
            502
        )


    if user_response.status_code != 200:

        print(
            "❌ Discord user error:",
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

    except (ValueError, KeyError):

        return (
            "Invalid Discord user response.",
            400
        )


    print(
        f"🔎 Verification requested by "
        f"{user.get('username', 'Unknown')} "
        f"({user_id})"
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
                "access_token": access_token
            },

            timeout=15,
        )

    except requests.RequestException as e:

        print(
            f"❌ Guild join error: {e}"
        )

        return (
            "Could not connect to Discord.",
            502
        )


    if join_response.status_code not in (
        200,
        201,
        204
    ):

        print(
            "❌ Guild join error:",
            join_response.status_code,
            join_response.text
        )

        return (
            "Could not join Discord server.",
            400
        )


    print(
        f"✅ User {user_id} joined guild."
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
            f"❌ Role request error: {e}"
        )

        return (
            "Could not connect to Discord.",
            502
        )


    if role_response.status_code not in (
        200,
        204
    ):

        print(
            "❌ Role assignment error:",
            role_response.status_code,
            role_response.text
        )

        return (
            "Verified, but role assignment failed.",
            500
        )


    print(
        f"✅ Verified role assigned to {user_id}"
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
# VERIFY BUTTON
# =========================================================

class VerifyView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

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

    print("=" * 60)

    print(
        f"✅ Discord bot logged in as "
        f"{bot.user} ({bot.user.id})"
    )

    print("=" * 60)


    # =====================================================
    # CHECK CHANNEL ID
    # =====================================================

    try:

        channel_id = int(
            VERIFY_CHANNEL_ID
        )

    except (
        TypeError,
        ValueError
    ):

        print(
            f"❌ VERIFY_CHANNEL_ID is invalid: "
            f"{VERIFY_CHANNEL_ID}"
        )

        return


    # =====================================================
    # FETCH CHANNEL
    # =====================================================

    try:

        channel = await bot.fetch_channel(
            channel_id
        )

    except discord.NotFound:

        print(
            f"❌ Channel does not exist: "
            f"{channel_id}"
        )

        return

    except discord.Forbidden:

        print(
            f"❌ Bot does not have permission "
            f"to access channel {channel_id}"
        )

        return

    except discord.HTTPException as e:

        print(
            f"❌ Discord channel fetch error: "
            f"{e}"
        )

        return

    except Exception as e:

        print(
            f"❌ Unexpected channel error: "
            f"{e}"
        )

        return


    print(
        f"✅ Found verify channel: "
        f"#{channel.name}"
    )


    # =====================================================
    # CHECK PERMISSIONS
    # =====================================================

    try:

        guild = channel.guild

        me = guild.me

        permissions = channel.permissions_for(me)

        print(
            "Bot permissions:"
        )

        print(
            f"  View Channel: "
            f"{permissions.view_channel}"
        )

        print(
            f"  Send Messages: "
            f"{permissions.send_messages}"
        )

        print(
            f"  Embed Links: "
            f"{permissions.embed_links}"
        )


        if not permissions.view_channel:

            print(
                "❌ Bot cannot VIEW this channel."
            )

            return


        if not permissions.send_messages:

            print(
                "❌ Bot cannot SEND messages "
                "in this channel."
            )

            return


        if not permissions.embed_links:

            print(
                "❌ Bot cannot EMBED links "
                "in this channel."
            )

            return


    except Exception as e:

        print(
            f"⚠️ Permission check failed: {e}"
        )


    # =====================================================
    # EMBED
    # =====================================================

    embed = discord.Embed(

        title="🔐 Xác Minh",

        description=(

            "Hãy click vào nút **VERIFY** bên dưới "
            "để chúng tôi xác minh bạn có phải là robot hay không.\n\n"

            "Có thắc mắc xin liên hệ @8zpc.\n"

            "Trân trọng!"
        ),

        color=discord.Color.blurple()
    )


    # =====================================================
    # EMBED IMAGE
    # =====================================================

    embed.set_image(

        url=(
            "https://cdn.discordapp.com/attachments/"
            "1539512033353928759/"
            "1539540467572809759/"
            "Wallpaper_Alchemy_-_Hinh_Nen_4K_Co_Gai_Anime_Haimiya_Mio.jpg"
            "?ex=6a89fc0a"
            "&is=6a88aa8a"
            "&hm=b07f1f1eea99af2c24d851b6f3d4eba79d42ad3844c626fc7813ff4ac52e39ca&"
        )
    )


    # =====================================================
    # FOOTER
    # =====================================================

    embed.set_footer(
        text="Make by 8zpc with love"
    )


    # =====================================================
    # SEND VERIFY MESSAGE
    # =====================================================

    try:

        message = await channel.send(

            embed=embed,

            view=VerifyView()
        )


        print("=" * 60)

        print(
            "✅ VERIFICATION MESSAGE SENT"
        )

        print(
            f"Message ID: {message.id}"
        )

        print("=" * 60)

        print(
            "💡 Add this to Render Environment Variables:"
        )

        print(
            f"VERIFY_MESSAGE_ID={message.id}"
        )


    except discord.Forbidden:

        print(
            "❌ DISCORD FORBIDDEN"
        )

        print(
            "Bot cannot send messages/embeds "
            "in this channel."
        )


    except discord.HTTPException as e:

        print(
            f"❌ DISCORD HTTP ERROR: {e}"
        )


    except Exception as e:

        print(
            f"❌ SEND MESSAGE ERROR: {e}"
        )


# =========================================================
# BOT START
# =========================================================

def start_discord_bot():

    if not DISCORD_TOKEN:

        print(
            "❌ DISCORD_TOKEN is missing."
        )

        return


    try:

        bot.run(
            DISCORD_TOKEN
        )

    except discord.LoginFailure:

        print(
            "❌ Discord token is invalid."
        )

    except Exception as e:

        print(
            f"❌ Discord bot stopped: {e}"
        )


# =========================================================
# START BOT THREAD
# =========================================================

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
        os.getenv(
            "PORT",
            "10000"
        )
    )


    print(
        f"🌐 Flask starting on port {port}"
    )


    app.run(

        host="0.0.0.0",

        port=port
    )
