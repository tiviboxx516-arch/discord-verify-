import os
import requests

from flask import Flask, redirect, render_template, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GUILD_ID = os.getenv("GUILD_ID")
VERIFIED_ROLE_ID = os.getenv("VERIFIED_ROLE_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")

DISCORD_API = "https://discord.com/api/v10"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/verify")
def verify():
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

    # Đổi code lấy access token
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

    if token.status_code != 200:
        return "OAuth2 authentication failed.", 400

    access_token = token.json()["access_token"]

    # Lấy thông tin Discord account
    user_request = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=15,
    )

    if user_request.status_code != 200:
        return "Could not get Discord account.", 400

    user = user_request.json()
    user_id = user["id"]

    # Add user vào server
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

    if join.status_code not in (200, 201, 204):
        return "Could not join Discord server.", 400

    # Cấp role Verified
    role = requests.put(
        f"{DISCORD_API}/guilds/{GUILD_ID}/members/"
        f"{user_id}/roles/{VERIFIED_ROLE_ID}",
        headers={
            "Authorization": f"Bot {DISCORD_TOKEN}"
        },
        timeout=15,
    )

    if role.status_code not in (200, 204):
        return "Verified, but role assignment failed.", 500

    username = user.get("global_name") or user.get("username")

    return render_template(
        "success.html",
        username=username
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )
