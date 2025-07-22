import discord
import aiohttp
import asyncio

DISCORD_BOT_TOKEN = "DISCORD_TOKEN.GZzSuM.htAnugBUtUExXORM5AdLRVPTiVTG6lfW-OXRec"
FLASK_API_URL = "http://localhost:8000"  

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"🤖 Bot is online as {client.user}")

@client.event
@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Check if the bot was mentioned
    if client.user in message.mentions:
        username = message.author.name.lower()  # e.g. "Ryan" becomes "ryan"
        
        if username == "ryan_ait":
            await message.channel.send("Hey, how can I help you, my boss? 🫡")
        else:
            await message.channel.send("Sorry, I only answer to my boss. 🛑")


client.run(DISCORD_BOT_TOKEN)
