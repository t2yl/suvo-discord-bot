# cog/EngoftheDay.py
import discord
from discord.ext import commands
import json
import os
import asyncio
import datetime
import random
from datetime import timezone, timedelta
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import textwrap

class EngoftheDay(commands.Cog):
    WORD_CHANNEL_ID    = 1378747766775484486
    PHRASE_CHANNEL_ID  = 1378747735750217810

    # Replace these with your actual role IDs
    WORD_ROLE_ID       = 1378764205355962502  # @WordOfTheDay role
    PHRASE_ROLE_ID     = 1378764133151015034  # @PhraseOfTheDay role

    LOCALE_TZ      = timezone(timedelta(hours=1))   # UTC+1 for BST
    START_DATE     = datetime.date(2025, 1, 1)

    FONT_PATH      = os.path.join(os.path.dirname(__file__), "NanumGothic-Bold.ttf")
    # Increased width and height to accommodate longer sentences and wrapped text
    IMAGE_SIZE     = (1000, 350)

    # Pale, light pastel colors for aesthetic
    BG_COLORS      = [
        "#FFEBEE", "#E8F5E9", "#E3F2FD", "#FFF3E0",
        "#F3E5F5", "#E0F7FA", "#FFFDE7", "#F1F8E9",
        "#ECEFF1", "#FCE4EC",
    ]

    MAIN_FONT_SIZE = 50
    SUB_FONT_SIZE  = 20
    LINE_SPACING   = 12  # pixels between lines

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(base_path, "eng_words.json"), encoding="utf-8") as f:
            self.words = json.load(f)
        with open(os.path.join(base_path, "eng_phrases.json"), encoding="utf-8") as f:
            self.phrases = json.load(f)

        cog_folder = os.path.dirname(__file__)
        self.progress_path = os.path.join(cog_folder, "eng_progress.json")
        self._load_progress()

        self.task_started = False

    def _load_progress(self):
        default = {"words": 0, "phrases": 0}
        if os.path.isfile(self.progress_path):
            try:
                with open(self.progress_path, "r", encoding="utf-8") as pf:
                    data = json.load(pf)
                for key in default:
                    if key not in data or not isinstance(data[key], int):
                        data[key] = default[key]
                self.progress = data
            except (json.JSONDecodeError, IOError):
                self.progress = default.copy()
        else:
            self.progress = default.copy()
            self._save_progress()

    def _save_progress(self):
        with open(self.progress_path, "w", encoding="utf-8") as pf:
            json.dump(self.progress, pf, ensure_ascii=False, indent=2)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.task_started:
            self.bot.loop.create_task(self._daily_scheduler())
            self.task_started = True

    async def _daily_scheduler(self):
        while True:
            now = datetime.datetime.now(EngoftheDay.LOCALE_TZ)
            target_today = now.replace(hour=5, minute=0, second=0, microsecond=0)
            if now >= target_today:
                target = target_today + datetime.timedelta(days=1)
            else:
                target = target_today

            await asyncio.sleep((target - now).total_seconds())
            await self.send_word_of_the_day()
            await self.send_phrase_of_the_day()
            self._save_progress()

    def _next_index(self, key: str, data_list: list) -> int:
        current = self.progress.get(key, 0) % len(data_list)
        self.progress[key] = (current + 1) % len(data_list)
        return current

    def _wrap_text_lines(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
        """
        Wrap input text into multiple lines so that none exceed max_width when drawn with the given font.
        Returns a list of lines.
        """
        lines = []
        # First split by existing newlines, then wrap each paragraph
        for paragraph in text.split("\n"):
            # initial wrap by an approximate character count
            wrapped = textwrap.wrap(paragraph, width=60)
            for line in wrapped:
                # If a wrapped line still exceeds max_width, split it further
                while draw.textbbox((0, 0), line, font=font)[2] > max_width:
                    # split roughly in half and find a space near midpoint
                    mid = len(line) // 2
                    split_index = line.rfind(" ", 0, mid)
                    if split_index == -1:
                        split_index = mid
                    first, second = line[:split_index], line[split_index:].lstrip()
                    lines.append(first)
                    line = second
                lines.append(line)
        return lines

    def _build_word_image(self, word_text: str, pronunciation: str, meaning: str):
        bg_hex = random.choice(EngoftheDay.BG_COLORS)
        bg_color = tuple(int(bg_hex[i : i + 2], 16) for i in (1, 3, 5))

        # Always use dark text on pale background
        font_color = (0, 0, 0)

        img = Image.new("RGB", EngoftheDay.IMAGE_SIZE, color=bg_color)
        draw = ImageDraw.Draw(img)

        # Load fonts
        try:
            main_font = ImageFont.truetype(EngoftheDay.FONT_PATH, EngoftheDay.MAIN_FONT_SIZE)
        except Exception:
            main_font = ImageFont.load_default()
        try:
            sub_font = ImageFont.truetype(EngoftheDay.FONT_PATH, EngoftheDay.SUB_FONT_SIZE)
        except Exception:
            sub_font = ImageFont.load_default()

        max_text_width = EngoftheDay.IMAGE_SIZE[0] - 40  # margin of 20px each side

        # 1) Measure the main word
        bbox_main = draw.textbbox((0, 0), word_text, font=main_font)
        w_main = bbox_main[2] - bbox_main[0]
        h_main = bbox_main[3] - bbox_main[1]

        # 2) Prepare pronunciation line if exists
        pron_line = f"[{pronunciation}]" if pronunciation else ""
        if pron_line:
            bbox_pron = draw.textbbox((0, 0), pron_line, font=sub_font)
            w_pron = bbox_pron[2] - bbox_pron[0]
            h_pron = bbox_pron[3] - bbox_pron[1]
        else:
            w_pron = h_pron = 0

        # 3) Wrap meaning into multiple lines
        meaning_lines = []
        meaning_heights = []
        if meaning:
            meaning_lines = self._wrap_text_lines(meaning, sub_font, max_text_width, draw)
            for line in meaning_lines:
                bbox_line = draw.textbbox((0, 0), line, font=sub_font)
                meaning_heights.append(bbox_line[3] - bbox_line[1])
        else:
            meaning_heights = []

        # 4) Calculate total block height
        total_height = h_main
        if pron_line:
            total_height += EngoftheDay.LINE_SPACING + h_pron
        for height in meaning_heights:
            total_height += EngoftheDay.LINE_SPACING + height

        # 5) Starting y to vertically center the block
        y_start = (EngoftheDay.IMAGE_SIZE[1] - total_height) // 2

        # 6) Draw each element centered horizontally:
        current_y = y_start

        # Main word
        x_main = (EngoftheDay.IMAGE_SIZE[0] - w_main) // 2
        draw.text((x_main, current_y), word_text, font=main_font, fill=font_color)
        current_y += h_main + EngoftheDay.LINE_SPACING

        # Pronunciation
        if pron_line:
            x_pron = (EngoftheDay.IMAGE_SIZE[0] - w_pron) // 2
            draw.text((x_pron, current_y), pron_line, font=sub_font, fill=font_color)
            current_y += h_pron + EngoftheDay.LINE_SPACING

        # Meaning (wrapped lines)
        for idx, line in enumerate(meaning_lines):
            h_line = meaning_heights[idx]
            bbox_line = draw.textbbox((0, 0), line, font=sub_font)
            w_line = bbox_line[2] - bbox_line[0]
            x_line = (EngoftheDay.IMAGE_SIZE[0] - w_line) // 2
            draw.text((x_line, current_y), line, font=sub_font, fill=font_color)
            current_y += h_line + EngoftheDay.LINE_SPACING

        # 7) Save to buffer
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer, bg_hex

    def _build_phrase_image(self, phrase_text: str, pron_kor: str, meaning_eng: str, meaning_kor: str):
        bg_hex = random.choice(EngoftheDay.BG_COLORS)
        bg_color = tuple(int(bg_hex[i : i + 2], 16) for i in (1, 3, 5))

        font_color = (0, 0, 0)

        img = Image.new("RGB", EngoftheDay.IMAGE_SIZE, color=bg_color)
        draw = ImageDraw.Draw(img)

        # Load fonts
        try:
            main_font = ImageFont.truetype(EngoftheDay.FONT_PATH, EngoftheDay.MAIN_FONT_SIZE)
        except Exception:
            main_font = ImageFont.load_default()
        try:
            sub_font = ImageFont.truetype(EngoftheDay.FONT_PATH, EngoftheDay.SUB_FONT_SIZE)
        except Exception:
            sub_font = ImageFont.load_default()

        max_text_width = EngoftheDay.IMAGE_SIZE[0] - 40  # margin

        # 1) Measure the phrase
        bbox_main = draw.textbbox((0, 0), phrase_text, font=main_font)
        w_main = bbox_main[2] - bbox_main[0]
        h_main = bbox_main[3] - bbox_main[1]

        # 2) Prepare Korean pronunciation
        pron_line = f"[{pron_kor}]" if pron_kor else ""
        if pron_line:
            bbox_pron = draw.textbbox((0, 0), pron_line, font=sub_font)
            w_pron = bbox_pron[2] - bbox_pron[0]
            h_pron = bbox_pron[3] - bbox_pron[1]
        else:
            w_pron = h_pron = 0

        # 3) Wrap English meaning
        eng_lines = []
        eng_heights = []
        if meaning_eng:
            eng_lines = self._wrap_text_lines(meaning_eng, sub_font, max_text_width, draw)
            for line in eng_lines:
                bbox_line = draw.textbbox((0, 0), line, font=sub_font)
                eng_heights.append(bbox_line[3] - bbox_line[1])
        else:
            eng_heights = []

        # 4) Wrap Korean meaning
        kor_lines = []
        kor_heights = []
        if meaning_kor:
            kor_lines = self._wrap_text_lines(meaning_kor, sub_font, max_text_width, draw)
            for line in kor_lines:
                bbox_line = draw.textbbox((0, 0), line, font=sub_font)
                kor_heights.append(bbox_line[3] - bbox_line[1])
        else:
            kor_heights = []

        # 5) Calculate total block height
        total_height = h_main
        if pron_line:
            total_height += EngoftheDay.LINE_SPACING + h_pron
        for h in eng_heights:
            total_height += EngoftheDay.LINE_SPACING + h
        for h in kor_heights:
            total_height += EngoftheDay.LINE_SPACING + h

        # 6) Starting y to vertically center the block
        y_start = (EngoftheDay.IMAGE_SIZE[1] - total_height) // 2
        current_y = y_start

        # Main phrase
        x_main = (EngoftheDay.IMAGE_SIZE[0] - w_main) // 2
        draw.text((x_main, current_y), phrase_text, font=main_font, fill=font_color)
        current_y += h_main + EngoftheDay.LINE_SPACING

        # Korean pronunciation
        if pron_line:
            x_pron = (EngoftheDay.IMAGE_SIZE[0] - w_pron) // 2
            draw.text((x_pron, current_y), pron_line, font=sub_font, fill=font_color)
            current_y += h_pron + EngoftheDay.LINE_SPACING

        # English meaning
        for idx, line in enumerate(eng_lines):
            h_line = eng_heights[idx]
            bbox_line = draw.textbbox((0, 0), line, font=sub_font)
            w_line = bbox_line[2] - bbox_line[0]
            x_line = (EngoftheDay.IMAGE_SIZE[0] - w_line) // 2
            draw.text((x_line, current_y), line, font=sub_font, fill=font_color)
            current_y += h_line + EngoftheDay.LINE_SPACING

        # Korean meaning
        for idx, line in enumerate(kor_lines):
            h_line = kor_heights[idx]
            bbox_line = draw.textbbox((0, 0), line, font=sub_font)
            w_line = bbox_line[2] - bbox_line[0]
            x_line = (EngoftheDay.IMAGE_SIZE[0] - w_line) // 2
            draw.text((x_line, current_y), line, font=sub_font, fill=font_color)
            current_y += h_line + EngoftheDay.LINE_SPACING

        # 7) Save to buffer
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer, bg_hex

    async def send_word_of_the_day(self):
        idx = self._next_index("words", self.words)
        entry = self.words[idx]
        channel = self.bot.get_channel(EngoftheDay.WORD_CHANNEL_ID)
        if channel is None:
            return

        word_text = entry.get("word", "N/A")
        pronunciation = entry.get("pronunciation", "")
        meaning = entry.get("meaning", "")

        now = datetime.datetime.now(EngoftheDay.LOCALE_TZ)
        if now.hour < 5:
            display_date = now.date() - datetime.timedelta(days=1)
        else:
            display_date = now.date()
        date_str = display_date.strftime("%Y-%m-%d (%A)")

        img_buffer, bg_hex = self._build_word_image(word_text, pronunciation, meaning)
        embed_color = int(bg_hex.lstrip("#"), 16)

        embed = discord.Embed(
            title="📘 Word of the Day",
            color=embed_color
        )
        embed.add_field(name="Word", value=word_text, inline=True)
        if pronunciation:
            embed.add_field(name="Pronunciation", value=f"[{pronunciation}]", inline=False)
        embed.add_field(name="Meaning", value=meaning, inline=False)
        embed.set_footer(text=date_str)

        file = discord.File(fp=img_buffer, filename="word.png")
        embed.set_image(url="attachment://word.png")

        mention = f"<@&{EngoftheDay.WORD_ROLE_ID}>"
        await channel.send(content=mention, embed=embed, file=file)

    async def send_phrase_of_the_day(self):
        idx = self._next_index("phrases", self.phrases)
        entry = self.phrases[idx]
        channel = self.bot.get_channel(EngoftheDay.PHRASE_CHANNEL_ID)
        if channel is None:
            return

        phrase_text  = entry.get("phrase", "N/A")
        pron_kor     = entry.get("korean_pronunciation", "")
        meaning_eng  = entry.get("meaning", "")
        meaning_kor  = entry.get("korean_meaning", "")

        now = datetime.datetime.now(EngoftheDay.LOCALE_TZ)
        if now.hour < 5:
            display_date = now.date() - datetime.timedelta(days=1)
        else:
            display_date = now.date()
        date_str = display_date.strftime("%Y-%m-%d (%A)")

        img_buffer, bg_hex = self._build_phrase_image(
            phrase_text,
            pron_kor,
            meaning_eng,
            meaning_kor
        )
        embed_color = int(bg_hex.lstrip("#"), 16)

        embed = discord.Embed(
            title="🗣️ Phrase of the Day",
            color=embed_color
        )
        embed.add_field(name="Phrase", value=phrase_text, inline=True)
        embed.set_footer(text=date_str)

        file = discord.File(fp=img_buffer, filename="phrase.png")
        embed.set_image(url="attachment://phrase.png")

        mention = f"<@&{EngoftheDay.PHRASE_ROLE_ID}>"
        await channel.send(content=mention, embed=embed, file=file)

    @commands.command(name="ewordtest")
    async def wordtest(self, ctx: commands.Context):
        """Immediately send today’s Word of the Day (for testing)."""
        await self.send_word_of_the_day()

    @commands.command(name="ephrasetest")
    async def phrasetest(self, ctx: commands.Context):
        """Immediately send today’s Phrase of the Day (for testing)."""
        await self.send_phrase_of_the_day()

async def setup(bot: commands.Bot):
    await bot.add_cog(EngoftheDay(bot))
