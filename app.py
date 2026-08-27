
import os
import threading
from urllib.parse import urlencode

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

# Optional:
# ID message verify đã tồn tại
VERIFY_MESSAGE_ID = os.getenv("VERIFY_MESSAGE_ID")


DISCORD_API = "https://discord.com/api/v10"


# =========================================================
# CHECK ENV
# =========================================================

ENV_VARS = {
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
    for name, value in ENV_VARS.items()
    if not value
]


if missing:

    print("")
    print("=" * 60)
    print("❌ MISSING ENVIRONMENT VARIABLES")
    print("=" * 60)

    for name in missing:
        print(f" - {name}")

    print("=" * 60)
    print("")


# =========================================================
# AUTO VERIFY URL
# =========================================================

if not VERIFY_URL and REDIRECT_URI:

    VERIFY_URL = (
        REDIRECT_URI
        .rsplit("/", 1)[0]
        + "/verify"
    )


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# DISCORD OAUTH VERIFY
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


    return redirect(
        oauth_url
    )


# =========================================================
# OAUTH CALLBACK
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
    # EXCHANGE CODE
    # =====================================================

    try:

        response = requests.post(

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
            f"❌ Token request error: {e}"
        )

        return (
            "Could not connect to Discord.",
            502
        )


    if response.status_code != 200:

        print(
            "❌ OAuth token error:",
            response.status_code,
            response.text
        )

        return (
            "OAuth2 authentication failed.",
            400
        )


    try:

        token_data = response.json()

        access_token = token_data[
            "access_token"
        ]


    except (
        ValueError,
        KeyError
    ):

        print(
            "❌ Invalid OAuth response."
        )

        return (
            "Invalid OAuth2 response.",
            400
        )


    # =====================================================
    # GET USER
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


    except (
        ValueError,
        KeyError
    ):

        return (
            "Invalid Discord user response.",
            400
        )


    username = (
        user.get("global_name")
        or user.get("username")
        or "User"
    )


    print(
        f"🔎 Verification: "
        f"{username} ({user_id})"
    )


    # =====================================================
    # JOIN SERVER
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
            f"❌ Guild join request error: {e}"
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
        f"✅ User {user_id} joined server."
    )


    # =====================================================
    # GIVE ROLE
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
        f"✅ Verified role assigned "
        f"to {user_id}"
    )


    # =====================================================
    # SUCCESS
    # =====================================================

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

class VerifyView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )


        self.add_item(

            discord.ui.Button(

                label="VERIFY",

                emoji="✅",

                style=
                    discord.ButtonStyle.link,

                url=VERIFY_URL
            )
        )


# =========================================================
# EMBED
# =========================================================

def create_verify_embed():

    embed = discord.Embed(

        title="🔐 Xác Minh",

        description=(

            "Hãy click vào nút **VERIFY** "
            "bên dưới để xác minh bạn có phải "
            "là robot hay không.\n\n"

            "Có thắc mắc xin liên hệ @8zpc.\n"

            "Trân trọng!"
        ),

        color=discord.Color.blurple()
    )


    embed.set_image(

        url=(
            "https://cdn.discordapp.com/attachments/"
            "1539512033353928759/"
            "1539540467572809759/"
            "Wallpaper_Alchemy_-_Hinh_Nen_4K_Co_Gai_Anime_Haimiya_Mio.jpg"
        )
    )


    embed.set_footer(

        text="Make by 8zpc with love"
    )


    return embed


# =========================================================
# FIND CHANNEL
# =========================================================

async def get_verify_channel():

    if not VERIFY_CHANNEL_ID:

        print(
            "❌ VERIFY_CHANNEL_ID is empty."
        )

        return None


    try:

        channel_id = int(
            VERIFY_CHANNEL_ID
        )

    except (
        TypeError,
        ValueError
    ):

        print(
            f"❌ Invalid VERIFY_CHANNEL_ID: "
            f"{VERIFY_CHANNEL_ID}"
        )

        return None


    # -----------------------------------------------------
    # CACHE
    # -----------------------------------------------------

    channel = bot.get_channel(
        channel_id
    )


    if channel:

        return channel


    # -----------------------------------------------------
    # API
    # -----------------------------------------------------

    try:

        channel = await bot.fetch_channel(
            channel_id
        )

        return channel


    except discord.NotFound:

        print(
            f"❌ Channel {channel_id} "
            f"does not exist."
        )


    except discord.Forbidden:

        print(
            f"❌ Bot cannot access "
            f"channel {channel_id}."
        )


    except discord.HTTPException as e:

        print(
            f"❌ Discord API error "
            f"while fetching channel: {e}"
        )


    return None


# =========================================================
# CHECK PERMISSIONS
# =========================================================

def check_channel_permissions(
    channel
):

    try:

        guild = channel.guild

        member = guild.me


        if member is None:

            print(
                "❌ Could not get bot member."
            )

            return False


        permissions = (
            channel.permissions_for(
                member
            )
        )


        print("")
        print("----------------------------------------")
        print("BOT CHANNEL PERMISSIONS")
        print("----------------------------------------")

        print(
            f"View Channel   : "
            f"{permissions.view_channel}"
        )

        print(
            f"Send Messages  : "
            f"{permissions.send_messages}"
        )

        print(
            f"Embed Links    : "
            f"{permissions.embed_links}"
        )

        print("----------------------------------------")


        if not permissions.view_channel:

            print(
                "❌ Missing View Channel."
            )

            return False


        if not permissions.send_messages:

            print(
                "❌ Missing Send Messages."
            )

            return False


        if not permissions.embed_links:

            print(
                "❌ Missing Embed Links."
            )

            return False


        return True


    except Exception as e:

        print(
            f"❌ Permission check error: {e}"
        )

        return False


# =========================================================
# SEND VERIFY MESSAGE
# =========================================================

async def send_verify_message():

    print("")
    print("=" * 60)
    print("🔐 VERIFY MESSAGE SYSTEM")
    print("=" * 60)


    channel = await get_verify_channel()


    if channel is None:

        print(
            "❌ Verify channel unavailable."
        )

        return


    print(
        f"✅ Channel: #{channel.name}"
    )

    print(
        f"✅ Channel ID: {channel.id}"
    )

    print(
        f"✅ Guild: {channel.guild.name}"
    )

    print(
        f"✅ Guild ID: {channel.guild.id}"
    )


    # =====================================================
    # CHECK GUILD
    # =====================================================

    if str(channel.guild.id) != str(GUILD_ID):

        print("")
        print(
            "❌ CHANNEL KHÔNG THUỘC GUILD_ID."
        )

        print(
            f"GUILD_ID env: "
            f"{GUILD_ID}"
        )

        print(
            f"Channel guild: "
            f"{channel.guild.id}"
        )

        return


    # =====================================================
    # CHECK PERMISSIONS
    # =====================================================

    if not check_channel_permissions(
        channel
    ):

        return


    # =====================================================
    # EXISTING MESSAGE
    # =====================================================

    if VERIFY_MESSAGE_ID:

        try:

            old_message = await channel.fetch_message(
                int(VERIFY_MESSAGE_ID)
            )


            print("")
            print(
                "✅ Existing verification "
                "message found."
            )

            print(
                f"Message ID: "
                f"{old_message.id}"
            )

            print(
                "⏭️ Không gửi message mới."
            )

            print("=" * 60)

            return


        except discord.NotFound:

            print(
                "⚠️ VERIFY_MESSAGE_ID không "
                "còn tồn tại."
            )


        except (
            ValueError,
            TypeError
        ):

            print(
                "⚠️ VERIFY_MESSAGE_ID không hợp lệ."
            )


        except discord.HTTPException as e:

            print(
                f"⚠️ Could not check old "
                f"message: {e}"
            )


    # =====================================================
    # CREATE MESSAGE
    # =====================================================

    embed = create_verify_embed()

    view = VerifyView()


    print("")
    print(
        "📨 Sending verification message..."
    )


    try:

        message = await channel.send(

            embed=embed,

            view=view
        )


    except discord.Forbidden:

        print("")
        print(
            "❌ DISCORD FORBIDDEN."
        )

        print(
            "Bot không có quyền gửi message."
        )

        return


    except discord.HTTPException as e:

        print("")
        print(
            f"❌ DISCORD HTTP ERROR: {e}"
        )

        return


    except Exception as e:

        print("")
        print(
            f"❌ UNKNOWN SEND ERROR: {e}"
        )

        return


    # =====================================================
    # SUCCESS
    # =====================================================

    print("")
    print("=" * 60)
    print(
        "✅ VERIFY MESSAGE SENT SUCCESSFULLY"
    )
    print("=" * 60)

    print(
        f"Message ID: {message.id}"
    )

    print(
        f"Channel ID: {channel.id}"
    )

    print(
        f"Channel URL:"
    )

    print(
        f"https://discord.com/channels/"
        f"{channel.guild.id}/"
        f"{channel.id}/"
        f"{message.id}"
    )

    print("")
    print(
        "Render Environment Variable:"
    )

    print(
        f"VERIFY_MESSAGE_ID={message.id}"
    )

    print("=" * 60)


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print("")
    print("=" * 60)
    print("🤖 DISCORD BOT ONLINE")
    print("=" * 60)

    print(
        f"Username : {bot.user}"
    )

    print(
        f"Bot ID   : {bot.user.id}"
    )

    print(
        f"Servers  : {len(bot.guilds)}"
    )


    # -----------------------------------------------------
    # LIST SERVERS
    # -----------------------------------------------------

    for guild in bot.guilds:

        print(
            f"  • {guild.name} "
            f"({guild.id})"
        )


    print("=" * 60)


    # -----------------------------------------------------
    # CHECK GUILD ID
    # -----------------------------------------------------

    if not GUILD_ID:

        print(
            "❌ GUILD_ID is missing."
        )

        return


    try:

        guild_id = int(
            GUILD_ID
        )

    except ValueError:

        print(
            f"❌ Invalid GUILD_ID: "
            f"{GUILD_ID}"
        )

        return


    # -----------------------------------------------------
    # GET GUILD
    # -----------------------------------------------------

    guild = bot.get_guild(
        guild_id
    )


    if guild is None:

        print("")
        print(
            "❌ BOT KHÔNG Ở TRONG SERVER."
        )

        print(
            f"Required Guild ID: "
            f"{guild_id}"
        )

        print("")
        print(
            "Bot hiện đang ở:"
        )


        for g in bot.guilds:

            print(
                f"  • {g.name} "
                f"({g.id})"
            )


        return


    print(
        f"✅ Server found: "
        f"{guild.name}"
    )


    # -----------------------------------------------------
    # SEND VERIFY MESSAGE
    # -----------------------------------------------------

    await send_verify_message()


# =========================================================
# START BOT
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
            "❌ DISCORD TOKEN IS INVALID."
        )


    except discord.PrivilegedIntentsRequired:

        print(
            "❌ Discord requires privileged intents."
        )


    except Exception as e:

        print(
            f"❌ Discord bot stopped: {e}"
        )


# =========================================================
# START DISCORD THREAD
# =========================================================

bot_thread = threading.Thread(

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


    print("")
    print("=" * 60)
    print(
        f"🌐 Flask starting on port {port}"
    )
    print("=" * 60)


    app.run(

        host="0.0.0.0",

        port=port
    )
