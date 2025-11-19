# renametag.py

import discord
from discord.ext import commands
import sqlite3
import os
from config import TAG_PERMISSIONS  # List of allowed role IDs

class RenameTag(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect("tags.db")
        self.cursor = self.db.cursor()

    def cog_unload(self):
        self.db.close()

    async def cog_check(self, ctx: commands.Context) -> bool:
        if any(role.id in TAG_PERMISSIONS for role in ctx.author.roles):
            return True
        await ctx.send("You do not have permission to use this command.")
        return False

    @commands.command(name="renametag", help="Rename an existing tag. Usage: ?renametag <old_name> <new_name>")
    async def renametag(self, ctx: commands.Context, old_name: str, new_name: str):
        # Check if the old tag exists
        self.cursor.execute("SELECT file_path FROM tags WHERE tag = ?", (old_name,))
        row_old = self.cursor.fetchone()
        if not row_old:
            await ctx.send(f"Tag '{old_name}' not found.")
            return

        # Check if the new tag name is already taken
        self.cursor.execute("SELECT 1 FROM tags WHERE tag = ?", (new_name,))
        if self.cursor.fetchone():
            await ctx.send(f"A tag named '{new_name}' already exists. Choose a different name.")
            return

        old_file_path = row_old[0]
        new_file_path = None

        # If a file is attached, rename it on disk
        if old_file_path:
            if os.path.exists(old_file_path):
                old_basename = os.path.basename(old_file_path)
                parts = old_basename.split("_", 1)
                remainder = parts[1] if len(parts) == 2 else old_basename
                new_basename = f"{new_name}_{remainder}"
                new_file_path = os.path.join(os.path.dirname(old_file_path), new_basename)
                try:
                    os.rename(old_file_path, new_file_path)
                except Exception as e:
                    await ctx.send(f"Failed to rename attached file: {e}")
                    return
            else:
                new_file_path = None

        # Update the database
        if new_file_path is not None:
            self.cursor.execute(
                "UPDATE tags SET tag = ?, file_path = ? WHERE tag = ?",
                (new_name, new_file_path, old_name)
            )
        else:
            self.cursor.execute(
                "UPDATE tags SET tag = ? WHERE tag = ?",
                (new_name, old_name)
            )
        self.db.commit()
        await ctx.send(f"Tag '{old_name}' has been renamed to '{new_name}'.")

async def setup(bot: commands.Bot):
    await bot.add_cog(RenameTag(bot))
