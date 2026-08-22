import os
import discord

from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
VERIFY_URL = os.getenv("VERIFY_URL")
VERIFY_CHANNEL_ID = int(os.getenv("VERIFY_CHANNEL_ID"))

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
    print(f"Logged in as {bot.user}")

    channel = bot.get_channel(VERIFY_CHANNEL_ID)

    if channel is None:
        return

    embed = discord.Embed(
        title="🔐 Server Verification",
        description=(
            "Click **VERIFY** below to verify your "
            "Discord account."
        ),
        color=discord.Color.blurple()
    )

    await channel.send(
        embed=embed,
        view=VerifyView()
    )


bot.run(TOKEN)
