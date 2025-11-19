import discord
from discord.ext import commands
import datetime

LOG_CHANNEL_ID = 1378069288321290330  # channel to send invite logs

class InviteLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # cache invites per guild: { guild_id: { invite_code: uses, ... }, ... }
        self.invites: dict[int, dict[str, int]] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        # initialize the cache when the bot starts
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
            except discord.Forbidden:
                continue
            self.invites[guild.id] = {inv.code: inv.uses for inv in invites}
        print(f"✅ InviteLogger cached invites for {len(self.invites)} guild(s)")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Invite Created",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="Creator", value=invite.inviter.mention, inline=True)
        embed.add_field(name="Code", value=invite.code, inline=True)
        embed.add_field(
            name="Channel",
            value=invite.channel.mention if invite.channel else "Unknown",
            inline=True
        )
        embed.add_field(
            name="Max Uses",
            value=str(invite.max_uses or "Unlimited"),
            inline=True
        )
        embed.add_field(
            name="Expires At",
            value=invite.expires_at.strftime("%Y-%m-%d %H:%M UTC") if invite.expires_at else "Never",
            inline=True
        )
        # thumbnail = creator's avatar
        embed.set_thumbnail(url=invite.inviter.display_avatar.url)
        await log_channel.send(embed=embed)

        # update cache
        self.invites.setdefault(invite.guild.id, {})[invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild_id = member.guild.id
        old_invites = self.invites.get(guild_id)
        if old_invites is None:
            # no cache for this guild
            return

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return

        try:
            current = await member.guild.invites()
        except discord.Forbidden:
            return

        # find which invite increased in uses
        used_invite = None
        new_uses_map = {}
        for inv in current:
            new_uses_map[inv.code] = inv.uses
            old_uses = old_invites.get(inv.code, 0)
            if inv.uses > old_uses:
                used_invite = inv

        # update cache
        self.invites[guild_id] = new_uses_map

        if used_invite:
            embed = discord.Embed(
                title="Member Joined via Invite",
                color=0xff0000,
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Username", value=member.name, inline=True)
            embed.add_field(name="Display Name", value=member.display_name, inline=True)
            embed.add_field(
                name="Inviter",
                value=used_invite.inviter.mention if used_invite.inviter else "Unknown",
                inline=True
            )
            embed.add_field(name="Invite Code", value=used_invite.code, inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(InviteLogger(bot))
