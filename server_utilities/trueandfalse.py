import json
import os
import random

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput

import config  # assumes EMBED_COLOR is defined here

DB_FILE = "trueandfalse.json"
ROLE_ID = 1382623879834370079
PAGE_SIZE = 15  # questions per page now 15


def load_db():
    """Load the TF database, returning [] on any read/parse error."""
    if not os.path.isfile(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[load_db] Failed to load {DB_FILE}: {e}")
        return []


def save_db(data):
    """Save the TF database, logging any write errors."""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"[save_db] Failed to write {DB_FILE}: {e}")


def generate_unique_id(existing_ids):
    """Generate a 6-digit ID not already in existing_ids."""
    while True:
        new_id = "".join(random.choices("0123456789", k=6))
        if new_id not in existing_ids:
            return new_id


class JumpToPageModal(Modal, title="Jump to Page"):
    page_input = TextInput(label="Page number", placeholder="Enter a page number", required=True)

    def __init__(self, paginator: "TFPaginator"):
        super().__init__()
        self.paginator = paginator

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_input.value)
        except ValueError:
            await interaction.response.send_message("🚫 Please enter a valid integer.", ephemeral=True)
            return

        # Delegate to paginator
        await self.paginator.show_page(interaction, page)


class TFPaginator(View):
    def __init__(self, entries, embed_color):
        super().__init__(timeout=None)
        self.entries = entries
        self.embed_color = embed_color
        self.total_pages = (len(entries) - 1) // PAGE_SIZE + 1
        self.current_page = 1

        # initialize button states
        self.prev_button.disabled = True
        if self.total_pages <= 1:
            self.next_button.disabled = True

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary, custom_id="tf_prev")
    async def prev_button(self, button: Button, interaction: discord.Interaction):
        await self.show_page(interaction, self.current_page - 1)

    @discord.ui.button(label="Jump", style=discord.ButtonStyle.primary, custom_id="tf_jump")
    async def jump_button(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(JumpToPageModal(self))

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary, custom_id="tf_next")
    async def next_button(self, button: Button, interaction: discord.Interaction):
        await self.show_page(interaction, self.current_page + 1)

    def get_page_embed(self, page: int) -> discord.Embed:
        # clamp page
        page = max(1, min(page, self.total_pages))
        self.current_page = page

        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        chunk = self.entries[start:end]

        embed = discord.Embed(
            title="True/False Questions",
            color=self.embed_color,
            description="\n".join(
                f"**ID:** `{e['id']}` • **Q:** {e['question']} • **A:** {e['answer']}"
                for e in chunk
            )
        )
        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • Total Questions: {len(self.entries)}")

        # update button states
        self.prev_button.disabled = (self.current_page == 1)
        self.next_button.disabled = (self.current_page == self.total_pages)

        return embed

    async def show_page(self, interaction: discord.Interaction, page: int):
        if not (1 <= page <= self.total_pages):
            await interaction.response.send_message(
                f"⚠️ Page number must be between 1 and {self.total_pages}.",
                ephemeral=True
            )
            return

        embed = self.get_page_embed(page)
        await interaction.response.edit_message(embed=embed, view=self)


class TrueandFalse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        if discord.utils.get(ctx.author.roles, id=ROLE_ID) is None:
            raise commands.MissingRole(ROLE_ID)
        return True

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRole):
            await ctx.reply("🚫 You don't have permission to use this command.", mention_author=False)
        else:
            await ctx.reply(f"❗ An unexpected error occurred: `{error}`", mention_author=False)
            raise error

    @commands.command(name="addtf")
    async def add_tf(self, ctx, *, payload: str):
        """
        Add a True/False question.
        Usage: !addtf question, t/f
        """
        # Expect one comma separating the question and the answer
        try:
            question_part, tf_part = payload.rsplit(",", 1)
        except ValueError:
            return await ctx.reply("🚫 Usage: `!addtf question, t/f`", mention_author=False)

        question = question_part.strip()
        tf = tf_part.strip().lower()

        if tf not in ("true", "false", "t", "f"):
            return await ctx.reply("🚫 Answer must be 'True' or 'False' (or 'T'/'F').", mention_author=False)

        answer = "True" if tf in ("true", "t") else "False"

        data = load_db()
        existing_ids = {e["id"] for e in data}
        new_id = generate_unique_id(existing_ids)
        entry = {"id": new_id, "question": question, "answer": answer}
        data.append(entry)
        save_db(data)

        embed = discord.Embed(
            title="Question Added",
            color=config.EMBED_COLOR,
            description=f"**ID:** `{new_id}`\n**Q:** {question}\n**A:** {answer}"
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="removetf")
    async def remove_tf(self, ctx, question_id: str):
        """Remove a True/False question by ID."""
        data = load_db()
        new_data = [e for e in data if e["id"] != question_id]
        if len(new_data) == len(data):
            await ctx.reply(f"⚠️ No question found with ID `{question_id}`.", mention_author=False)
            return
        save_db(new_data)
        embed = discord.Embed(
            title="Question Removed",
            color=config.EMBED_COLOR,
            description=f"Removed question with ID `{question_id}`."
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="viewtfall")
    async def view_tf_all(self, ctx):
        """View all True/False questions with pagination (15 per page)."""
        data = load_db()
        if not data:
            await ctx.reply("No questions in the database.", mention_author=False)
            return

        paginator = TFPaginator(data, config.EMBED_COLOR)
        embed = paginator.get_page_embed(1)
        await ctx.send(embed=embed, view=paginator)


async def setup(bot):
    await bot.add_cog(TrueandFalse(bot))
