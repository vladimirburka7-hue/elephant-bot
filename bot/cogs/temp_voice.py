import discord
from discord import app_commands, ui
from discord.ext import commands
from bot.emojis import emoji_object, emoji_tag
from bot.services.storage import get_settings, save_settings

TEMP_VOICE_OWNERS = {}


class VoicePanel(ui.LayoutView):
    def __init__(self, owner_id: int):
        super().__init__(timeout=None)
        self.add_item(ui.Container(
            ui.TextDisplay(f"# {emoji_tag('microphone')} Комната"),
            ui.TextDisplay(f"> {emoji_tag('gear')} Вы владелец этой комнаты."),
            ui.ActionRow(
                ui.Button(label="Лимит", emoji=emoji_object("member"), style=discord.ButtonStyle.secondary,
                          custom_id="temp:limit"),
                ui.Button(label="Закрыть/Открыть", emoji=emoji_object("sword"), style=discord.ButtonStyle.secondary,
                          custom_id="temp:lock"),
            )
        ))


class TempVoice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_voice", description="Настроить временные войсы")
    @app_commands.default_permissions(administrator=True)
    async def setup_voice(self, interaction: discord.Interaction):
        category = discord.utils.get(interaction.guild.categories, name="Временные войсы")
        if not category: category = await interaction.guild.create_category("Временные войсы")

        info = await interaction.guild.create_text_channel("⁌・Информация", category=category)
        create = await interaction.guild.create_voice_channel("⁌・Создать", category=category)

        settings = get_settings(interaction.guild.id)
        settings["temp_voice_creator_id"] = create.id
        save_settings(interaction.guild.id, settings)

        view = ui.LayoutView()
        view.add_item(ui.Container(ui.TextDisplay(
            f"# {emoji_tag('microphone')} Временные комнаты\nЗайди в канал **⁌・Создать**, чтобы получить свою комнату.")))
        await info.send(view=view)

        await interaction.response.send_message("Настроено!", ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        if member.bot: return
        settings = get_settings(member.guild.id)
        creator_id = settings.get("temp_voice_creator_id")

        if after.channel and creator_id and after.channel.id == int(creator_id):
            category = after.channel.category
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(view_channel=True),
                member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True)
            }
            new_channel = await member.guild.create_voice_channel(name=f"🔊 {member.display_name}", category=category,
                                                                  overwrites=overwrites)
            TEMP_VOICE_OWNERS[new_channel.id] = member.id
            await member.move_to(new_channel)

            text_ch = await member.guild.create_text_channel(name=f"упр-{member.name}", category=category)
            await text_ch.set_permissions(member, manage_channels=True)
            await text_ch.send(view=VoicePanel(member.id))

        if before.channel and before.channel != after.channel:
            if before.channel.name.startswith("🔊"):
                if len(before.channel.members) == 0:
                    await before.channel.delete()
                    text_name = before.channel.name.replace("🔊 ", "упр-")
                    text_ch = discord.utils.get(before.channel.category.text_channels, name=text_name)
                    if text_ch: await text_ch.delete()


async def setup(bot: commands.Bot):
    await bot.add_cog(TempVoice(bot))