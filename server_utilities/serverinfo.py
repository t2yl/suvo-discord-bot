import discord
from discord.ext import commands
import datetime

class ServerInfo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="serverinfo")
    @commands.has_permissions(administrator=True)
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        if not guild:
            return

        # Owner
        owner = guild.owner or "Unknown"

        # Boosts & pricing (USD→GBP rate as of June 6, 2025: 1 USD = 0.7393 GBP)
        total_boosts = guild.premium_subscription_count
        boost_price_gbp = 4.99 * 0.7393
        total_boost_price_gbp = total_boosts * boost_price_gbp

        # Members
        total_members = guild.member_count
        total_bots = sum(1 for m in guild.members if m.bot)
        online_members = sum(
            1 for m in guild.members
            if m.status != discord.Status.offline and not m.bot
        )
        timestamp_now = int(datetime.datetime.utcnow().timestamp())

        # Roles & permissions
        num_roles = len(guild.roles)
        highest_role = guild.roles[-1].name if guild.roles else "None"
        admins_count = sum(
            1 for m in guild.members
            if m.guild_permissions.administrator
        )

        # Channels
        num_text_channels = len(guild.text_channels)
        num_voice_channels = len(guild.voice_channels)
        num_stage_channels = len(guild.stage_channels)
        num_categories = len(guild.categories)
        total_channels = len(guild.channels)

        # Emojis
        num_emojis = len(guild.emojis)

        # Verification & MFA
        verification_level = str(guild.verification_level).title()
        mfa_level = "Elevated" if getattr(guild, "mfa_level", 0) == 1 else "None"

        # Creation date
        created_at = f"<t:{int(guild.created_at.timestamp())}:F>"

        # Nitro & vanity
        nitro_tier = str(guild.premium_tier).replace("_", " ").title()
        vanity_code = guild.vanity_url_code or "None"

        # Features (e.g., ANIMATED_ICON, NEWS, etc.)
        features = ", ".join(guild.features) if guild.features else "None"

        embed = discord.Embed(
            title="Server Information",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_author(
            name=guild.name,
            icon_url=guild.icon.url if guild.icon else None
        )

        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=owner, inline=True)
        embed.add_field(name="Created On", value=created_at, inline=True)

        embed.add_field(name="Total Members", value=total_members, inline=True)
        embed.add_field(name="Total Bots", value=total_bots, inline=True)
        embed.add_field(
            name="Online Members",
            value=f"{online_members} (as of <t:{timestamp_now}:F>)",
            inline=False
        )

        embed.add_field(name="Number of Roles", value=num_roles, inline=True)
        embed.add_field(name="Highest Role", value=highest_role, inline=True)
        embed.add_field(name="Members with Admin Perms", value=admins_count, inline=True)

        embed.add_field(name="Total Channels", value=total_channels, inline=True)
        embed.add_field(name="Text Channels", value=num_text_channels, inline=True)
        embed.add_field(name="Voice Channels", value=num_voice_channels, inline=True)
        embed.add_field(name="Stage Channels", value=num_stage_channels, inline=True)
        embed.add_field(name="Categories", value=num_categories, inline=True)

        embed.add_field(name="Active Boosts", value=total_boosts, inline=True)
        embed.add_field(
            name="Total Boost Price (UK, GBP)",
            value=f"£{total_boost_price_gbp:.2f} (~£{boost_price_gbp:.2f}/boost)",
            inline=True
        )
        embed.add_field(name="Nitro Tier", value=nitro_tier, inline=True)
        embed.add_field(name="Vanity URL Code", value=vanity_code, inline=True)

        embed.add_field(name="Verification Level", value=verification_level, inline=True)
        embed.add_field(name="MFA Level", value=mfa_level, inline=True)
        embed.add_field(name="Emoji Count", value=num_emojis, inline=True)
        embed.add_field(name="Features", value=features, inline=True)

        await ctx.reply(embed=embed, mention_author=False)

    @serverinfo.error
    async def serverinfo_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("You need Administrator permissions to use this command.", mention_author=False)
        else:
            raise error

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerInfo(bot))
