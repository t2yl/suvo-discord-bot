import discord
from discord.ext import commands
import sqlite3
import uuid
import datetime
import asyncio

class RecordText(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Connect to (or create) the SQLite3 database
        self.db = sqlite3.connect('recordings.db')
        self.cursor = self.db.cursor()

        # Create tables if they don't exist
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                user_id INTEGER,
                channel_id INTEGER,
                start_time INTEGER
            )
            '''
        )
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_key TEXT,
                message_text TEXT
            )
            '''
        )
        self.db.commit()

        # Keep track of active recordings in memory
        self.active_recordings = {}

    @commands.command(name='rec')
    @commands.has_permissions(administrator=True)
    async def rec(self, ctx: commands.Context, user: discord.Member):
        """
        Start recording all messages sent by <user> in this channel for the next 60 minutes.
        """
        # Generate a unique key for this recording
        recording_key = uuid.uuid4().hex[:8]
        start_ts = int(datetime.datetime.utcnow().timestamp())

        # Insert a new recording entry
        self.cursor.execute(
            'INSERT INTO recordings (key, user_id, channel_id, start_time) VALUES (?, ?, ?, ?)',
            (recording_key, user.id, ctx.channel.id, start_ts)
        )
        self.db.commit()

        # Mark as active
        self.active_recordings[recording_key] = {
            'user_id': user.id,
            'channel_id': ctx.channel.id
        }

        await ctx.send(f"Recording started for {user.mention}. Key: `{recording_key}`. This will last 60 minutes.")

        # Schedule stopping
        asyncio.create_task(self._stop_recording_after(recording_key, ctx.channel))

    async def _stop_recording_after(self, key: str, channel: discord.abc.Messageable):
        # Wait 60 minutes
        await asyncio.sleep(60 * 60)
        # Remove from active
        self.active_recordings.pop(key, None)
        # Notify in channel
        await channel.send(
            f"Recording `{key}` finished storing the last 60 minutes. To record again, type `!rec <user>`."
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots
        if message.author.bot:
            return

        # Optionally ignore your own commands so you don't record them
        if message.content.startswith(tuple(self.bot.command_prefix if isinstance(self.bot.command_prefix, (list, tuple)) else [self.bot.command_prefix])):
            return

        # Check active recordings and store messages
        for key, info in list(self.active_recordings.items()):
            if info['user_id'] == message.author.id and info['channel_id'] == message.channel.id:
                self.cursor.execute(
                    'INSERT INTO messages (recording_key, message_text) VALUES (?, ?)',
                    (key, message.content)
                )
                self.db.commit()

        # **DO NOT** call process_commands here anymore!

    @commands.command(name='sendrec')
    @commands.has_permissions(administrator=True)
    async def sendrec(self, ctx: commands.Context, recording_key: str):
        """
        Send back all recorded messages under <recording_key>, splitting into multiple messages if needed.
        """
        # Fetch all messages for this key
        self.cursor.execute(
            'SELECT message_text FROM messages WHERE recording_key = ? ORDER BY id',
            (recording_key,)
        )
        rows = self.cursor.fetchall()
        if not rows:
            return await ctx.send(f"No recording found for key `{recording_key}`.")

        # Concatenate and chunk
        full = "\n".join(r[0] for r in rows)
        chunks = [full[i:i + 2000] for i in range(0, len(full), 2000)]
        for chunk in chunks:
            await ctx.send(chunk)

    @commands.command(name='viewrec')
    @commands.has_permissions(administrator=True)
    async def viewrec(self, ctx: commands.Context):
        """
        View all recordings (keys and users) in an embed.
        """
        self.cursor.execute('SELECT key, user_id FROM recordings')
        rows = self.cursor.fetchall()
        if not rows:
            return await ctx.send("No recordings found.")

        embed = discord.Embed(title="Recordings", color=discord.Color.blue())
        for key, user_id in rows:
            embed.add_field(name=key, value=f'<@{user_id}>', inline=False)

        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(RecordText(bot))
