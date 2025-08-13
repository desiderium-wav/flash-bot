import os
import io
import asyncio
import discord
from discord.ext import commands
from collections import OrderedDict

# Load environment variables directly from Render
TOKEN = os.environ["DISCORD_TOKEN"]
FLASH_CHANNEL_ID = int(os.environ["FLASH_CHANNEL_ID"])
FLASH_PING_ROLE_ID = int(os.environ["FLASH_PING_ROLE_ID"])

# Allowed image file extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Active batches stored in order of creation: batch_id -> {start_message, messages}
batches = OrderedDict()


async def enforce_spoiler_with_webhook(message: discord.Message):
    """Only reupload images if they are not already marked as spoilers."""
    image_attachments = [att for att in message.attachments if is_image_attachment(att)]
    if not image_attachments:
        return message  # No image, nothing to do

    # Check if all images already have spoilers
    all_spoilers = all(att.is_spoiler() for att in image_attachments)
    if all_spoilers:
        return message  # Already spoilered, do nothing

    # Proceed to reupload via webhook
    channel = message.channel
    webhook = await channel.create_webhook(name="FlashSpoilerBot")

    try:
        files = []
        for attachment in image_attachments:
            img_bytes = await attachment.read()
            spoiler_filename = f"SPOILER_{attachment.filename}" if not attachment.is_spoiler() else attachment.filename
            files.append(discord.File(io.BytesIO(img_bytes), filename=spoiler_filename))

        await message.delete()
        await webhook.send(
            content=message.content or None,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            files=files
        )

        history = [m async for m in channel.history(limit=1)]
        return history[0] if history else None

    finally:
        await webhook.delete()


async def start_flash_timer(batch_id: int):
    """Start a 5-minute timer for a flash batch."""
    await asyncio.sleep(300)  # 5 minutes

    batch = batches.pop(batch_id, None)
    if not batch:
        return

    try:
        await batch["start_message"].channel.delete_messages(batch["messages"])
    except discord.HTTPException:
        for msg in batch["messages"]:
            try:
                await msg.delete()
            except discord.HTTPException:
                pass


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id != FLASH_CHANNEL_ID:
        return

    image_attachments = [att for att in message.attachments if is_image_attachment(att)]

    if image_attachments:
        new_message = await enforce_spoiler_with_webhook(message)
        if not new_message:
            return

        # Send Flash Ping and store the ping message in the batch
        flash_ping_role = message.guild.get_role(FLASH_PING_ROLE_ID)
        ping_message = None
        if flash_ping_role:
            ping_message = await message.channel.send(f"{flash_ping_role.mention}")

        # Create new batch
        batch_id = new_message.id
        batches[batch_id] = {
            "start_message": new_message,
            "messages": [new_message],
        }

        if ping_message:
            batches[batch_id]["messages"].append(ping_message)

        bot.loop.create_task(start_flash_timer(batch_id))

    else:
        if not batches:
            await message.delete()
        else:
            latest_batch_id = next(reversed(batches))
            batches[latest_batch_id]["messages"].append(message)

# Admin-only debug command to show active batches
@bot.command(name="showbatches")
async def show_batches(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not batches:
        await ctx.send("📭 No active batches.")
        return

    msg_lines = []
    for idx, (batch_id, batch_data) in enumerate(batches.items(), start=1):
        msg_lines.append(
            f"**Batch {idx}**\n"
            f"- Start message ID: `{batch_id}`\n"
            f"- Messages in batch: `{len(batch_data['messages'])}`"
        )

    await ctx.send("\n\n".join(msg_lines))


bot.run(TOKEN)
