import os
import json
from datetime import datetime
from itertools import combinations

import discord
from discord.ext import commands

import config  # make sure config.EMBED_COLOR exists

class VCLeaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.file_path = 'voices.json'
        # Data structure:
        # {
        #   "users": { user_id_str: total_seconds, ... },
        #   "duos":  { "id1:id2": total_seconds, ... },
        #   "trios": { "id1:id2:id3": total_seconds, ... }
        # }
        self.voice_data = {"users": {}, "duos": {}, "trios": {}}
        self.load_data()

        # Active session starts
        self.user_sessions = {}      # user_id -> datetime they joined
        self.channel_sessions = {}   # channel_id -> {"members": [user_ids], "last_update": datetime}

    def load_data(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                self.voice_data = json.load(f)
            # ensure keys exist
            for k in ("users", "duos", "trios"):
                self.voice_data.setdefault(k, {})
        else:
            self.save_data()

    def save_data(self):
        with open(self.file_path, 'w') as f:
            json.dump(self.voice_data, f, indent=4)

    @commands.Cog.listener()
    async def on_ready(self):
        # only run once
        if getattr(self, '_sessions_initialized', False):
            return
        self._sessions_initialized = True

        now = datetime.utcnow()
        # pick up any existing VC members across all guilds
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                members = [m for m in channel.members if not m.bot]
                if not members:
                    continue

                # seed channel session
                uids = [m.id for m in members]
                self.channel_sessions[channel.id] = {
                    "members": uids,
                    "last_update": now
                }

                # seed individual timers
                for m in members:
                    self.user_sessions.setdefault(m.id, now)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        now = datetime.utcnow()
        bchan = before.channel.id if before.channel else None
        achan = after.channel.id  if after.channel else None

        # -------- handle leaving or moving out of before.channel --------
        if bchan is not None and bchan != achan:
            # 1) credit individual time
            start = self.user_sessions.pop(member.id, None)
            if start:
                secs = int((now - start).total_seconds())
                uid = str(member.id)
                self.voice_data["users"][uid] = self.voice_data["users"].get(uid, 0) + secs

            # 2) credit duo/trio time for that channel, then remove them
            await self._process_group_change(
                channel_id=bchan,
                timestamp=now,
                leave=member.id
            )

        # -------- handle joining or moving into after.channel --------
        if achan is not None and achan != bchan:
            # 1) start individual timer
            self.user_sessions[member.id] = now

            # 2) credit duo/trio time for old group and add them to new
            await self._process_group_change(
                channel_id=achan,
                timestamp=now,
                join=member.id
            )

        # save on every change
        self.save_data()

    async def _process_group_change(self, channel_id: int, timestamp: datetime, join: int = None, leave: int = None):
        """
        On any join/leave in a voice channel:
        1) Credit all existing combinations (pairs, trios) for elapsed time.
        2) Mutate the member list, reset last_update.
        """
        sess = self.channel_sessions.get(channel_id)

        # if there was an existing group, credit them
        if sess and sess["members"]:
            delta = int((timestamp - sess["last_update"]).total_seconds())
            # duos
            for a, b in combinations(sess["members"], 2):
                key = ":".join(sorted((str(a), str(b))))
                self.voice_data["duos"][key] = self.voice_data["duos"].get(key, 0) + delta
            # trios
            for a, b, c in combinations(sess["members"], 3):
                key = ":".join(sorted((str(a), str(b), str(c))))
                self.voice_data["trios"][key] = self.voice_data["trios"].get(key, 0) + delta

        # now update the session record
        if not sess:
            # brand new session
            members = [join] if join else []
            self.channel_sessions[channel_id] = {
                "members": members,
                "last_update": timestamp
            }
        else:
            if join:
                sess["members"].append(join)
            if leave and leave in sess["members"]:
                sess["members"].remove(leave)
            sess["last_update"] = timestamp
            # drop empty sessions
            if not sess["members"]:
                self.channel_sessions.pop(channel_id, None)

    @commands.command(name='vclb')
    async def vclb(self, ctx, mode: str = None):
        """
        !vclb            → top 10 users
        !vclb duo        → top duo (single)
        !vclb trio       → top trio (single)
        """
        # per-user
        if mode is None:
            data = self.voice_data["users"]
            if not data:
                return await ctx.send("No voice data available yet.")
            top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
            lines = []
            for uid, secs in top:
                m = ctx.guild.get_member(int(uid))
                name = m.display_name if m else f"<@{uid}>"
                mins = secs // 60
                lines.append(f"**{name}** — {mins} min")
            embed = discord.Embed(
                title="📊 VC Leaderboard",
                description="\n".join(lines),
                color=config.EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        # duo or trio
        mode = mode.lower()
        if mode == 'duo':
            data, title = self.voice_data["duos"], "🏆 Top VC Duo"
        elif mode == 'trio':
            data, title = self.voice_data["trios"], "🏆 Top VC Trio"
        else:
            return await ctx.send("Invalid mode: use `!vclb`, `!vclb duo`, or `!vclb trio`.")

        if not data:
            return await ctx.send(f"No {mode} data available yet.")

        # pick the single highest
        key, secs = max(data.items(), key=lambda x: x[1])
        ids = key.split(':')
        names = []
        for sid in ids:
            m = ctx.guild.get_member(int(sid))
            names.append(m.display_name if m else f"<@{sid}>")
        mins = secs // 60
        desc = f"**{' & '.join(names)}** — {mins} min"
        embed = discord.Embed(title=title, description=desc, color=config.EMBED_COLOR)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(VCLeaderboard(bot))
