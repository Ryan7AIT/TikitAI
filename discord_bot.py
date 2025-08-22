import os
import discord
import aiohttp
import asyncio
from discord import Intents

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"🤖 Bot is online as {client.user}")

@client.event
async def on_message(message):
    print(f"Received message: {message.content} from {message.author.name}")
    if message.author.bot:
        return

    if message.content == 'Tell them what u can do?':
        await message.channel.send(
            "**Hey there! I'm Aidly**, your laid-back support buddy here at DATAFIRST. 😊\n\n"
            "I’ve been around long enough to know this system like the back of my hand—quirks, features, and all.\n\n"
            "Need help finding something? Debugging a weird edge case? Just tag me and fire away.\n"
            "I’ll dig into the knowledge base and get you a solid answer—or let you know if I need more to go on.\n\n"
            "_Go ahead, ask me anything. I’ve got your back!_ 💪"
        )
        return
    # Check if the bot was mentioned
    if client.user in message.mentions:
        username = message.author.name.lower()  # e.g. "Ryan" becomes "ryan"
        print(f"Message from {username}: {message.content}")
        if username == "ryan_ait":
            await message.channel.send("Hey, how can I help you, my boss? 🫡")
        else:
            await message.channel.send("Sorry, I only answer to my boss. 🛑")


client.run(DISCORD_BOT_TOKEN)
