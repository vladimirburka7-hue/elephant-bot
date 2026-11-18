from __future__ import annotations

import logging
import os

import discord
from discord.ext import commands

from bot.services.storage import init_storage
from bot.ui.containers import ApplicationsPanelView, GuidePanelView

log = logging.getLogger("community_bot")


class CommunityBot(commands.Bot):
    async def setup_hook(self) -> None:
        init_storage()

        # Загружаем модули
        await self.load_extension("bot.cogs.panels")
        await self.load_extension("bot.cogs.applications")
        await self.load_extension("bot.cogs.welcome")
        await self.load_extension("bot.cogs.market")
        await self.load_extension("bot.cogs.temp_voice")
        await self.load_extension("bot.cogs.moderation")
        await self.load_extension("bot.cogs.media")
        await self.load_extension("bot.cogs.setup_system")
        await self.load_extension("bot.cogs.license")
        await self.load_extension("bot.cogs.staff_panel")

        # Новые модули (Премиум фичи)
        await self.load_extension("bot.cogs.tickets")
        await self.load_extension("bot.cogs.economy")
        await self.load_extension("bot.cogs.reaction_roles")

        # Регистрируем постоянные кнопки
        self.add_view(ApplicationsPanelView())
        self.add_view(GuidePanelView())

        test_guild_id = os.getenv("TEST_GUILD_ID", "").strip()
        if test_guild_id:
            try:
                guild = discord.Object(id=int(test_guild_id))
            except ValueError as exc:
                raise RuntimeError("TEST_GUILD_ID должен быть числовым ID сервера.") from exc
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Синхронизировано %d команд для тестового сервера %s", len(synced), test_guild_id)
        else:
            synced = await self.tree.sync()
            log.info("Синхронизировано %d глобальных команд", len(synced))
            log.warning("Глобальные команды могут появиться не сразу; для теста укажи TEST_GUILD_ID в .env.")

    async def on_ready(self) -> None:
        log.info("Бот вошёл в Discord как %s", self.user)


def create_bot() -> CommunityBot:
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return CommunityBot(command_prefix="!", intents=intents)