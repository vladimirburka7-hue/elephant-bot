from __future__ import annotations

import discord
from discord.ext import commands

from bot.services.storage import get_settings, record_join
from bot.ui.containers import WelcomeView


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        settings = get_settings(member.guild.id)
        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            return
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(channel_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        joins = record_join(member.guild.id, member.id)
        view = WelcomeView(
            member=member,
            join_number=joins,
            member_count=member.guild.member_count or 0,
            boost_count=member.guild.premium_subscription_count or 0,
        )
        await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
