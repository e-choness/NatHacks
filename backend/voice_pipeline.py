import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from gemini_assistant import GeminiAssistant
from speech_clients import TTS, STT

try:  # pragma: no cover - optional dependency during tests
    from vertex_speech import VertexSpeechToText
except ImportError:  # pragma: no cover - optional dependency during tests
    VertexSpeechToText = None  # type: ignore

# voice_assistant.py

# TODO: unit tests, hardware integration tests
# TODO: double check costs for API calls (make sure rate limiting is ok?)

LOGGER = logging.getLogger("voice_assistant")


@dataclass
class ConversationResult:
    transcript: Optional[str]
    response_text: Optional[str]
    audio_bytes: Optional[bytes]
    raw_tts: Optional[Any]


class VoiceAssistant:
    """
    overarching voice assistant pipeline
    audio -> text -> Gemini -> audio
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        max_retries: int = 3,
        *,
        use_vertex_stt: bool = False,
        stt_kwargs: Optional[Dict[str, Any]] = None,
        stt_client: Optional[Any] = None,
        tts_client: Optional[Any] = None,
        llm_client: Optional[Any] = None,
    ) -> None:
        self.max_retries = max_retries
        stt_kwargs = dict(stt_kwargs or {})
        stt_kwargs.setdefault("max_retries", max_retries)

        speech_params = {
            key: stt_kwargs[key]
            for key in ("language_code", "timeout_s", "max_retries")
            if key in stt_kwargs
        }
        model_name = stt_kwargs.get("model_name", "gemini-1.5-flash")
        vertex_params = {
            key: stt_kwargs[key]
            for key in ("language_code", "instruction", "max_retries", "cache_size")
            if key in stt_kwargs
        }

        if stt_client is not None:
            self.listener = stt_client
        elif use_vertex_stt:
            if VertexSpeechToText is None:
                LOGGER.warning(
                    "VertexSpeechToText unavailable; falling back to Google Cloud Speech"
                )
                self.listener = STT(**speech_params)
            else:
                self.listener = VertexSpeechToText(
                    project_id=project_id,
                    location=location,
                    model_name=model_name,
                    **vertex_params,
                )
        else:
            self.listener = STT(**speech_params)

        self.middleman = llm_client or GeminiAssistant(project_id, location)
        self.speaker = tts_client or TTS()

        components = (self.listener, self.middleman, self.speaker)
        self.enabled = all(getattr(component, "enabled", True) for component in components)
        if not self.enabled:
            LOGGER.warning("VoiceAssistant created but some component(s) not enabled")
        self._last_audio_params: Optional[Tuple[str, bool]] = None
        self._last_result: Optional[ConversationResult] = None

    def converse_with_details(
        self,
        audio_file: str,
        *,
        play_audio: bool = True,
    ) -> Optional[ConversationResult]:
        """Run the full pipeline and return structured output.

        Returns ``None`` when transcription or generation fails.
        """
        self._last_audio_params = (audio_file, play_audio)
        self._last_result = None
        if not self.enabled:
            LOGGER.warning("VoiceAssistant disabled")
            return None
        
        # TRANSCRIPTION
        user_text = None
        for attempt in range(self.max_retries):
            try:
                user_text = self.listener.transcribe(audio_file)
                if user_text:
                    break
            except Exception as exc:  # pragma: no cover - defensive log
                LOGGER.warning("STT failed attempt %d: %s", attempt + 1, exc)
        if not user_text:
            LOGGER.info(f"no speech detected in file named {audio_file}")
            return None

        # GENERATE RESPONSE
        ai_response = None
        for attempt in range(self.max_retries):
            try:
                ai_response = self.middleman.generate_text(user_text)
                if ai_response:
                    break
            except Exception as exc:  # pragma: no cover - defensive log
                LOGGER.warning("Gemini failed attempt %d: %s", attempt + 1, exc)
        if not ai_response:
            LOGGER.warning("Gemini didn't generate a response")
            return None
        
        # SPEAK RESPONSE
        tts_response = None
        for attempt in range(self.max_retries):
            try:
                tts_response = self.speaker.synthesize(ai_response)
                if tts_response:
                    break
            except Exception as exc:  # pragma: no cover - defensive log
                LOGGER.warning("TTS failed attempt %d: %s", attempt + 1, exc)
        audio_bytes: Optional[bytes] = None
        if tts_response:
            audio_bytes = getattr(tts_response, "audio_content", None)
            if audio_bytes is None:
                if isinstance(tts_response, (bytes, bytearray)):
                    audio_bytes = bytes(tts_response)
                elif isinstance(tts_response, dict) and "audio_content" in tts_response:
                    maybe_audio = tts_response.get("audio_content")
                    if isinstance(maybe_audio, (bytes, bytearray)):
                        audio_bytes = bytes(maybe_audio)
            if play_audio and hasattr(self.speaker, "playAudioOutputLive"):
                try:
                    self.speaker.playAudioOutputLive(tts_response)
                except Exception as exc:  # pragma: no cover - defensive log
                    LOGGER.warning("Failed to play TTS audio: %s", exc)
        else:
            LOGGER.warning("TTS failed to generate audio")

        result = ConversationResult(
            transcript=user_text,
            response_text=ai_response,
            audio_bytes=audio_bytes,
            raw_tts=tts_response,
        )
        self._last_result = result
        return result

    def converse(
        self,
        audio_file: str,
        output_file: str = "response.mp3",
        play_audio: bool = True,
    ) -> Optional[str]:
        """
        trasncribe audio, generate response w/ Gemini, speak text
        returns AI's text response
        """
        if (
            self._last_audio_params == (audio_file, play_audio)
            and self._last_result is not None
        ):
            result = self._last_result
            if play_audio and result.raw_tts and hasattr(self.speaker, "playAudioOutputLive"):
                try:
                    self.speaker.playAudioOutputLive(result.raw_tts)
                except Exception as exc:  # pragma: no cover - defensive log
                    LOGGER.warning("Failed to play cached TTS audio: %s", exc)
        else:
            result = self.converse_with_details(audio_file, play_audio=play_audio)
        if not result:
            return None
        if output_file and hasattr(self.speaker, "writeAudioOutputToFile") and result.raw_tts:
            try:
                self.speaker.writeAudioOutputToFile(result.raw_tts, output_file)
            except Exception as exc:  # pragma: no cover - defensive log
                LOGGER.warning("Failed to write TTS audio to file %s: %s", output_file, exc)
        return result.response_text


def build_voice_assistant_from_env(
    *,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
    use_vertex_override: Optional[bool] = None,
    stt_overrides: Optional[Dict[str, Any]] = None,
) -> VoiceAssistant:
    """Factory that wires a VoiceAssistant based on environment settings."""

    env_project = project_id or os.getenv("VOICE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    env_location = location or os.getenv("VOICE_LOCATION", "us-central1")
    use_vertex_env = os.getenv("VOICE_USE_VERTEX")
    if use_vertex_override is not None:
        use_vertex = use_vertex_override
    elif use_vertex_env is not None:
        use_vertex = use_vertex_env.lower() in {"1", "true", "yes", "on"}
    else:
        use_vertex = False

    stt_kwargs: Dict[str, Any] = dict(stt_overrides or {})
    language = stt_kwargs.setdefault("language_code", os.getenv("VOICE_LANGUAGE", "en-US"))
    model_name = os.getenv("VOICE_VERTEX_MODEL")
    if model_name:
        stt_kwargs["model_name"] = model_name
    instruction = os.getenv("VOICE_VERTEX_INSTRUCTION")
    if instruction:
        stt_kwargs["instruction"] = instruction

    assistant = VoiceAssistant(
        project_id=env_project or "test-project",
        location=env_location,
        max_retries=int(os.getenv("VOICE_MAX_RETRIES", "3")),
        use_vertex_stt=use_vertex,
        stt_kwargs={**stt_kwargs, "language_code": language},
    )

    if not assistant.enabled:
        LOGGER.warning("VoiceAssistant initialised from env but is disabled")
    else:
        LOGGER.info(
            "VoiceAssistant ready (project=%s, location=%s, vertex=%s, language=%s)",
            env_project,
            env_location,
            use_vertex,
            language,
        )

    return assistant


