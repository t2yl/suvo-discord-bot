import discord
from discord.ext import commands
import sqlite3
import difflib

class TagListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect("tags.db")
        self.cursor = self.db.cursor()

    def cog_unload(self):
        self.db.close()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.content.startswith("?tag"):
            return

        # Extract search terms (after "?tag")
        parts = message.content.split()[1:]
        if not parts:
            return

        terms = [p.lower() for p in parts]
        exact_tag = "-".join(terms)

        # Fetch all tags from database
        self.cursor.execute("SELECT tag, message, file_path FROM tags")
        all_rows = self.cursor.fetchall()
        all_tags = [row[0] for row in all_rows]

        # 1. Exact match
        self.cursor.execute(
            "SELECT tag, message, file_path FROM tags WHERE tag = ?",
            (exact_tag,)
        )
        row = self.cursor.fetchone()
        if row:
            _, tag_message, file_path = row
            await self._send_tag_response(message, tag_message, file_path)
            return

        # 2. Partial match: tag contains all search terms (order-agnostic)
        like_clauses = " AND ".join(["tag LIKE ?"] * len(terms))
        params = [f"%{term}%" for term in terms]
        query = f"SELECT tag, message, file_path FROM tags WHERE {like_clauses}"
        self.cursor.execute(query, params)
        partial_results = self.cursor.fetchall()

        if len(partial_results) == 1:
            _, tag_message, file_path = partial_results[0]
            await self._send_tag_response(message, tag_message, file_path)
            return

        if len(partial_results) > 1:
            suggestions = [row[0].replace("-", " ").title() for row in partial_results]
            suggestion_text = "\n".join(f"- {s}" for s in suggestions)
            response = (
                f"Multiple tags match your query '{' '.join(parts)}'.\n"
                "Did you mean:\n"
                f"{suggestion_text}"
            )
            await message.channel.send(response)
            return

        # 3. Fuzzy match (suggest closest tags by similarity)
        #    Compare user input (joined with hyphens) against all_tags
        fuzzy_matches = difflib.get_close_matches(
            exact_tag, all_tags, n=5, cutoff=0.6
        )

        # If no fuzzy matches for exact_tag, also try matching against each individual term
        if not fuzzy_matches:
            for term in terms:
                matches = difflib.get_close_matches(term, all_tags, n=5, cutoff=0.6)
                for m in matches:
                    if m not in fuzzy_matches:
                        fuzzy_matches.append(m)

        if fuzzy_matches:
            suggestions = [tag.replace("-", " ").title() for tag in fuzzy_matches]
            suggestion_text = "\n".join(f"- {s}" for s in suggestions)
            response = (
                f"No direct tag found for '{' '.join(parts)}'.\n"
                "Did you mean:\n"
                f"{suggestion_text}"
            )
            await message.channel.send(response)
            return

        # 4. No matches at all
        await message.channel.send(f"Tag '{' '.join(parts)}' not found. Sorry!")

    async def _send_tag_response(self, message: discord.Message, tag_message: str, file_path: str):
        """
        Send the tag response as a reply if the original message was a reply,
        otherwise send it in-channel. Handles both text and file attachments.
        """
        async def send_to(destination):
            if file_path:
                try:
                    if tag_message:
                        await destination.reply(tag_message, file=discord.File(file_path), mention_author=False)
                    else:
                        await destination.reply(file=discord.File(file_path), mention_author=False)
                except Exception as e:
                    await message.channel.send(f"Error sending file: {e}")
            else:
                try:
                    await destination.reply(tag_message, mention_author=False)
                except Exception as e:
                    await message.channel.send(f"Error sending message: {e}")

        if message.reference:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                await send_to(ref_msg)
            except Exception as e:
                await message.channel.send(f"Error fetching referenced message: {e}")
        else:
            if file_path:
                try:
                    if tag_message:
                        await message.channel.send(content=tag_message, file=discord.File(file_path))
                    else:
                        await message.channel.send(file=discord.File(file_path))
                except Exception as e:
                    await message.channel.send(f"Error sending file: {e}")
            else:
                try:
                    await message.channel.send(tag_message)
                except Exception as e:
                    await message.channel.send(f"Error sending message: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(TagListener(bot))
