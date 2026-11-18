import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import timedelta
from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import log_staff_action

async def notify_user(member: discord.Member, title: str, desc: str):
    try:
        view = ui.LayoutView()
        view.add_item(ui.Container(ui.TextDisplay(f"# {title}\n{desc}")))
        await member.send(view=view)
    except discord.Forbidden:
        pass

class ModCenterView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('gear')} Центр управления"),
            ui.TextDisplay(f"> {emoji_tag('sword')} Выберите действие ниже."),
            ui.ActionRow(
                ui.Button(label="Мут", emoji=emoji_object("microphone"), style=discord.ButtonStyle.secondary, custom_id="mod:btn:mute"),
                ui.Button(label="Снять мут", emoji=emoji_object("yes"), style=discord.ButtonStyle.secondary, custom_id="mod:btn:unmute"),
            )
        ))

class MuteModal(ui.Modal):
    def __init__(self, target: discord.Member):
        super().__init__(title=f"Мут: {target.name}"[:45], timeout=300)
        self.target = target
        self.minutes = ui.TextInput(label="На сколько минут", default="15", max_length=5)
        self.reason = ui.TextInput(label="Причина", required=False, max_length=200)
        self.add_item(ui.Label(text="Минуты", component=self.minutes))
        self.add_item(ui.Label(text="Причина", component=self.reason))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            mins = int(self.minutes.value)
            until = discord.utils.utcnow() + timedelta(minutes=mins)
            await self.target.timeout(until, reason=self.reason.value or "Мут от персонала")
            log_staff_action(interaction.guild.id, interaction.user.id, "Мут", f"{self.target.mention} на {mins} мин.")
            await interaction.response.send_message(f"{emoji_tag('yes')} {self.target.mention} в муте на **{mins} мин**.", ephemeral=True)
            await notify_user(self.target, f"{emoji_tag('sword')} Вы получили мут", f"На сервере **{interaction.guild.name}** на **{mins} минут**.\nПричина: {self.reason.value or 'не указана'}")
        except ValueError:
            await interaction.response.send_message("Введите число.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("У бота нет прав на мут.", ephemeral=True)

class SelectUserForMuteModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Кому выдать мут?")
        self.user_id = ui.TextInput(label="ID или @юзернейм")
        self.add_item(ui.Label(text="Пользователь", component=self.user_id))
    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_id = int(self.user_id.value.replace("<@", "").replace(">", ""))
            member = interaction.guild.get_member(target_id)
            if member: await interaction.response.send_modal(MuteModal(member))
            else: await interaction.response.send_message("Не найден.", ephemeral=True)
        except:
            await interaction.response.send_message("Ошибка в ID.", ephemeral=True)

class ModCenter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(ModCenterView())

    @app_commands.command(name="setup_mod", description="Создать центр управления модерацией")
    @app_commands.default_permissions(administrator=True)
    async def setup_mod(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=ModCenterView(), ephemeral=False)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component: return
        cid = interaction.data.get("custom_id", "")
        if cid == "mod:btn:mute":
            await interaction.response.send_modal(SelectUserForMuteModal())
        elif cid == "mod:btn:unmute":
            await interaction.response.send_message("Выберите участника для снятия мута в меню ниже (в разработке).", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModCenter(bot))