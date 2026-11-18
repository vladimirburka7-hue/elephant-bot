import discord
from discord import app_commands, ui
from discord.ext import commands
import random
from datetime import datetime, timedelta
from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import get_settings, save_settings, get_balance, add_balance, get_rep, add_rep


class EconomyView(ui.LayoutView):
    def __init__(self, balance: int, rep: int):
        super().__init__(timeout=180)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('star')} Ваш профиль"),
            ui.TextDisplay(f"> {emoji_tag('diamond')} **Баланс:** {balance} монет"),
            ui.TextDisplay(f"> {emoji_tag('heart5')} **Уважение:** {rep}"),
            ui.ActionRow(
                ui.Button(label="Казино (Ставка 10)", emoji=emoji_object("gamepad"),
                          style=discord.ButtonStyle.secondary, custom_id="eco:casino"),
                ui.Button(label="Купить роль (100)", emoji=emoji_object("key"), style=discord.ButtonStyle.secondary,
                          custom_id="eco:buyrole")
            )
        ))


class ProfileButton(ui.Button):
    def __init__(self, user_id): super().__init__(label="Профиль", emoji=emoji_object("member"),
                                                  style=discord.ButtonStyle.secondary,
                                                  custom_id=f"rep:profile:{user_id}")


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Посмотреть свой профиль")
    async def profile(self, interaction: discord.Interaction):
        bal = get_balance(interaction.guild.id, interaction.user.id)
        rep = get_rep(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(view=EconomyView(bal, rep), ephemeral=True)

    @app_commands.command(name="rep", description="Дать уважение другому участнику")
    @app_commands.describe(user="Кому вы хотите дать уважение?")
    async def rep(self, interaction: discord.Interaction, user: discord.Member):
        if user.id == interaction.user.id:
            await interaction.response.send_message("Нельзя дать уважение самому себе.", ephemeral=True)
            return
        add_rep(interaction.guild.id, user.id, 1)
        total = get_rep(interaction.guild.id, user.id)

        view = ui.LayoutView()
        view.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('heart5')} Уважение выдано!"),
            ui.TextDisplay(f"> {emoji_tag('member')} **{user.mention}** получил +1 уважение.\n> Всего: **{total}**")
        ))
        await interaction.response.send_message(view=view)

    @app_commands.command(name="daily", description="Получить ежедневную награду")
    async def daily(self, interaction: discord.Interaction):
        # Упрощенная логика (в идеале проверять дату)
        add_balance(interaction.guild.id, interaction.user.id, 50)
        await interaction.response.send_message(f"{emoji_tag('yes')} Вы получили **50 монет**! Заходите завтра.",
                                                ephemeral=True)


class ShopView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('diamond')} Магазин ролей"),
            ui.TextDisplay(f"> {emoji_tag('key')} Здесь можно купить кастомные роли за монеты."),
            ui.Separator(),
            ui.ActionRow(
                ui.Button(label="Купить VIP (500)", style=discord.ButtonStyle.secondary, custom_id="shop:vip",
                          emoji=emoji_object("diamond")),
                ui.Button(label="Купить Цвет (200)", style=discord.ButtonStyle.secondary, custom_id="shop:color",
                          emoji=emoji_object("heart5"))
            )
        ))


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_shop", description="Создать магазин ролей")
    @app_commands.default_permissions(administrator=True)
    async def setup_shop(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await channel.send(view=ShopView())
        await interaction.response.send_message("Магазин создан.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
    await bot.add_cog(Shop(bot))