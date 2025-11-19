import discord
from discord.ext import commands
import json
import os
import asyncio
import datetime
from datetime import timezone, timedelta
from discord.ui import View, Button
import config  # Ensure config.EMBED_COLOR is defined as an integer (e.g., 0x2ecc71)

class KorQuizOfTheDay(commands.Cog):
    QUIZ_CHANNEL_ID = 1379145101187485899             # Replace with your quiz channel ID
    QUIZ_LEADERBOARD_CHANNEL_ID = 1379152409875710062  # Replace with your leaderboard channel ID

    LOCALE_TZ = timezone(timedelta(hours=1))  # UTC+1 for BST (adjust if needed)
    START_DATE = datetime.date(2025, 1, 1)

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        cog_folder = os.path.dirname(__file__)
        base_path = os.path.abspath(os.path.join(cog_folder, ".."))

        # Paths for persistent JSON databases
        self.answer_db_path = os.path.join(cog_folder, "kor_quiz_answer_users.json")
        self.leaderboard_db_path = os.path.join(cog_folder, "kor_quiz_leaderboard.json")
        self.progress_path = os.path.join(cog_folder, "kor_progress.json")

        # Load quiz entries from kor_quiz.json
        with open(os.path.join(base_path, "kor_quiz.json"), encoding="utf-8") as f:
            self.quizzes = json.load(f)

        # Load or initialize persistent state
        self._load_progress()
        self._load_answered()
        self._load_leaderboard()

        # In-memory state for today’s quiz
        self.current_answered = set(self.answered_data.get("answered", []))
        self.current_correct = list(self.leaderboard_data.get("correct", []))
        self.leaderboard_msg = None
        self.quiz_msg = None

        self.task_started = False

    def _load_progress(self):
        default = {"quizzes": 0}
        if os.path.isfile(self.progress_path):
            try:
                with open(self.progress_path, "r", encoding="utf-8") as pf:
                    data = json.load(pf)
                if "quizzes" not in data or not isinstance(data["quizzes"], int):
                    data["quizzes"] = default["quizzes"]
                self.progress = data
            except (json.JSONDecodeError, IOError):
                self.progress = default.copy()
        else:
            self.progress = default.copy()
            self._save_progress()

    def _save_progress(self):
        with open(self.progress_path, "w", encoding="utf-8") as pf:
            json.dump(self.progress, pf, ensure_ascii=False, indent=2)

    def _load_answered(self):
        """
        Load or initialize answered-user database. Structure:
        {
          "date": "YYYY-MM-DD",
          "answered": [user_id, ...]
        }
        """
        today_str = self._today_str()
        default = {"date": today_str, "answered": []}

        if os.path.isfile(self.answer_db_path):
            try:
                with open(self.answer_db_path, "r", encoding="utf-8") as pf:
                    data = json.load(pf)
                if data.get("date") != today_str:
                    data = default.copy()
                    self._save_answered(data)
                self.answered_data = data
            except (json.JSONDecodeError, IOError):
                self.answered_data = default.copy()
                self._save_answered(self.answered_data)
        else:
            self.answered_data = default.copy()
            self._save_answered(self.answered_data)

    def _save_answered(self, data: dict = None):
        """
        Save answered-user database to JSON.
        If data is None, save self.answered_data.
        """
        if data is None:
            data = self.answered_data
        with open(self.answer_db_path, "w", encoding="utf-8") as pf:
            json.dump(data, pf, ensure_ascii=False, indent=2)

    def _load_leaderboard(self):
        """
        Load or initialize leaderboard database. Structure:
        {
          "date": "YYYY-MM-DD",
          "correct": [display_name, ...],
          "message_id": int,          # leaderboard embed message ID
          "quiz_message_id": int,     # quiz embed message ID
          "sent_ts": str              # ISO timestamp when quiz was sent
        }
        """
        today_str = self._today_str()
        default = {
            "date": today_str,
            "correct": [],
            "message_id": None,
            "quiz_message_id": None,
            "sent_ts": None
        }

        if os.path.isfile(self.leaderboard_db_path):
            try:
                with open(self.leaderboard_db_path, "r", encoding="utf-8") as pf:
                    data = json.load(pf)
                if data.get("date") != today_str:
                    data = default.copy()
                    self._save_leaderboard(data)
                self.leaderboard_data = data
            except (json.JSONDecodeError, IOError):
                self.leaderboard_data = default.copy()
                self._save_leaderboard(self.leaderboard_data)
        else:
            self.leaderboard_data = default.copy()
            self._save_leaderboard(self.leaderboard_data)

    def _save_leaderboard(self, data: dict = None):
        """
        Save leaderboard database to JSON.
        If data is None, save self.leaderboard_data.
        """
        if data is None:
            data = self.leaderboard_data
        with open(self.leaderboard_db_path, "w", encoding="utf-8") as pf:
            json.dump(data, pf, ensure_ascii=False, indent=2)

    def _today_str(self) -> str:
        """Return today's date string in YYYY-MM-DD based on LOCALE_TZ."""
        now = datetime.datetime.now(KorQuizOfTheDay.LOCALE_TZ)
        return now.date().isoformat()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.task_started:
            # Fetch persistent messages if they exist
            lb_channel = self.bot.get_channel(KorQuizOfTheDay.QUIZ_LEADERBOARD_CHANNEL_ID)
            if self.leaderboard_data.get("message_id") and lb_channel:
                try:
                    self.leaderboard_msg = await lb_channel.fetch_message(self.leaderboard_data["message_id"])
                except Exception:
                    self.leaderboard_msg = None

            qz_channel = self.bot.get_channel(KorQuizOfTheDay.QUIZ_CHANNEL_ID)
            if self.leaderboard_data.get("quiz_message_id") and qz_channel:
                try:
                    self.quiz_msg = await qz_channel.fetch_message(self.leaderboard_data["quiz_message_id"])
                except Exception:
                    self.quiz_msg = None

            # If today’s quiz is still active, re-register the persistent view
            if self.quiz_msg:
                idx = self.progress.get("quizzes", 0) - 1
                if idx < 0:
                    idx += len(self.quizzes)
                entry = self.quizzes[idx]
                options = entry["options"]
                correct_index = entry["answer_index"]

                view = self.QuizView(
                    options,
                    correct_index,
                    self.current_answered,
                    self.current_correct,
                    self.leaderboard_msg,
                    self.answered_data,
                    self.leaderboard_data
                )
                self.bot.add_view(view)

                # If we have a stored "sent_ts", schedule removal based on it
                sent_ts = self.leaderboard_data.get("sent_ts")
                if sent_ts:
                    asyncio.create_task(self._schedule_remove(sent_ts))

            # Start daily scheduler
            self.bot.loop.create_task(self._daily_scheduler())
            self.task_started = True

    async def _daily_scheduler(self):
        while True:
            now = datetime.datetime.now(KorQuizOfTheDay.LOCALE_TZ)
            # Send new quiz at 7:39 PM BST
            target_today = now.replace(hour=5, minute=0, second=0, microsecond=0)
            if now >= target_today:
                target = target_today + datetime.timedelta(days=1)
            else:
                target = target_today

            await asyncio.sleep((target - now).total_seconds())
            await self.send_quiz_of_the_day()
            self._save_progress()

            # No "sleep + edit" here; removal is handled by _schedule_remove.
            # Loop then waits until next day's 19:39.

    def _next_index(self) -> int:
        current = self.progress.get("quizzes", 0) % len(self.quizzes)
        self.progress["quizzes"] = (current + 1) % len(self.quizzes)
        return current

    async def send_quiz_of_the_day(self):
        # 1) Determine today's index
        idx = self._next_index()
        entry = self.quizzes[idx]

        quiz_channel = self.bot.get_channel(KorQuizOfTheDay.QUIZ_CHANNEL_ID)
        lb_channel = self.bot.get_channel(KorQuizOfTheDay.QUIZ_LEADERBOARD_CHANNEL_ID)
        if quiz_channel is None or lb_channel is None:
            return

        # 2) Reset JSON databases for a new day
        today_str = self._today_str()
        self.answered_data = {"date": today_str, "answered": []}
        self._save_answered(self.answered_data)

        self.leaderboard_data = {
            "date": today_str,
            "correct": [],
            "message_id": None,
            "quiz_message_id": None,
            "sent_ts": None
        }
        self._save_leaderboard(self.leaderboard_data)

        # 3) Refresh in-memory state
        self.current_answered.clear()
        self.current_correct.clear()
        self.leaderboard_msg = None
        self.quiz_msg = None

        # 4) Quiz details
        question = entry.get("question", "N/A")
        options = entry.get("options", [])
        answer_index = entry.get("answer_index", 0)
        level = entry.get("level", "Beginner")

        # 5) Prepare date footer
        date_obj = datetime.datetime.now(KorQuizOfTheDay.LOCALE_TZ)
        footer_text = date_obj.strftime("%Y-%m-%d (%A)")

        # 6) Send initial leaderboard embed to leaderboard channel
        lb_embed = discord.Embed(
            title="<a:bunny_dance:1379158339061157969> Korean Quiz Leaderboard",
            description="No correct answers yet. Be the first!",
            color=config.EMBED_COLOR
        )
        lb_embed.set_footer(text=footer_text)
        lb_msg = await lb_channel.send(embed=lb_embed)

        # 7) Persist leaderboard message ID
        self.leaderboard_data["message_id"] = lb_msg.id
        self._save_leaderboard(self.leaderboard_data)
        self.leaderboard_msg = lb_msg

        # 8) Create the persistent View
        view = self.QuizView(
            options,
            answer_index,
            self.current_answered,
            self.current_correct,
            self.leaderboard_msg,
            self.answered_data,
            self.leaderboard_data
        )
        self.bot.add_view(view)

        # 9) Send quiz embed with buttons to quiz channel, capture message
        quiz_embed = discord.Embed(
            title="📝 Korean Quiz of the Day",
            description=question,
            color=config.EMBED_COLOR
        )
        quiz_embed.add_field(name="Level", value=level, inline=True)
        quiz_embed.set_footer(text=footer_text)

        mention = "<@&1379159799572467894>"
        quiz_msg = await quiz_channel.send(content=mention, embed=quiz_embed, view=view)
        self.quiz_msg = quiz_msg

        # 10) Persist quiz_message_id and sent_ts into leaderboard_data
        self.leaderboard_data["quiz_message_id"] = quiz_msg.id
        self.leaderboard_data["sent_ts"] = datetime.datetime.now(KorQuizOfTheDay.LOCALE_TZ).isoformat()
        self._save_leaderboard(self.leaderboard_data)

        # 11) Schedule removal 23 hours after send
        asyncio.create_task(self._schedule_remove(self.leaderboard_data["sent_ts"]))

    async def _schedule_remove(self, sent_ts_iso: str):
        """
        Calculate time difference between now and (sent_ts + 23h).
        If already ≥ 23h, edit immediately; otherwise sleep remaining seconds, then remove buttons + add answer.
        """
        sent_dt = datetime.datetime.fromisoformat(sent_ts_iso)
        sent_dt = sent_dt.replace(tzinfo=KorQuizOfTheDay.LOCALE_TZ)

        target_dt = sent_dt + datetime.timedelta(hours=23)
        now = datetime.datetime.now(KorQuizOfTheDay.LOCALE_TZ)
        delay = (target_dt - now).total_seconds()

        if delay <= 0:
            await self._do_remove_buttons()
        else:
            await asyncio.sleep(delay)
            await self._do_remove_buttons()

    async def _do_remove_buttons(self):
        """Remove buttons and reveal answer on self.quiz_msg, if still present."""
        if not self.quiz_msg:
            return

        idx = self.progress.get("quizzes", 0) - 1
        if idx < 0:
            idx += len(self.quizzes)
        entry = self.quizzes[idx]
        correct_option = entry["options"][entry["answer_index"]]

        try:
            embed = self.quiz_msg.embeds[0]
            embed.add_field(name="Answer", value=correct_option, inline=False)
            await self.quiz_msg.edit(embed=embed, view=None)
        except Exception:
            pass

    # @commands.command(name="quiztest")
    # async def quiztest(self, ctx: commands.Context):
    #     """Immediately send today’s Korean Quiz (for testing)."""
    #     await self.send_quiz_of_the_day()

    class QuizView(View):
        def __init__(
            self,
            options: list,
            correct_index: int,
            answered_set: set,
            correct_list: list,
            leaderboard_message: discord.Message,
            answered_data: dict,
            leaderboard_data: dict
        ):
            # Removed `persistent=True` because View.__init__ doesn’t accept it
            super().__init__(timeout=None)
            self.correct_index = correct_index
            self.answered = answered_set
            self.correct_users = correct_list
            self.leaderboard_msg = leaderboard_message

            # References to JSON data for persistence
            self.answered_data = answered_data
            self.leaderboard_data = leaderboard_data

            # Add up to 4 buttons for options
            for i, opt in enumerate(options):
                button = Button(label=opt, style=discord.ButtonStyle.secondary, custom_id=f"kor_quiz_{i}")
                async def callback(interaction: discord.Interaction, idx=i):
                    await self._handle_answer(interaction, idx)
                button.callback = callback
                self.add_item(button)

        async def _handle_answer(self, interaction: discord.Interaction, selected_index: int):
            user_id = interaction.user.id
            display_name = interaction.user.display_name

            # 1) Check if user already answered today
            if user_id in self.answered:
                await interaction.response.send_message(
                    "You have already answered today's quiz. Please wait for tomorrow's quiz.",
                    ephemeral=True
                )
                return

            # 2) Mark the user as having answered, both in-memory and in JSON
            self.answered.add(user_id)
            self.answered_data["answered"].append(user_id)
            with open(os.path.join(os.path.dirname(__file__), "kor_quiz_answer_users.json"), "w", encoding="utf-8") as pf:
                json.dump(self.answered_data, pf, ensure_ascii=False, indent=2)

            # 3) Check correctness
            if selected_index == self.correct_index:
                # Add to correct_users and JSON leaderboard
                self.correct_users.append(display_name)
                self.leaderboard_data["correct"].append(display_name)
                with open(os.path.join(os.path.dirname(__file__), "kor_quiz_leaderboard.json"), "w", encoding="utf-8") as pf:
                    json.dump(self.leaderboard_data, pf, ensure_ascii=False, indent=2)

                rank = len(self.correct_users)
                # Update leaderboard embed (top 20), showing display name and username
                top_users = self.correct_users[:20]
                description_lines = []
                for i, dn in enumerate(top_users):
                    member = interaction.guild.get_member_named(dn)
                    username = member.name if member else "unknown"
                    description_lines.append(f"Rank {i+1}: {dn} ({username})")
                new_desc = "\n".join(description_lines)

                # Reconstruct footer date
                date_obj = datetime.datetime.now(KorQuizOfTheDay.LOCALE_TZ)
                footer_text = date_obj.strftime("%Y-%m-%d (%A)")

                lb_embed = discord.Embed(
                    title="<a:bunny_dance:1379158339061157969> Korean Quiz Leaderboard",
                    description=new_desc,
                    color=config.EMBED_COLOR
                )
                lb_embed.set_footer(text=footer_text)

                if self.leaderboard_msg:
                    await self.leaderboard_msg.edit(embed=lb_embed)
                else:
                    lb_channel = interaction.client.get_channel(KorQuizOfTheDay.QUIZ_LEADERBOARD_CHANNEL_ID)
                    try:
                        msg = await lb_channel.fetch_message(self.leaderboard_data["message_id"])
                        self.leaderboard_msg = msg
                        await msg.edit(embed=lb_embed)
                    except Exception:
                        pass

                await interaction.response.send_message(
                    f"✅ Correct! Your rank is {rank}.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Incorrect. Better luck next time!", ephemeral=True
                )

    @commands.command(name="quizprogress")
    async def quizprogress(self, ctx: commands.Context):
        """Show current quiz index and total count."""
        current = self.progress.get("quizzes", 0)
        total = len(self.quizzes)
        await ctx.send(f"Current quiz: {current} / {total}")

async def setup(bot: commands.Bot):
    await bot.add_cog(KorQuizOfTheDay(bot))
