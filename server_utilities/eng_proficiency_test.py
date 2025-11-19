import discord
from discord.ext import commands
import os
import json
import asyncio
import random
import time

class EngProficiencyTest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register persistent view so the "Take Proficiency" button survives restarts
        self.bot.add_view(TakeTestView(self))

    @commands.command(name="eng_proficiency-test")
    @commands.has_permissions(administrator=True)
    async def proficiency_test(self, ctx: commands.Context):
        """
        Admin-only command. Sends an embed with rules & a 'Take Proficiency' button.
        When a user clicks the button, a private thread is created, and they can start the test.
        """
        rules_embed = discord.Embed(
            title="📘 English Proficiency Test",
            description=(
                "Welcome to the English Proficiency Test!\n\n"
                "**Rules & Regulations:**\n"
                "• You will have 90 seconds per question once you start.\n"
                "• Reply by sending only the option number (e.g., 1, 2, 3, 4).\n"
                "• Any other messages (invalid numbers or text) will be ignored.\n"
                "• Once you begin, no one else can participate in your test thread.\n"
                "• At the end, you will receive your score, time breakdown, and answer key.\n\n"
                "Click **Take Proficiency** below to begin!"
            ),
            color=0xffffff
        )
        rules_embed.set_footer(text="Only one test per session. Make sure you are ready before clicking.")
        
        # Send the embed with the persistent view
        await ctx.send(embed=rules_embed, view=TakeTestView(self))

    @proficiency_test.error
    async def proficiency_test_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need Administrator permissions to use this command.")

    async def run_test(self, user: discord.Member, thread: discord.Thread, questions: list):
        """
        Core test logic: ask questions in the private thread, collect valid responses, calculate score.
        """
        # Send intro embed inside thread
        intro = discord.Embed(
            title="Test Started!",
            description=(
                f"{user.mention}, the test is now live.\n"
                "⏱️ You have 90 seconds per question.\n"
                "✅ Reply using only the option number (1, 2, 3, 4).\n"
                "📌 Invalid inputs will be ignored.\n"
                "Good luck!"
            ),
            color=0xffffff
        )
        await thread.send(embed=intro)

        score = 0
        total = len(questions)
        answer_key = []
        time_per_question = []

        for idx, q in enumerate(questions, start=1):
            question_text = q.get("question")
            options = q.get("options", [])
            answer_idx = q.get("answer_index", 0)

            embed = discord.Embed(
                title=f"Question {idx}/{total}",
                description=f"```{question_text}```",
                color=discord.Color.light_grey()
            )
            for i, opt in enumerate(options, start=1):
                embed.add_field(name=f"{i}.", value=opt, inline=False)

            await thread.send(embed=embed)
            q_start = time.time()
            deadline = q_start + 90

            user_choice = None
            while time.time() < deadline:
                try:
                    time_left = deadline - time.time()
                    msg = await self.bot.wait_for(
                        'message',
                        check=lambda m: m.author == user and m.channel == thread,
                        timeout=time_left
                    )
                except asyncio.TimeoutError:
                    break  # No valid response within 90s

                content = msg.content.strip()
                if content.isdigit():
                    choice = int(content)
                    if 1 <= choice <= len(options):
                        user_choice = choice
                        q_time = time.time() - q_start
                        time_per_question.append(q_time)

                        if choice - 1 == answer_idx:
                            score += 1
                            response = "✅ Correct!"
                            color = discord.Color.green()
                        else:
                            response = f"❌ Incorrect! The correct answer was **{answer_idx + 1}. {options[answer_idx]}**."
                            color = discord.Color.red()

                        await thread.send(embed=discord.Embed(description=response, color=color))
                        break  # move to next question
                    else:
                        # Ignore invalid numeric input outside range
                        continue
                else:
                    # Ignore non-numeric input
                    continue
            else:
                # Time expired without valid answer
                time_per_question.append(90.0)
                await thread.send(
                    embed=discord.Embed(
                        description=f"⏰ Time's up! The correct answer was **{answer_idx + 1}. {options[answer_idx]}**.",
                        color=discord.Color.orange()
                    )
                )

            answer_key.append(f"Q{idx}: {answer_idx + 1}. {options[answer_idx]}")

        # Calculate percentage and level
        percent = (score / total) * 100
        if percent <= 40:
            level = "Beginner"
        elif percent <= 75:
            level = "Intermediate"
        else:
            level = "Advanced"

        total_time = sum(time_per_question)

        # Send result embed
        result_embed = discord.Embed(
            title="✅ Test Completed",
            color=discord.Color.green()
        )
        result_embed.add_field(name="Score", value=f"{score}/{total} ({percent:.2f}%)", inline=False)
        result_embed.add_field(name="Level", value=level, inline=False)
        result_embed.add_field(name="Total Time", value=f"{int(total_time)} seconds", inline=False)
        await thread.send(embed=result_embed)

        # Time breakdown embed
        details = "\n".join([f"Q{i+1}: {int(t)}s" for i, t in enumerate(time_per_question)])
        await thread.send(embed=discord.Embed(
            title="⏱️ Time per Question",
            description=details,
            color=discord.Color.light_grey()
        ))

        # Lock the thread at the end
        try:
            await thread.edit(locked=True)
        except Exception:
            pass


class TakeTestView(discord.ui.View):
    def __init__(self, cog: EngProficiencyTest):
        super().__init__(timeout=None)  # Persistent view; no timeout
        self.cog = cog

    @discord.ui.button(label="Take Proficiency Test", style=discord.ButtonStyle.success, custom_id="take_eng_proficiency")
    async def take_proficiency(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        channel = interaction.channel

        # Load random question set (1 of 5 files)
        question_file = f"english_proficiency_questions_{random.randint(1, 5)}.json"
        try:
            with open(question_file, "r", encoding="utf-8") as f:
                questions = json.load(f)
        except Exception:
            await interaction.response.send_message(
                "⚠️ Failed to load the test questions. Please try again later.",
                ephemeral=True
            )
            return

        # Create private thread and add the user
        try:
            thread = await channel.create_thread(
                name=f"{user.name}-proficiency-test",
                type=discord.ChannelType.private_thread,
                auto_archive_duration=60
            )
            await thread.add_user(user)


        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ I do not have permission to create threads.",
                ephemeral=True
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "⚠️ Failed to create a thread. Please try again later.",
                ephemeral=True
            )
            return

        # Acknowledge button press
        await interaction.response.send_message(
            f"✅ {user.mention}, your test thread has been created: {thread.mention}",
            ephemeral=True
        )

        # Send test details embed inside thread with a Start Test button
        details_embed = discord.Embed(
            title="🔖 Test Instructions",
            description=(
                "• You will have 90 seconds per question.\n"
                "• Reply with only the option number (e.g., 1, 2, 3, 4).\n"
                "• Invalid messages will be ignored.\n\n"
                "Click **Start Test** below to begin. If you do not click within 90 seconds, this thread will be deleted."
            ),
            color=0xffffff
        )
        details_embed.set_footer(text="Make sure you're ready before clicking Start Test.")

        view = StartTestView(self.cog, user, thread, questions)
        await thread.send(embed=details_embed, view=view)


class StartTestView(discord.ui.View):
    def __init__(self, cog: EngProficiencyTest, user: discord.Member, thread: discord.Thread, questions: list):
        super().__init__(timeout=90)
        self.cog = cog
        self.user = user
        self.thread = thread
        self.questions = questions
        self.test_started = False

    @discord.ui.button(label="Start Test", style=discord.ButtonStyle.success, custom_id="start_eng_test")
    async def start_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message(
                "❌ Only the user who clicked 'Take Proficiency' can start this test.",
                ephemeral=True
            )
            return

        self.test_started = True
        await interaction.response.defer()  # Acknowledge immediately to avoid "This interaction failed."

        # Disable the button to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Begin the test
        await self.cog.run_test(self.user, self.thread, self.questions)

    async def on_timeout(self):
        # If the user didn't start the test within 90s, delete the thread
        if not self.test_started:
            try:
                await self.thread.delete()
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(EngProficiencyTest(bot))
