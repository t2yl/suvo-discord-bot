import json
import os
import random
import discord
from discord.ext import commands
from discord.ui import View, Button

# Constants
TF_DB_FILE = "trueandfalse.json"
QUESTIONS_PER_GAME = 5
ROLE_ID = 1377884248144482375  # if you want to restrict usage by role, else remove checks

def load_tf_db():
    """Load the true/false database, returning [] on error."""
    if not os.path.isfile(TF_DB_FILE):
        return []
    try:
        with open(TF_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[load_tf_db] Error loading {TF_DB_FILE}: {e}")
        return []

class TrueFalseSession:
    def __init__(self, ctx, questions):
        self.ctx = ctx
        self.channel = ctx.channel
        self.player = ctx.author
        self.questions = questions
        self.current_index = 0
        self.score = 0
        self.view = None
        self.message = None

    async def start(self):
        await self.channel.send(f"📝 {self.player.mention}, starting a True/False quiz of {len(self.questions)} questions!")
        await self.next_question()

    async def next_question(self):
        # end if done
        if self.current_index >= len(self.questions):
            return await self.end()
        q = self.questions[self.current_index]
        self.current_index += 1

        # build view with True/False buttons
        self.view = View(timeout=60)

        def make_callback(choice: str):
            async def callback(interaction: discord.Interaction):
                if interaction.user.id != self.player.id:
                    return await interaction.response.send_message("❗ Not your quiz!", ephemeral=True)

                # disable buttons
                for btn in self.view.children:
                    btn.disabled = True
                await interaction.response.edit_message(view=self.view)

                correct = q["answer"]
                if choice.lower() == correct.lower():
                    self.score += 1
                    await interaction.followup.send("✅ Correct!", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Wrong! The correct answer was **{correct}**.", ephemeral=True)

                # short delay then next
                await self.next_question()

            return callback

        btn_true = Button(label="True", style=discord.ButtonStyle.success)
        btn_true.callback = make_callback("True")
        btn_false = Button(label="False", style=discord.ButtonStyle.danger)
        btn_false.callback = make_callback("False")

        self.view.add_item(btn_true)
        self.view.add_item(btn_false)

        # send the question
        content = f"**Q{self.current_index}/{len(self.questions)}:** {q['question']}"
        self.message = await self.channel.send(content, view=self.view)

    async def end(self):
        # clean up
        self.ctx.bot.get_cog("TrueFalseQuiz").active_sessions.pop(self.channel.id, None)
        await self.channel.send(f"🏁 Quiz complete! {self.player.mention} scored **{self.score}/{len(self.questions)}**.")

class TrueFalseQuiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # active sessions per channel
        self.active_sessions: dict[int, TrueFalseSession] = {}

    @commands.command(name="tfstart")
    async def tfstart(self, ctx):
        """Start a 5-question True/False quiz from the latest entries."""
        # optional role check
        # if ROLE_ID and discord.utils.get(ctx.author.roles, id=ROLE_ID) is None:
        #     return await ctx.reply("🚫 You don't have permission to start the quiz.", ephemeral=True)

        if ctx.channel.id in self.active_sessions:
            return await ctx.send("⚠️ A quiz is already in progress in this channel.", delete_after=10)

        data = load_tf_db()
        if not data:
            return await ctx.send("⚠️ No questions available in the database.", delete_after=10)

        # take up to the last QUESTIONS_PER_GAME entries
        latest = data[-QUESTIONS_PER_GAME:]
        # if fewer than needed, will quiz on all
        session = TrueFalseSession(ctx, latest)
        self.active_sessions[ctx.channel.id] = session
        await session.start()

    async def cog_command_error(self, ctx, error):
        await ctx.send(f"❗ Error: {error}", delete_after=10)
        raise error

async def setup(bot):
    await bot.add_cog(TrueFalseQuiz(bot))
