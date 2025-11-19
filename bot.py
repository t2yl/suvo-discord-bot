import discord
from discord.ext import commands
import os
import config
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = commands.Bot(
    command_prefix="!",
    intents=discord.Intents.all(),
    help_command=None,
    application_id=config.APPLICATION_ID
)
TARGET_GUILD_ID = config.GUILD_ID

async def load_all_extensions():
    folders = {
        "precommands":        "precommands",
        "server_utilities":   "server_utilities",
        "role_commands":      "role_commands",
        "activity_listeners": "activity_listeners",
        "tag_commands":       "tag_commands",
        "ticket_commands":    "ticket_commands",
        "appcommands":        "appcommands", # <--- ADD THIS LINE
    }
    for folder_name, module_path in folders.items():
        if not os.path.isdir(folder_name):
            continue
        for filename in os.listdir(folder_name):
            if not filename.endswith(".py"):
                continue
            if filename == "__init__.py":
                continue
            ext = filename[:-3]  # remove “.py”
            full_module = f"{module_path}.{ext}"
            try:
                await bot.load_extension(full_module)
                logger.info(f"Loaded extension: {full_module}")
            except Exception as e:
                logger.error(f"Error loading extension {full_module}: {e}")

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online)
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        guild_obj = discord.Object(id=TARGET_GUILD_ID)
        await bot.tree.sync(guild=guild_obj)
        logger.info(f"🔄 Synced application commands to guild {TARGET_GUILD_ID}.")
    except Exception as e:
        logger.error(f"Failed to sync commands to guild {TARGET_GUILD_ID}: {e}")

@bot.event
async def on_guild_join(guild):
    if guild.id != TARGET_GUILD_ID:
        logger.info(f"Joined unauthorized guild '{guild.name}' (ID: {guild.id}), leaving...")
        await guild.leave()
    else:
        logger.info(f"Joined target guild '{guild.name}' (ID: {guild.id})")

async def main():
    await load_all_extensions()
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    asyncio.run(main())