import discord
from discord.ext import commands
import sqlite3
import os
from config import TAG_PERMISSIONS

class MessageTags(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Ensure the directory for tag files exists
        os.makedirs("tag_files", exist_ok=True)

        # Connect to the SQLite database
        self.db = sqlite3.connect("tags.db")
        self.cursor = self.db.cursor()

        # Create the tags table with an extra 'file_path' column
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                tag TEXT PRIMARY KEY,
                message TEXT,
                file_path TEXT
            )
        """)
        # In case an older version of the table exists without 'file_path'
        try:
            self.cursor.execute("ALTER TABLE tags ADD COLUMN file_path TEXT")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        self.db.commit()

    def cog_unload(self):
        self.db.close()

    async def cog_check(self, ctx: commands.Context) -> bool:
        if any(role.id in TAG_PERMISSIONS for role in ctx.author.roles):
            return True
        await ctx.send("You do not have permission to use this command.")
        return False

    @commands.command(name="mtag", help="Create or retrieve a message tag. Usage: !mtag <tag name> [message]")
    async def mtag(self, ctx: commands.Context, tag_name: str, *, message: str = None):
        attachments = ctx.message.attachments

        # No message text and no attachment → retrieve
        if message is None and not attachments:
            self.cursor.execute("SELECT message, file_path FROM tags WHERE tag = ?", (tag_name,))
            row = self.cursor.fetchone()
            if row:
                tag_message, file_path = row

                # If the command was used as a reply
                if ctx.message.reference:
                    try:
                        ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                        # Reply with text and/or file
                        if file_path:
                            await ref_msg.reply(tag_message or "", file=discord.File(file_path), mention_author=False)
                        else:
                            await ref_msg.reply(tag_message, mention_author=False)
                    except Exception as e:
                        await ctx.send(f"Error sending reply: {e}")
                else:
                    # Send in channel
                    if file_path:
                        await ctx.send(content=tag_message or "", file=discord.File(file_path))
                    else:
                        await ctx.send(tag_message)
            else:
                await ctx.send(f"Tag '{tag_name}' not found.")
            return

        # Either message text is provided, or there is an attachment (or both) → store/update
        file_path_to_store = None

        if attachments:
            # Only take the first attachment
            attachment = attachments[0]
            # Build a safe filename: prefix with tag name
            safe_filename = f"{tag_name}_{attachment.filename}"
            destination = os.path.join("tag_files", safe_filename)

            try:
                await attachment.save(destination)
                file_path_to_store = destination
            except Exception as e:
                await ctx.send(f"Failed to save attached file: {e}")
                return

        # Store or update the tag entry (message may be None if only file is attached)
        self.cursor.execute(
            "REPLACE INTO tags (tag, message, file_path) VALUES (?, ?, ?)",
            (tag_name, message, file_path_to_store)
        )
        self.db.commit()
        await ctx.send(f"Tag '{tag_name}' saved.")


async def setup(bot: commands.Bot):
    await bot.add_cog(MessageTags(bot))
