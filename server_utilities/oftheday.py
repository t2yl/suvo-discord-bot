# cog/dayoftheday.py
import discord
from discord.ext import commands
import json
import os
import asyncio
import datetime
import random
import re
from datetime import timezone, timedelta
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

class DayoftheDay(commands.Cog):
    WORD_CHANNEL_ID    = 1378636496117960895
    PHRASE_CHANNEL_ID  = 1378636534613413968

    # Replace these with your actual role IDs
    WORD_ROLE_ID       = 1378668209405825145  # @WordOfTheDay role
    PHRASE_ROLE_ID     = 1378668315576373328  # @PhraseOfTheDay role

    LOCALE_TZ  = timezone(timedelta(hours=1))   # UTC+1 for BST
    START_DATE = datetime.date(2025, 1, 1)

    FONT_PATH    = os.path.join(os.path.dirname(__file__), "NanumGothic-Bold.ttf")
    IMAGE_SIZE   = (550, 190)

    BG_COLORS = [
        "#FFCDD2",  # slightly darker pink
        "#C8E6C9",  # pale green
        "#BBDEFB",  # pale blue
        "#FFE0B2",  # soft orange
        "#D1C4E9",  # soft purple
        "#B2EBF2",  # aqua
        "#FFF9C4",  # soft yellow
        "#DCEDC8",  # pale lime
        "#CFD8DC",  # soft grey-blue
        "#F8BBD0",  # soft rose
    ]

    MAIN_FONT_SIZE = 80
    SUB_FONT_SIZE  = 30

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(base_path, "words.json"), encoding="utf-8") as f:
            self.words = json.load(f)
        with open(os.path.join(base_path, "phrases.json"), encoding="utf-8") as f:
            self.phrases = json.load(f)

        cog_folder = os.path.dirname(__file__)
        self.progress_path = os.path.join(cog_folder, "progress.json")
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
            now = datetime.datetime.now(DayoftheDay.LOCALE_TZ)
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

    def _extract_romanization(self, details_en: str) -> str:
        if not details_en:
            return ""
        match = re.search(r"\(([^)]+)\)", details_en)
        return match.group(1) if match else ""

    def _build_word_image(self, korean_word: str, romanization: str, meaning: str):
        bg_hex = random.choice(DayoftheDay.BG_COLORS)
        bg_color = tuple(int(bg_hex[i : i + 2], 16) for i in (1, 3, 5))

        brightness = (bg_color[0] * 299 + bg_color[1] * 587 + bg_color[2] * 114) / 1000
        font_color = (255, 255, 255) if brightness < 128 else (0, 0, 0)

        img = Image.new("RGB", DayoftheDay.IMAGE_SIZE, color=bg_color)
        draw = ImageDraw.Draw(img)

        # Dynamically adjust main font size to fit width
        max_width = DayoftheDay.IMAGE_SIZE[0] - 20
        font_size = DayoftheDay.MAIN_FONT_SIZE
        while font_size > 10:
            try:
                main_font = ImageFont.truetype(DayoftheDay.FONT_PATH, font_size)
            except Exception:
                main_font = ImageFont.load_default()
                break
            bbox_main = draw.textbbox((0, 0), korean_word, font=main_font)
            w_main = bbox_main[2] - bbox_main[0]
            if w_main <= max_width:
                break
            font_size -= 2

        try:
            sub_font = ImageFont.truetype(DayoftheDay.FONT_PATH, DayoftheDay.SUB_FONT_SIZE)
        except Exception:
            sub_font = ImageFont.load_default()

        bbox_main = draw.textbbox((0, 0), korean_word, font=main_font)
        w_main = bbox_main[2] - bbox_main[0]
        h_main = bbox_main[3] - bbox_main[1]

        rom_line = f"[{romanization}]" if romanization else ""
        mean_line = meaning if meaning else ""

        if rom_line:
            bbox_rom = draw.textbbox((0, 0), rom_line, font=sub_font)
            w_rom = bbox_rom[2] - bbox_rom[0]
            h_rom = bbox_rom[3] - bbox_rom[1]
        else:
            w_rom = h_rom = 0

        if mean_line:
            bbox_mean = draw.textbbox((0, 0), mean_line, font=sub_font)
            w_mean = bbox_mean[2] - bbox_mean[0]
            h_mean = bbox_mean[3] - bbox_mean[1]
        else:
            w_mean = h_mean = 0

        spacing = 8
        block_height = h_main
        if rom_line:
            block_height += spacing + h_rom
        if mean_line:
            block_height += spacing + h_mean

        y_start = (DayoftheDay.IMAGE_SIZE[1] - block_height) // 2

        x_main = (DayoftheDay.IMAGE_SIZE[0] - w_main) // 2
        draw.text((x_main, y_start), korean_word, font=main_font, fill=font_color)

        current_y = y_start + h_main

        if rom_line:
            current_y += spacing
            x_rom = (DayoftheDay.IMAGE_SIZE[0] - w_rom) // 2
            draw.text((x_rom, current_y), rom_line, font=sub_font, fill=font_color)
            current_y += h_rom

        if mean_line:
            current_y += spacing
            x_mean = (DayoftheDay.IMAGE_SIZE[0] - w_mean) // 2
            draw.text((x_mean, current_y), mean_line, font=sub_font, fill=font_color)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer, bg_hex

    async def send_word_of_the_day(self):
        idx = self._next_index("words", self.words)
        entry = self.words[idx]
        channel = self.bot.get_channel(DayoftheDay.WORD_CHANNEL_ID)
        if channel is None:
            return

        roman = entry.get("romanization", "") or self._extract_romanization(entry.get("details_en", ""))
        meaning = entry.get("english", "")

        now = datetime.datetime.now(DayoftheDay.LOCALE_TZ)
        if now.hour < 5:
            display_date = now.date() - datetime.timedelta(days=1)
        else:
            display_date = now.date()
        date_str = display_date.strftime("%Y-%m-%d (%A)")

        img_buffer, bg_hex = self._build_word_image(
            entry.get("korean", "N/A"),
            roman,
            meaning
        )

        embed_color = int(bg_hex.lstrip("#"), 16)

        embed = discord.Embed(
            title="📘 Word of the Day | 오늘의 한국어 단어",
            color=embed_color
        )
        embed.add_field(name="한국어", value=entry.get("korean", "N/A"), inline=True)
        embed.add_field(name="English", value=meaning, inline=False)
        if entry.get("details_en"):
            embed.add_field(name="Explanation (English)", value=entry["details_en"], inline=False)
        if entry.get("details_ko"):
            embed.add_field(name="설명 (한국어)", value=entry["details_ko"], inline=False)
        embed.set_footer(text=date_str)

        file = discord.File(fp=img_buffer, filename="word.png")
        embed.set_image(url="attachment://word.png")

        mention = f"<@&{DayoftheDay.WORD_ROLE_ID}>"
        await channel.send(content=mention, embed=embed, file=file)

    async def send_phrase_of_the_day(self):
        idx = self._next_index("phrases", self.phrases)
        entry = self.phrases[idx]
        channel = self.bot.get_channel(DayoftheDay.PHRASE_CHANNEL_ID)
        if channel is None:
            return

        roman = entry.get("romanization", "") or self._extract_romanization(entry.get("details_en", ""))
        meaning = entry.get("english", "")

        now = datetime.datetime.now(DayoftheDay.LOCALE_TZ)
        if now.hour < 5:
            display_date = now.date() - datetime.timedelta(days=1)
        else:
            display_date = now.date()
        date_str = display_date.strftime("%Y-%m-%d (%A)")

        img_buffer, bg_hex = self._build_word_image(
            entry.get("korean", "N/A"),
            roman,
            meaning
        )

        embed_color = int(bg_hex.lstrip("#"), 16)

        embed = discord.Embed(
            title="🗣️ Phrase of the Day | 오늘의 한국어 표현",
            color=embed_color
        )
        embed.add_field(name="한국어", value=entry.get("korean", "N/A"), inline=True)
        embed.add_field(name="English", value=meaning, inline=False)
        if entry.get("details_en"):
            embed.add_field(name="Explanation (English)", value=entry["details_en"], inline=False)
        if entry.get("details_ko"):
            embed.add_field(name="설명 (한국어)", value=entry["details_ko"], inline=False)
        embed.set_footer(text=date_str)

        file = discord.File(fp=img_buffer, filename="phrase.png")
        embed.set_image(url="attachment://phrase.png")

        mention = f"<@&{DayoftheDay.PHRASE_ROLE_ID}>"
        await channel.send(content=mention, embed=embed, file=file)

    @commands.command(name="wordtest")
    async def wordtest(self, ctx: commands.Context):
        """Immediately send today’s Word of the Day (for testing)."""
        await self.send_word_of_the_day()

    @commands.command(name="phrasetest")
    async def phrasetest(self, ctx: commands.Context):
        """Immediately send today’s Phrase of the Day (for testing)."""
        await self.send_phrase_of_the_day()

async def setup(bot: commands.Bot):
    await bot.add_cog(DayoftheDay(bot))
