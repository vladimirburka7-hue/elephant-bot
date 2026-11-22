import io
import os
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("community_bot")

# ================= НАСТРОЙКИ БАННЕРА =================
GUILD_ID = 123456789012345678          # <-- ВСТАВЬТЕ СЮДА ID ВАШЕГО СЕРВЕРА (число без кавычек)
TEXT_COLOR = (30, 30, 30)              # Почти чёрный цвет, в тон логотипу
COUNT_BOTS = True                      # True — считать всех, False — только людей (без ботов)

POS_X_RATIO = 0.485                    # Ровно по левому краю буквы "E" в слове Elephant
POS_Y_RATIO = 0.585                    # Прямо под словом Elephant на чистом белом фоне
FONT_SIZE_RATIO = 0.046                # Аккуратный размер, соразмерный логотипу
# =====================================================

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_PATH = os.path.join(ROOT_DIR, "banner_template.png")
FONT_PATH = os.path.join(ROOT_DIR, "font.ttf")


class ServerBannerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_count = None
        self.update_banner_task.start()

    def cog_unload(self):
        self.update_banner_task.cancel()

    def create_banner_image(self, count: int) -> bytes:
        with Image.open(TEMPLATE_PATH).convert("RGBA") as img:
            width, height = img.size
            draw = ImageDraw.Draw(img)

            font_size = max(18, int(height * FONT_SIZE_RATIO))
            font = ImageFont.truetype(FONT_PATH, font_size)

            try:
                font.set_variation_by_axes([700])
            except Exception:
                pass

            formatted_number = f"{count:,}".replace(",", " ")
            text = f"Участников: {formatted_number}"

            x = int(width * POS_X_RATIO)
            y = int(height * POS_Y_RATIO)

            draw.text(
                (x, y),
                text,
                font=font,
                fill=TEXT_COLOR,
                anchor="lm"
            )

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer.read()

    @tasks.loop(minutes=10)
    async def update_banner_task(self):
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            log.warning("[Баннер] Сервер с ID %s не найден. Проверьте GUILD_ID в banner_cog.py", GUILD_ID)
            return

        current_count = (
            guild.member_count
            if COUNT_BOTS
            else sum(1 for m in guild.members if not m.bot)
        )

        if current_count != self.last_count:
            try:
                banner_bytes = self.create_banner_image(current_count)
                await guild.edit(banner=banner_bytes, reason="Обновление счётчика участников")
                self.last_count = current_count
                log.info("[Баннер] Успешно обновлён: %d участников", current_count)
            except discord.Forbidden:
                log.error("[Баннер] Ошибка прав: дайте роли бота право 'Управлять сервером' (Manage Server).")
            except discord.HTTPException as e:
                log.error("[Баннер] Ошибка Discord API: %s", e)

    @update_banner_task.before_loop
    async def before_update_banner(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="testbanner", description="Предпросмотр баннера в чате")
    @app_commands.default_permissions(administrator=True)
    async def slash_test_banner(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=True)
        try:
            count = (
                interaction.guild.member_count
                if COUNT_BOTS
                else sum(1 for m in interaction.guild.members if not m.bot)
            )
            banner_bytes = self.create_banner_image(count)
            file = discord.File(io.BytesIO(banner_bytes), filename="preview.png")
            await interaction.followup.send("Предпросмотр баннера:", file=file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка:\n`{type(e).__name__}: {e}`", ephemeral=True)

    @app_commands.command(name="setbanner", description="Принудительно поставить баннер в шапку сервера прямо сейчас")
    @app_commands.default_permissions(administrator=True)
    async def slash_set_banner(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=True)
        try:
            count = (
                interaction.guild.member_count
                if COUNT_BOTS
                else sum(1 for m in interaction.guild.members if not m.bot)
            )
            banner_bytes = self.create_banner_image(count)
            await interaction.guild.edit(banner=banner_bytes, reason=f"Установка баннера ({interaction.user})")
            self.last_count = count
            await interaction.followup.send(f"✅ Баннер успешно установлен в шапку сервера! (Участников: **{count}**)", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ У бота нет права **«Управлять сервером» (Manage Server)**.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Ошибка Discord API (возможно, превышен лимит смены баннера): `{e}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка:\n`{type(e).__name__}: {e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerBannerCog(bot))