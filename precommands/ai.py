import re
import aiohttp
import asyncio
import random
import discord
from discord.ext import commands
import config

class AskCog(commands.Cog):
    """Handles the '!ask' command by creating a private thread and managing AI-powered replies."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Map thread_id to conversation context
        self.conversations: dict[int, dict] = {}
        # Limit concurrent Gemini calls (tune as needed)
        self._semaphore = asyncio.Semaphore(5)
        # Create one shared HTTP session with a 30s timeout
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout=timeout)

    @commands.command(name="ask")
    async def ask(self, ctx: commands.Context):
        """
        Reply to the !ask command by creating a private thread and starting the AI conversation.
        """
        try:
            await ctx.message.add_reaction("✅")
        except:
            pass

        thread_name = f"ask-{ctx.author.display_name}"
        thread = await ctx.channel.create_thread(
            name=thread_name,
            message=ctx.message,
            type=discord.ChannelType.private_thread,
            invitable=True
        )
        await thread.add_user(ctx.author)

        # Initialize with empty history
        self.conversations[thread.id] = {
            "user_id": ctx.author.id,
            "history": []
        }

        await thread.send(f"{ctx.author.mention} Hello {ctx.author.display_name}, how can I help you?")
        asyncio.create_task(self._lock_thread_after(thread, 1800))

    async def _lock_thread_after(self, thread: discord.Thread, delay: int):
        await asyncio.sleep(delay)
        try:
            await thread.edit(locked=True)
            await thread.send("Thread locked after 30 minutes. Use `!ask` to start another.")
            self.conversations.pop(thread.id, None)
        except:
            pass

    async def _call_gemini(self, url: str, payload: dict) -> dict:
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            async with self._semaphore:
                try:
                    async with self._session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        if resp.status == 503:
                            # model overloaded: wait then retry
                            backoff = min(2 ** attempt, 10) + random.random()
                            await asyncio.sleep(backoff)
                            continue
                        # other HTTP error: bail immediately
                        text = await resp.text()
                        raise RuntimeError(f"Error {resp.status}: {text}")
                except asyncio.TimeoutError:
                    # timeout, retry until max_retries
                    if attempt == max_retries:
                        raise RuntimeError("Request timed out after multiple attempts.")
                    await asyncio.sleep(1 + random.random())
                    continue
        # after exhausting retries, indicate model is busy
        raise RuntimeError("MODEL_OVERLOADED")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and non-thread messages
        if message.author.bot or not isinstance(message.channel, discord.Thread):
            return

        ctx_data = self.conversations.get(message.channel.id)
        if not ctx_data or message.author.id != ctx_data["user_id"]:
            return

        # Append user message
        ctx_data["history"].append({"role": "user", "content": message.content})
        # Trim conversation history to last 20 entries to keep payload small
        if len(ctx_data["history"]) > 20:
            ctx_data["history"] = ctx_data["history"][-20:]

        # Updated persona prompt to request specificity and brevity
        system_text = (
            f"You are Suvo, AI assistant created by Gaurav. "
            f"Chatting with {message.author.display_name}. "
            "Answer with specific details: directly address the user’s question, include a concrete example when relevant, and avoid vague language. "
            "Keep your response under 500 characters."
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": [
                {"role": e["role"], "parts": [{"text": e["content"]}]}
                for e in ctx_data["history"]
            ],
            # Lower temperature and max tokens to keep answers focused and concise
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 100}
        }

        async with message.channel.typing():
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
            )
            try:
                data = await self._call_gemini(url, payload)
            except RuntimeError as e:
                if str(e) == "MODEL_OVERLOADED":
                    return await message.channel.send(
                        "The AI service is busy right now. Please try again in a moment."
                    )
                return await message.channel.send(f"Error: {e}")

        try:
            parts = data["candidates"][0]["content"]["parts"]
            reply = "".join(part.get("text", "") for part in parts).strip()
        except:
            reply = "Sorry, I couldn't process that."

        # Append assistant reply and trim again if needed
        ctx_data["history"].append({"role": "assistant", "content": reply})
        if len(ctx_data["history"]) > 20:
            ctx_data["history"] = ctx_data["history"][-20:]

        await message.channel.send(reply)

    @commands.Cog.listener()
    async def on_cog_unload(self):
        # Close the shared HTTP session when the cog is unloaded
        await self._session.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(AskCog(bot))
