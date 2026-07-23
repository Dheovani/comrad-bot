"""ComradBot lifecycle and service composition."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.ai.conversation import AIService, SlidingWindowLimiter
from comradbot.ai.groq_provider import GroqProvider
from comradbot.ai.openai_provider import OpenAIProvider
from comradbot.ai.prompts import resolve_comradbot_persona
from comradbot.ai.provider import AIProvider, SpeechProvider
from comradbot.audio.ffmpeg import FFmpegRunner
from comradbot.audio.manager import GuildAudioManager
from comradbot.audio.resolver import YtDlpAudioResolver
from comradbot.config import Settings
from comradbot.database.repositories import AIRepository, PlaylistRepository, SoundRepository
from comradbot.database.session import Database
from comradbot.errors import ComradBotError, PermissionDeniedError
from comradbot.logging import log_context
from comradbot.services.music import PlaylistService
from comradbot.sounds.service import SoundService
from comradbot.sounds.storage import SoundStorage

logger = logging.getLogger(__name__)
EXTENSIONS = (
    "comradbot.commands.general",
    "comradbot.commands.music",
    "comradbot.commands.sounds",
    "comradbot.commands.ai",
)


class ComradBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings
        self.database = Database(settings.database_url)
        self.ffmpeg = FFmpegRunner()
        self.audio_resolver = YtDlpAudioResolver(settings.music_resolve_timeout_seconds)
        self.audio_manager = GuildAudioManager(
            max_queue_size=settings.max_queue_size,
            idle_timeout=settings.audio_idle_timeout_seconds,
            default_volume=settings.default_volume,
            source_refresher=self.audio_resolver,
        )
        self.playlist_service = PlaylistService(
            PlaylistRepository(self.database.sessions),
            self.audio_resolver,
            max_playlists_per_guild=settings.max_playlists_per_guild,
            max_tracks_per_playlist=settings.max_playlist_tracks,
        )
        sound_repository = SoundRepository(self.database.sessions)
        self.sound_service = SoundService(
            sound_repository,
            SoundStorage(settings.sounds_directory),
            self.ffmpeg,
            max_size_bytes=settings.max_sound_file_size_mb * 1024 * 1024,
            max_duration_seconds=settings.max_sound_duration_seconds,
        )
        ai_repository = AIRepository(self.database.sessions)
        provider, speech_provider = build_ai_providers(settings)
        self.ai_service = AIService(
            provider,
            speech_provider,
            ai_repository,
            SlidingWindowLimiter(
                user_limit=settings.ai_user_requests_per_minute,
                guild_limit=settings.ai_guild_requests_per_minute,
                cooldown_seconds=settings.ai_cooldown_seconds,
            ),
            max_context_messages=settings.max_ai_context_messages,
            max_prompt_characters=settings.ai_max_prompt_characters,
            max_response_characters=settings.max_ai_response_characters,
            temp_directory=settings.data_directory / "tmp",
        )
        self.tree.error(self.on_app_command_error)

    async def setup_hook(self) -> None:
        self.settings.prepare_directories()
        ffmpeg, ffprobe = self.ffmpeg.verify_tools()
        logger.info("Ferramentas de áudio disponíveis: ffmpeg=%s ffprobe=%s", ffmpeg, ffprobe)
        logger.info(
            "Provedor de IA configurado: %s",
            self.settings.configured_ai_provider or "disabled",
        )
        await self.database.create_schema()
        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.info("Cog carregado: %s", extension)
        if self.settings.discord_guild_id is not None:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Comandos sincronizados no servidor de desenvolvimento: %d", len(synced))
        if self.settings.discord_sync_global_commands:
            synced = await self.tree.sync()
            logger.info("Comandos globais sincronizados: %d", len(synced))
        elif self.settings.discord_guild_id is None:
            logger.warning(
                "Nenhuma sincronização solicitada; defina DISCORD_GUILD_ID ou "
                "DISCORD_SYNC_GLOBAL_COMMANDS=true"
            )

    async def on_ready(self) -> None:
        logger.info("ComradBot conectado como %s", self.user)

    async def close(self) -> None:
        await self.audio_manager.close()
        await self.ai_service.close()
        await self.database.close()
        await super().close()

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        with log_context(guild_id=interaction.guild_id, user_id=interaction.user.id):
            if isinstance(original, PermissionDeniedError):
                message = f"⛔ {original}"
                logger.warning("Operação negada: %s", original)
            elif isinstance(original, ComradBotError):
                message = f"⚠️ {original}"
                logger.info("Falha esperada: %s", type(original).__name__)
            elif isinstance(original, app_commands.CheckFailure):
                message = "⛔ Você não tem permissão para usar este comando."
                logger.warning("Check de comando negado")
            else:
                message = "💥 O ComradBot tropeçou numa engrenagem. Tente novamente em instantes."
                logger.exception("Erro inesperado em comando", exc_info=original)
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


def build_ai_providers(
    settings: Settings,
) -> tuple[AIProvider | None, SpeechProvider | None]:
    configured = settings.configured_ai_provider
    persona = resolve_comradbot_persona(settings.custom_comradbot_persona)
    if configured == "groq" and settings.groq_api_key is not None:
        return (
            GroqProvider(
                api_key=settings.groq_api_key.get_secret_value(),
                model=settings.groq_model,
                persona=persona,
                timeout_seconds=settings.ai_timeout_seconds,
            ),
            None,
        )
    if configured == "openai" and settings.openai_api_key is not None:
        provider = OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            persona=persona,
            tts_model=settings.openai_tts_model,
            tts_voice=settings.openai_tts_voice,
            timeout_seconds=settings.ai_timeout_seconds,
        )
        return provider, provider
    return None, None
