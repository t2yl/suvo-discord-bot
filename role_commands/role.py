import discord
from discord.ext import commands
import asyncio
import config  # for EMBED_COLOR, optional

async def safe_edit(coro, *, retries=3):
    """
    Call a coroutine that makes an HTTP request. If it raises HTTPException with status 429,
    back off for the suggested retry_after, then retry up to `retries` times.
    """
    for attempt in range(retries):
        try:
            return await coro
        except discord.HTTPException as e:
            if getattr(e, 'status', None) == 429 and hasattr(e, 'retry_after'):
                wait = e.retry_after
            else:
                raise
        # wait before retrying
        await asyncio.sleep(wait)
    # final try
    return await coro

class RoleManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _get_role(self, guild: discord.Guild, identifier: str):
        if identifier.isdigit():
            role = guild.get_role(int(identifier))
            if role:
                return role
        return discord.utils.find(lambda r: r.name.lower() == identifier.lower(), guild.roles)

    async def _modify_role(self, ctx, members, role, add: bool):
        action = "Added" if add else "Removed"
        failures = []

        for member in members:
            try:
                # wrap the API call to catch 429s
                await safe_edit(member.add_roles(role, reason=f"{action} by {ctx.author}")) if add \
                    else await safe_edit(member.remove_roles(role, reason=f"{action} by {ctx.author}"))
                # small pause between each request to stay under the limit
                await asyncio.sleep(1.0)
            except Exception:
                failures.append(member.display_name)

        mention_list = "everyone" if members == ctx.guild.members else ", ".join(m.mention for m in members)
        desc = f"✅ {action} `{role.name}` {'to' if add else 'from'} {mention_list}."
        if failures:
            desc += f"\n⚠️ Failed for: {', '.join(failures)}"
        await ctx.send(embed=discord.Embed(description=desc, color=config.EMBED_COLOR))

    @commands.command(name="roleadd")
    @commands.has_guild_permissions(manage_roles=True)
    async def role_add(self, ctx, target: str, *, role_id: str):
        role = await self._get_role(ctx.guild, role_id)
        if not role:
            return await ctx.send(embed=discord.Embed(
                title="Role Not Found",
                description=f"No role matches `{role_id}`.",
                color=config.EMBED_COLOR
            ))

        if target.lower() == "all":
            members = [m for m in ctx.guild.members if not m.bot]
        else:
            try:
                members = [await commands.MemberConverter().convert(ctx, target)]
            except commands.BadArgument:
                return await ctx.send(embed=discord.Embed(
                    title="Member Not Found",
                    description=f"No member matches `{target}`.",
                    color=config.EMBED_COLOR
                ))

        await self._modify_role(ctx, members, role, add=True)

    @commands.command(name="roleremove")
    @commands.has_guild_permissions(manage_roles=True)
    async def role_remove(self, ctx, target: str, *, role_id: str):
        role = await self._get_role(ctx.guild, role_id)
        if not role:
            return await ctx.send(embed=discord.Embed(
                title="Role Not Found",
                description=f"No role matches `{role_id}`.",
                color=config.EMBED_COLOR
            ))

        if target.lower() == "all":
            members = [m for m in ctx.guild.members if role in m.roles and not m.bot]
        else:
            try:
                members = [await commands.MemberConverter().convert(ctx, target)]
            except commands.BadArgument:
                return await ctx.send(embed=discord.Embed(
                    title="Member Not Found",
                    description=f"No member matches `{target}`.",
                    color=config.EMBED_COLOR
                ))

        await self._modify_role(ctx, members, role, add=False)

    @role_add.error
    @role_remove.error
    async def role_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                title="Missing Permissions",
                description="You need **Manage Roles** to use this.",
                color=config.EMBED_COLOR
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Error",
                description=str(error),
                color=config.EMBED_COLOR
            ))

async def setup(bot):
    await bot.add_cog(RoleManagement(bot))
