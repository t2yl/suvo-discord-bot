import discord
from discord.ext import commands
import re
import asyncio

BYPASS_ROLE_ID = 1381992457897775125

# English swear words categorized by severity
MILD_EN_SWEARS = [
    "damn", "hell", "crap", "screw you", "shut up", "idiot", "dumb", "moron", "jerk", "loser", "stupid"
]


MEDIUM_EN_SWEARS = [
    "shit", "bitch", "bastard", "asshole", "dick", "piss", "slut", "whore",
    "douche", "prick", "jackass", "twat", "skank", "cock", "motherfucker", "dipshit", "dickhead"
]


EXTREME_EN_SWEARS = [
    "fuck", "fucker", "cunt", "motherfucking", "motherfucker",
    # racial slurs
    "nigger", "nigga", "chink", "gook", "spic", "kike", "kyke", "wetback", "beaner", "raghead", 
    "tranny", "faggot", "dyke", "retard", "mongoloid", "cripple", "fag", "camel jockey", 
    "shemale", "sandnigger", "oreo", "porch monkey", "ape", "coon", "zipperhead"
]


# Korean swear words categorized by severity
MILD_KR_SWEARS = [
    "꺼져", "닥쳐", "엿먹어", "멍청이", "바보", "느려터진", "찌질이", "쫄보", "천치"
]


MEDIUM_KR_SWEARS = [
    "씨발", "ㅅㅂ", "좆", "존나", "ㅈㄴ", "미친", "ㅂㅅ", "ㅈ같", "개같", "좆같", 
    "씨팔", "썅", "개놈", "죽어라", "돌았냐", "미쳤냐"
]


EXTREME_KR_SWEARS = [
    "개새끼", "병신", "미친놈", "애미", "애미뒤진", "씹새끼", "애미없", "애비없",
    "씨바알", "좆밥", "좆까", "좃같", "쌍놈", "썅년", "개년", "좃나", "씹창", "좃물", "씨방새",
    # racial and identity-based slurs
    "짱깨", "깜둥이", "쭝꿔", "쪽발이", "화교", "조센징", "혼혈아", "돌대가리", "병자호란"
]

def compile_patterns(word_list: list[str]) -> list[re.Pattern]:
    """
    Build regexes that match each word even if someone inserts
    ANY non-alphanumeric (or underscore) characters between letters,
    but only when it’s not part of a larger alphanumeric word.
    """
    patterns = []
    for word in word_list:
        # Escape each character, then allow [\W_]* after it
        escaped = "".join([re.escape(char) + r"[\W_]*" for char in word])
        # Drop the final [\W_]* so we don’t allow trailing junk
        if escaped.endswith(r"[\W_]*"):
            escaped = escaped[: -len(r"[\W_]*")]

        # Add lookarounds: (?<!\w) … (?!\w)
        regex = r"(?<!\w)" + escaped + r"(?!\w)"
        patterns.append(re.compile(regex, re.IGNORECASE))
    return patterns


class SwearFilter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Compile regex patterns for English swear words
        self.swear_patterns: list[tuple[re.Pattern, str]] = []
        for level, words in [
            ("mild", MILD_EN_SWEARS),
            ("medium", MEDIUM_EN_SWEARS),
            ("extreme", EXTREME_EN_SWEARS),
        ]:
            for patt in compile_patterns(words):
                self.swear_patterns.append((patt, level))

        # Compile regex patterns for Korean swear words
        for level, words in [
            ("mild", MILD_KR_SWEARS),
            ("medium", MEDIUM_KR_SWEARS),
            ("extreme", EXTREME_KR_SWEARS),
        ]:
            for patt in compile_patterns(words):
                self.swear_patterns.append((patt, level))

        # Simple cooldown tracker (30s per user)
        self._last_warning: dict[int, float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots (including itself)
        if message.author.bot:
            return

        # Check bypass role
        if isinstance(message.author, discord.Member):
            if any(role.id == BYPASS_ROLE_ID for role in message.author.roles):
                return

        content = message.content
        for pattern, level in self.swear_patterns:
            if pattern.search(content):
                now = asyncio.get_event_loop().time()
                last = self._last_warning.get(message.author.id, 0)
                if now - last < 30:
                    return  # still in cooldown for this user
                self._last_warning[message.author.id] = now

                embed = discord.Embed(
                    title="⚠️ Warning",
                    description=(
                        f"{message.author.mention}, please refrain from using **{level}**-level profanity or slurs."
                    ),
                    color=discord.Color.red()
                )
                embed.set_footer(text="This warning will auto-delete in 10 seconds.")

                try:
                    warning_msg = await message.reply(embed=embed)
                except (discord.HTTPException, OSError):
                    return

                await asyncio.sleep(10)
                try:
                    await message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                try:
                    await warning_msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass

                return  # stop after first matched swear


# Add to bot
async def setup(bot: commands.Bot):
    await bot.add_cog(SwearFilter(bot))
