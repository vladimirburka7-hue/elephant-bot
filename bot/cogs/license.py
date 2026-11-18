import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime, timedelta
import sqlite3
from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import DB_PATH, get_settings, save_settings

OWNER_USERNAMES = ["thep1neyyy", "demoraale"]


class LicenseView(ui.LayoutView):
    def __init__(self, text: str, is_success: bool):
        super().__init__(timeout=None)
        emoji_key = "yes" if is_success else "sword"
        self.add_item(ui.Container(ui.TextDisplay(f"# {emoji_tag(emoji_key)}\n{text}")))


class License(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_owner(self, user: discord.User) -> bool:
        return user.name in OWNER_USERNAMES

    @app_commands.command(name="genkey", description="Сгенерировать ключ активации (Только для владельцев)")
    @app_commands.describe(days="На сколько дней выдать ключ")
    async def genkey(self, interaction: discord.Interaction, days: int = 30):
        if not self.is_owner(interaction.user):
            await interaction.response.send_message("У вас нет прав на создание ключей.", ephemeral=True)
            return

        import secrets
        key = f"EAGLE-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO licenses (key, expires_at, is_used) VALUES (?, ?, 0)", (key, expires_at))
            conn.commit()

        text = f"Ключ создан: `{key}`\nСрок действия: **{days} дней**."
        await interaction.response.send_message(view=LicenseView(text, True), ephemeral=True)

    @app_commands.command(name="activate", description="Активировать бота на сервере")
    @app_commands.describe(key="Ваш ключ")
    async def activate(self, interaction: discord.Interaction, key: str):
        if interaction.guild is None: return

        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT expires_at, is_used FROM licenses WHERE key = ?", (key,)).fetchone()

            if not row:
                await interaction.response.send_message(view=LicenseView("Ключ не найден.", False), ephemeral=True)
                return

            expires_at, is_used = row
            if is_used:
                await interaction.response.send_message(view=LicenseView("Этот ключ уже был использован.", False),
                                                        ephemeral=True)
                return

            expire_date = datetime.fromisoformat(expires_at)
            if expire_date < datetime.utcnow():
                await interaction.response.send_message(view=LicenseView("Срок действия ключа истек.", False),
                                                        ephemeral=True)
                return

            # Активируем
            settings = get_settings(interaction.guild.id)
            settings["license_key"] = key
            settings["is_active"] = True
            settings["license_expires"] = expires_at
            save_settings(interaction.guild.id, settings)

            conn.execute("UPDATE licenses SET is_used = 1, guild_id = ? WHERE key = ?",
                         (str(interaction.guild.id), key))
            conn.commit()

        text = f"Бот успешно активирован!\nДействует до: `{expire_date.strftime('%d.%m.%Y')}`."
        await interaction.response.send_message(view=LicenseView(text, True), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(License(bot))