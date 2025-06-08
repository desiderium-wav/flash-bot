import discord
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True

# Load env variables
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("FLASH_CHANNEL_ID"))
ROLE_ID = int(os.getenv("FLASH_ROLE_ID"))

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"[+] Logged in as {client.user.name}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != CHANNEL_ID:
        return

    # Check if the message contains an image (embed or attachment)
    has_image = False

    for embed in message.embeds:
        if embed.image and embed.image.url:
            has_image = True
            break

    if message.attachments:
        has_image = True

    if has_image:
        print(f"[+] Image detected from {message.author}. Flash ping sent.")
        role = message.guild.get_role(ROLE_ID)
        if role:
            await message.channel.send(f"{role.mention}")

    # Start a 5-minute delete timer for ANY message
    print(f"[~] Message from {message.author} scheduled for deletion in 5 minutes.")
    await asyncio.sleep(300)  # 5 minutes

    try:
        await message.delete()
        print(f"[-] Message from {message.author} deleted.")
    except discord.NotFound:
        print("[x] Message already deleted.")
    except discord.Forbidden:
        print("[x] Missing permissions to delete the message.")
    except Exception as e:
        print(f"[x] Error deleting message: {e}")

client.run(TOKEN)
