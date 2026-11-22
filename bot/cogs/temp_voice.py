from __future__ import annotations

import discord
from discord import app_commands, ui
from discord.ext import commands

from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import get_settings, save_settings

DEFAULT_VOICE_NAME = "၊၊||၊〡・Голосовой канал"
TEMP_VOICE_OWNERS: dict[int, int] = {}


def _is_voice_owner(interaction: discord.Interaction) -> bool:
    if not interaction.channel:
        return False
    return interaction.user.id == TEMP_VOICE_OWNERS.get(interaction.channel.id)


class VoiceRenameModal(ui.Modal, title="Переименовать комнату"):
    name_input = ui.TextInput(label="Новое название канала", max_length=90, required=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.VoiceChannel) or not _is_voice_owner(interaction):
            await interaction.response.send_message(f"{emoji_tag('question')} Только владелец комнаты может менять название.", ephemeral=True)
            return
        new_name = self.name_input.value.strip() or DEFAULT_VOICE_NAME
        await interaction.channel.edit(name=new_name)
        await interaction.response.send_message(f"{emoji_tag('yes')} Название изменено на **{discord.utils.escape_markdown(new_name)}**.", ephemeral=True)


class VoiceLimitModal(ui.Modal, title="Лимит участников"):
    limit_input = ui.TextInput(label="Количество мест (0 — без лимита, до 99)", max_length=2, required=True)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.VoiceChannel) or not _is_voice_owner(interaction):
            await interaction.response.send_message(f"{emoji_tag('question')} Только владелец комнаты может менять лимит.", ephemeral=True)
            return
        raw = self.limit_input.value.strip()
        if not raw.isdigit() or not (0 <= int(raw) <= 99):
            await interaction.response.send_message(f"{emoji_tag('question')} Введите число от **0** до **99**.", ephemeral=True)
            return
        limit = int(raw)
        await interaction.channel.edit(user_limit=limit)
        text = "снят (без ограничений)" if limit == 0 else f"установлен на **{limit}** чел."
        await interaction.response.send_message(f"{emoji_tag('yes')} Лимит участников {text}", ephemeral=True)


class VoiceKickSelect(ui.UserSelect):
    def __init__(self, voice_channel: discord.VoiceChannel, owner_id: int) -> None:
        super().__init__(placeholder="Выберите участника для кика...", min_values=1, max_values=1)
        self.voice_channel = voice_channel
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(f"{emoji_tag('question')} Доступно только владельцу комнаты.", ephemeral=True)
            return
        target = self.values[0]
        if not isinstance(target, discord.Member) or target.id == self.owner_id:
            await interaction.response.send_message(f"{emoji_tag('question')} Выберите другого участника.", ephemeral=True)
            return
        if not target.voice or target.voice.channel != self.voice_channel:
            await interaction.response.send_message(f"{emoji_tag('question')} Участник не в вашей комнате.", ephemeral=True)
            return
        await target.move_to(None, reason=f"Кик из приватного войса владельцем {interaction.user}")
        await interaction.response.edit_message(content=f"{emoji_tag('yes')} Участник {target.mention} исключён из комнаты.", view=None)


class VoiceTransferSelect(ui.UserSelect):
    def __init__(self, voice_channel: discord.VoiceChannel, panel_message: discord.Message, owner_id: int) -> None:
        super().__init__(placeholder="Выберите нового владельца...", min_values=1, max_values=1)
        self.voice_channel = voice_channel
        self.panel_message = panel_message
        self.owner_id = owner_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(f"{emoji_tag('question')} Доступно только владельцу комнаты.", ephemeral=True)
            return
        target = self.values[0]
        if not isinstance(target, discord.Member) or target.bot or not target.voice or target.voice.channel != self.voice_channel:
            await interaction.response.send_message(f"{emoji_tag('question')} Новый владелец должен находиться в этой комнате.", ephemeral=True)
            return
        TEMP_VOICE_OWNERS[self.voice_channel.id] = target.id
        try:
            await self.voice_channel.set_permissions(interaction.user, overwrite=None)
            await self.voice_channel.set_permissions(target, manage_channels=True, connect=True, speak=True)
            await self.panel_message.edit(view=VoicePanel(target.id))
        except discord.HTTPException:
            pass
        await interaction.response.edit_message(content=f"{emoji_tag('owner')} Права владельца переданы {target.mention}.", view=None)
class VoiceActionButton(ui.Button):
    def __init__(self, label: str, emoji_key: str, action: str) -> None:
        super().__init__(label=label, emoji=emoji_object(emoji_key), style=discord.ButtonStyle.secondary, custom_id=f"tempvoice:{action}")
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("Работает только в чате голосового канала.", ephemeral=True)
            return
        owner_id = TEMP_VOICE_OWNERS.get(interaction.channel.id)
        if owner_id is None or interaction.user.id != owner_id:
            await interaction.response.send_message(f"{emoji_tag('question')} Управлять этой комнатой может только её владелец.", ephemeral=True)
            return

        if self.action == "rename":
            await interaction.response.send_modal(VoiceRenameModal())
        elif self.action == "limit":
            await interaction.response.send_modal(VoiceLimitModal())
        elif self.action == "lock":
            assert interaction.guild is not None
            current_ow = interaction.channel.overwrites_for(interaction.guild.default_role)
            if current_ow.connect is False:
                current_ow.connect = None
                await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=current_ow)
                await interaction.response.send_message(f"{emoji_tag('yes')} Комната **открыта** для всех.", ephemeral=True)
            else:
                current_ow.connect = False
                await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=current_ow)
                await interaction.channel.set_permissions(interaction.user, connect=True, speak=True, manage_channels=True)
                await interaction.response.send_message(f"{emoji_tag('key')} Комната **закрыта**.", ephemeral=True)
        elif self.action == "kick":
            view = ui.View(timeout=60)
            view.add_item(VoiceKickSelect(interaction.channel, owner_id))
            await interaction.response.send_message(f"{emoji_tag('sword')} Кого выгнать из комнаты?", view=view, ephemeral=True)
        elif self.action == "transfer":
            if interaction.message is None:
                return
            view = ui.View(timeout=60)
            view.add_item(VoiceTransferSelect(interaction.channel, interaction.message, owner_id))
            await interaction.response.send_message(f"{emoji_tag('owner')} Кому передать комнату?", view=view, ephemeral=True)
        elif self.action == "delete":
            TEMP_VOICE_OWNERS.pop(interaction.channel.id, None)
            await interaction.response.send_message(f"{emoji_tag('flag')} Удаляю комнату...", ephemeral=True)
            try:
                await interaction.channel.delete(reason=f"Удалено владельцем {interaction.user}")
            except discord.HTTPException:
                pass


class VoicePanel(ui.LayoutView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('microphone')} Управление приватной комнатой"),
            ui.TextDisplay(f"> {emoji_tag('owner')} **Владелец:** <@{owner_id}>\n> {emoji_tag('gear')} Кнопки доступны **только владельцу**."),
            ui.Separator(spacing=discord.SeparatorSpacing.large),
            ui.ActionRow(
                VoiceActionButton("Название", "gear", "rename"),
                VoiceActionButton("Лимит", "member", "limit"),
                VoiceActionButton("Закрыть/Открыть", "key", "lock"),
            ),
            ui.ActionRow(
                VoiceActionButton("Выгнать", "sword", "kick"),
                VoiceActionButton("Передать", "owner", "transfer"),
                VoiceActionButton("Удалить", "flag", "delete"),
            ),
        ))


class TempVoice(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="setup_voice", description="Настроить временные войсы")
    @app_commands.default_permissions(administrator=True)
    async def setup_voice(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        category = discord.utils.get(interaction.guild.categories, name="——・Приватные") or await interaction.guild.create_category("——・Приватные")
        info = await interaction.guild.create_text_channel("┌︱⚪・управление", category=category)
        create = await interaction.guild.create_voice_channel("└︱📡・Создать", category=category)
        settings = get_settings(interaction.guild.id)
        settings["temp_voice_creator_id"] = create.id
        settings["voice_create_channel_id"] = create.id
        save_settings(interaction.guild.id, settings)
        view = ui.LayoutView()
        view.add_item(ui.Container(ui.TextDisplay(f"# {emoji_tag('microphone')} Временные комнаты\n> {emoji_tag('key')} Зайди в **└︱📡・Создать**, чтобы создать свою комнату.")))
        await info.send(view=view)
        await interaction.response.send_message(f"{emoji_tag('yes')} Временные комнаты настроены!", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return
        settings = get_settings(member.guild.id)
        creator_id = settings.get("voice_create_channel_id") or settings.get("temp_voice_creator_id")

        if after.channel and creator_id and after.channel.id == int(creator_id):
            category = after.channel.category
            overwrites = dict(category.overwrites) if category else {}
            overwrites[member] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, manage_channels=True)
            new_channel = await member.guild.create_voice_channel(name=DEFAULT_VOICE_NAME, category=category, overwrites=overwrites)
            TEMP_VOICE_OWNERS[new_channel.id] = member.id
            try:
                await member.move_to(new_channel)
            except discord.HTTPException:
                TEMP_VOICE_OWNERS.pop(new_channel.id, None)
                await new_channel.delete()
                return
            await new_channel.send(view=VoicePanel(member.id))

        if before.channel and before.channel != after.channel and before.channel.id in TEMP_VOICE_OWNERS and len(before.channel.members) == 0:
            TEMP_VOICE_OWNERS.pop(before.channel.id, None)
            try:
                await before.channel.delete(reason="Приватная комната опустела")
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TempVoice(bot))
