import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import config

class AskApp(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        guild = discord.Object(id=config.GUILD_ID)  
        # add the command _only_ to that guild
        bot.tree.add_command(self.ask, guild=guild)

    @app_commands.command(
        name="ask",
        description="Ask Suvo a question and get a direct answer."
    )
    @app_commands.describe(question="Your question for Suvo")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        system_text = (
            "You are Suvo, an intelligent AI assistant created by Gaurav. "
            f"Answer the following question from {interaction.user.display_name}. "
            "Be strict, concise, and helpful. No unnecessary fluff. "
            "Limit your answer to 500 characters."
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": [
                {"role": "user", "parts": [{"text": question}]}
            ],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 150}
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            reply = "".join(p.get("text", "") for p in parts)
        except Exception as e:
            reply = f"Error: {e}"
        await interaction.followup.send(reply)

async def setup(bot: commands.Bot):
    await bot.add_cog(AskApp(bot))
