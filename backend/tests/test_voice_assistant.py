"""
Comprehensive test suite for TTS, STT, and GeminiAssistant classes.

Run with: pytest backend/tests/test_voice_assistant.py -v

Note: Some tests require valid Google Cloud credentials and may be skipped
if credentials are not available.
"""
import pytest
import os
import sys
import tempfile
import logging
from pathlib import Path
from typing import Optional

import numpy as np

# Add project root to Python path to enable imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from speech_clients import TTS, STT
from gemini_assistant import GeminiAssistant
from vertex_speech import VertexSpeechToText
from voice_pipeline import VoiceAssistant

# Configure logging for tests
LOGGER = logging.getLogger("test_voice_assistant")


# ============================================================================
# TTS (Text-to-Speech) Tests
# ============================================================================

class TestTTS:
    """Test suite for TTS class"""
    
    def test_tts_initialization(self):
        """Test TTS class initialization"""
        tts = TTS()
        assert hasattr(tts, 'client')
        assert hasattr(tts, 'voice')
        assert hasattr(tts, 'audio_config')
        assert hasattr(tts, 'enabled')
        assert hasattr(tts, 'cache')
        assert isinstance(tts.cache, dict)
    
    def test_tts_initialization_with_params(self):
        """Test TTS initialization with custom parameters"""
        tts = TTS(language_code="en-GB", gender="FEMALE")
        assert tts.voice.language_code == "en-GB"
        # Note: enabled status depends on credentials
    
    def test_tts_synthesize_disabled(self):
        """Test synthesize returns None when TTS is disabled"""
        tts = TTS()
        if not tts.enabled:
            result = tts.synthesize("Hello, world!")
            assert result is None, "Should return None when disabled"
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_tts_synthesize_enabled(self):
        """Test synthesize when TTS is enabled (requires credentials)"""
        tts = TTS()
        if tts.enabled:
            result = tts.synthesize("Hello, this is a test.")
            assert result is not None, "Should return audio response when enabled"
            assert hasattr(result, 'audio_content'), "Response should have audio_content"
            assert len(result.audio_content) > 0, "Audio content should not be empty"
    
    def test_tts_synthesize_empty_text(self):
        """Test synthesize with empty text"""
        tts = TTS()
        result = tts.synthesize("")
        assert result is None, "Should return None for empty text"
    
    def test_tts_synthesize_none_text(self):
        """Test synthesize with None text"""
        tts = TTS()
        result = tts.synthesize(None)  # type: ignore[arg-type]
        assert result is None, "Should return None for None text"
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_tts_caching(self):
        """Test that TTS caches responses"""
        tts = TTS()
        if tts.enabled:
            text = "This is a caching test."
            # First call
            result1 = tts.synthesize(text)
            assert result1 is not None
            # Second call should use cache
            result2 = tts.synthesize(text)
            assert result2 is not None
            assert text in tts.cache, "Text should be in cache"
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_tts_write_audio_to_file(self):
        """Test writing audio output to file"""
        tts = TTS()
        if tts.enabled:
            response = tts.synthesize("Test audio file output.")
            if response:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                    output_path = tmp_file.name
                
                try:
                    result_path = tts.writeAudioOutputToFile(response, output_path)
                    assert result_path == output_path
                    assert os.path.exists(output_path), "Output file should exist"
                    assert os.path.getsize(output_path) > 0, "Output file should not be empty"
                finally:
                    if os.path.exists(output_path):
                        os.remove(output_path)


# ============================================================================
# STT (Speech-to-Text) Tests
# ============================================================================

class TestSTT:
    """Test suite for STT class"""
    
    def test_stt_initialization(self):
        """Test STT class initialization"""
        stt = STT()
        assert hasattr(stt, 'client')
        assert hasattr(stt, 'enabled')
        assert hasattr(stt, 'language_code')
        assert hasattr(stt, 'cache')
        assert hasattr(stt, 'timeout_s')
        assert hasattr(stt, 'max_retries')
        assert isinstance(stt.cache, dict)
    
    def test_stt_initialization_with_params(self):
        """Test STT initialization with custom parameters"""
        stt = STT(language_code="en-GB", timeout_s=15.0, max_retries=5)
        assert stt.language_code == "en-GB"
        assert stt.timeout_s == 15.0
        assert stt.max_retries == 5
    
    def test_stt_transcribe_disabled(self):
        """Test transcribe returns None when STT is disabled"""
        stt = STT()
        if not stt.enabled:
            result = stt.transcribe("nonexistent.wav")
            assert result is None, "Should return None when disabled"
    
    def test_stt_transcribe_nonexistent_file(self):
        """Test transcribe with non-existent file"""
        stt = STT()
        result = stt.transcribe("this_file_does_not_exist.wav")
        assert result is None, "Should return None for non-existent file"
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_stt_transcribe_valid_file(self):
        """Test transcribe with valid audio file (requires credentials and test audio)"""
        stt = STT()
        if stt.enabled:
            # Create a minimal test audio file (WAV format, LINEAR16, 16kHz)
            # Note: This is a placeholder - you'll need actual audio files for real testing
            test_audio_path = "test_audio.wav"
            if os.path.exists(test_audio_path):
                result = stt.transcribe(test_audio_path)
                # Result could be None if no speech detected, or a string if transcription succeeds
                assert result is None or isinstance(result, str)
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_stt_caching(self):
        """Test that STT caches transcriptions"""
        stt = STT()
        if stt.enabled:
            test_audio_path = "test_audio.wav"
            if os.path.exists(test_audio_path):
                # First call
                result1 = stt.transcribe(test_audio_path)
                # Second call should use cache
                result2 = stt.transcribe(test_audio_path)
                if result1 is not None:
                    assert test_audio_path in stt.cache, "File should be in cache"
                    assert result1 == result2, "Cached result should match"


# ============================================================================
# VertexSpeechToText Tests
# ============================================================================


class DummyVertexModel:
    def __init__(self, response_text: str = "unit test transcript"):
        self.response_text = response_text
        self.generate_calls = 0

    def generate_content(self, payload):  # pragma: no cover - simple stub
        self.generate_calls += 1

        class _Response:
            def __init__(self, text: str) -> None:
                self.text = text

        return _Response(self.response_text)


class TestVertexSpeechToText:
    """Test suite for VertexSpeechToText helper"""

    @pytest.fixture
    def project_id(self):
        return os.getenv("GOOGLE_CLOUD_PROJECT", "test-project")

    def test_vertex_stt_initialization(self, project_id):
        stt = VertexSpeechToText(project_id=project_id)
        assert hasattr(stt, "enabled")
        assert hasattr(stt, "transcribe")

    def test_vertex_stt_transcribe_disabled(self, tmp_path, project_id):
        audio_path = tmp_path / "sample.wav"
        audio_path.write_bytes(b"fake audio")
        stt = VertexSpeechToText(project_id=project_id)
        stt.enabled = False
        stt.model = None
        result = stt.transcribe(str(audio_path))
        assert result is None

    def test_vertex_stt_caching_logic(self, tmp_path, project_id):
        audio_path = tmp_path / "cached.wav"
        audio_path.write_bytes(b"fake audio cache test")
        stt = VertexSpeechToText(project_id=project_id)
        stt.enabled = True
        stt.model = DummyVertexModel()
        stt._create_audio_part = lambda *args, **kwargs: (args, kwargs)  # type: ignore
        result1 = stt.transcribe(str(audio_path))
        result2 = stt.transcribe(str(audio_path))
        assert result1 == result2 == "unit test transcript"
        assert stt.model.generate_calls == 1


# ============================================================================
# GeminiAssistant Tests


# ============================================================================
# GeminiAssistant Tests
# ============================================================================

class TestGeminiAssistant:
    """Test suite for GeminiAssistant class"""
    
    @pytest.fixture
    def project_id(self):
        """Get project ID from environment or use default"""
        return os.getenv("GOOGLE_CLOUD_PROJECT", "test-project")
    
    def test_gemini_initialization(self, project_id):
        """Test GeminiAssistant class initialization"""
        assistant = GeminiAssistant(project_id=project_id)
        assert hasattr(assistant, 'model')
        assert hasattr(assistant, 'enabled')
        assert hasattr(assistant, 'max_retries')
        assert hasattr(assistant, 'cache')
        assert hasattr(assistant, 'max_cache_size')
        assert isinstance(assistant.cache, dict)
    
    def test_gemini_initialization_with_params(self, project_id):
        """Test GeminiAssistant initialization with custom parameters"""
        assistant = GeminiAssistant(
            project_id=project_id,
            location="us-east1",
            model_name="gemini-1.5-flash",
            max_retries=5
        )
        assert assistant.max_retries == 5
        assert assistant.max_cache_size == 100
    
    def test_gemini_generate_text_disabled(self, project_id):
        """Test generate_text returns empty string when disabled"""
        assistant = GeminiAssistant(project_id=project_id)
        if not assistant.enabled:
            result = assistant.generate_text("Hello")
            assert result == "", "Should return empty string when disabled"
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_gemini_generate_text_enabled(self, project_id):
        """Test generate_text when enabled (requires credentials)"""
        assistant = GeminiAssistant(project_id=project_id)
        if assistant.enabled:
            result = assistant.generate_text("Say hello in one word.")
            assert isinstance(result, str), "Should return a string"
            assert len(result) > 0, "Should return non-empty response"
    
    def test_gemini_generate_text_with_system_instruction(self, project_id):
        """Test generate_text with system instruction"""
        assistant = GeminiAssistant(project_id=project_id)
        if assistant.enabled:
            system_instruction = "You are a helpful assistant."
            result = assistant.generate_text(
                "What is 2+2?",
                system_instruction=system_instruction
            )
            assert isinstance(result, str)
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_gemini_caching(self, project_id):
        """Test that GeminiAssistant caches responses"""
        assistant = GeminiAssistant(project_id=project_id)
        if assistant.enabled:
            prompt = "What is the capital of France? Answer in one word."
            # First call
            result1 = assistant.generate_text(prompt)
            # Second call should use cache
            result2 = assistant.generate_text(prompt)
            if result1:
                assert prompt in assistant.cache, "Prompt should be in cache"
                assert result1 == result2, "Cached result should match"
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_gemini_cache_size_limit(self, project_id):
        """Test that cache respects max_cache_size"""
        assistant = GeminiAssistant(project_id=project_id, max_retries=1)
        if assistant.enabled:
            # Fill cache beyond max_cache_size
            for i in range(assistant.max_cache_size + 10):
                prompt = f"Test prompt {i}"
                assistant.generate_text(prompt)
            # Cache should not exceed max_cache_size
            assert len(assistant.cache) <= assistant.max_cache_size


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for combined functionality"""
    
    @pytest.fixture
    def project_id(self):
        """Get project ID from environment or use default"""
        return os.getenv("GOOGLE_CLOUD_PROJECT", "test-project")
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and 
        not os.path.exists(os.path.expanduser("~/.config/gcloud/application_default_credentials.json")),
        reason="Google Cloud credentials not available"
    )
    def test_full_pipeline_simulation(self, project_id):
        """Test a simulated full pipeline: TTS -> Gemini -> TTS"""
        tts = TTS()
        gemini = GeminiAssistant(project_id=project_id)
        
        if tts.enabled and gemini.enabled:
            # Step 1: Generate text with Gemini
            prompt = "Say 'Hello, this is a test' in exactly those words."
            gemini_response = gemini.generate_text(prompt)
            assert gemini_response, "Gemini should generate a response"
            
            # Step 2: Convert to speech with TTS
            tts_response = tts.synthesize(gemini_response)
            assert tts_response is not None, "TTS should generate audio"
            assert hasattr(tts_response, 'audio_content'), "Response should have audio content"
    
    def test_all_classes_initialization(self, project_id):
        """Test that all three classes can be initialized together"""
        tts = TTS()
        stt = STT()
        gemini = GeminiAssistant(project_id=project_id)
        
        # All should initialize without errors
        assert tts is not None
        assert stt is not None
        assert gemini is not None
        
        # Log status for debugging
        LOGGER.info(f"TTS enabled: {tts.enabled}")
        LOGGER.info(f"STT enabled: {stt.enabled}")
        LOGGER.info(f"Gemini enabled: {gemini.enabled}")


class DummySTTClient:
    def __init__(self, transcript: Optional[str] = "brush teeth") -> None:
        self.enabled = True
        self.transcript = transcript
        self.calls = 0

    def transcribe(self, filename: str) -> Optional[str]:
        self.calls += 1
        return self.transcript


class DummyGeminiClient:
    def __init__(self, reply: str = "great job") -> None:
        self.enabled = True
        self.reply = reply
        self.calls = 0

    def generate_text(self, prompt: str) -> str:
        self.calls += 1
        return self.reply


class DummyTTSClient:
    def __init__(self) -> None:
        self.enabled = True
        self.synth_calls = 0
        self.play_calls = 0
        self.audio_content = np.random.randint(0, 255, size=128, dtype=np.uint8).tobytes()

    def synthesize(self, text: str):
        self.synth_calls += 1
        return type("_Response", (), {"audio_content": self.audio_content})()

    def playAudioOutputLive(self, response):  # noqa: N802 - keep original casing
        self.play_calls += 1

    def writeAudioOutputToFile(self, response, output_path: str):
        Path(output_path).write_bytes(self.audio_content)
        return output_path


class TestVoiceAssistantPipeline:
    """Unit tests for VoiceAssistant orchestration"""

    def test_voice_assistant_with_injected_clients(self):
        stt = DummySTTClient()
        gemini = DummyGeminiClient()
        tts = DummyTTSClient()

        assistant = VoiceAssistant(
            project_id="test-project",
            stt_client=stt,
            llm_client=gemini,
            tts_client=tts,
            max_retries=2,
        )

        assert assistant.enabled

        detailed = assistant.converse_with_details("fake.wav", play_audio=False)

        assert detailed is not None
        assert detailed.transcript == "brush teeth"
        assert detailed.response_text == "great job"
        assert detailed.raw_tts is not None
        assert isinstance(detailed.audio_bytes, bytes)

        result = assistant.converse("fake.wav", play_audio=False)
        assert result == "great job"
        assert stt.calls == 1
        assert gemini.calls == 1
        assert tts.synth_calls == 1
        assert tts.play_calls == 0

    def test_voice_assistant_writes_audio_file(self, tmp_path):
        stt = DummySTTClient()
        gemini = DummyGeminiClient()
        tts = DummyTTSClient()

        assistant = VoiceAssistant(
            project_id="test-project",
            stt_client=stt,
            llm_client=gemini,
            tts_client=tts,
            max_retries=1,
        )

        output_file = tmp_path / "response.mp3"
        result = assistant.converse(str(tmp_path / "fake.wav"), output_file=str(output_file), play_audio=False)

        assert result == "great job"
        assert output_file.exists()
        assert output_file.read_bytes() == tts.audio_content


# ============================================================================
# Helper Functions for Manual Testing
# ============================================================================

def run_manual_tests():
    """
    Run manual tests that require user interaction or specific test files.
    Call this function directly for interactive testing.
    """
    print("\n" + "="*60)
    print("Manual Test Suite for Voice Assistant Components")
    print("="*60)
    
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "test-project")
    
    # Test TTS
    print("\n[1] Testing TTS...")
    tts = TTS()
    print(f"   TTS enabled: {tts.enabled}")
    if tts.enabled:
        response = tts.synthesize("Hello, this is a TTS test.")
        if response:
            print("   ✓ TTS synthesis successful")
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                output_path = tts.writeAudioOutputToFile(response, tmp.name)
                print(f"   ✓ Audio saved to: {output_path}")
                os.remove(output_path)
        else:
            print("   ✗ TTS synthesis failed")
    
    # Test STT
    print("\n[2] Testing STT...")
    stt = STT()
    print(f"   STT enabled: {stt.enabled}")
    if stt.enabled:
        # Check for test audio file
        test_audio = "test_audio.wav"
        if os.path.exists(test_audio):
            result = stt.transcribe(test_audio)
            if result:
                print(f"   ✓ Transcription successful: {result[:50]}...")
            else:
                print("   ✗ Transcription returned None")
        else:
            print(f"   ⚠ Test audio file '{test_audio}' not found, skipping transcription test")
    
    # Test GeminiAssistant
    print("\n[3] Testing GeminiAssistant...")
    gemini = GeminiAssistant(project_id=project_id)
    print(f"   Gemini enabled: {gemini.enabled}")
    if gemini.enabled:
        result = gemini.generate_text("Say 'test successful' in exactly those words.")
        if result:
            print(f"   ✓ Gemini generation successful: {result[:50]}...")
        else:
            print("   ✗ Gemini generation failed")
    
    print("\n" + "="*60)
    print("Manual tests completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Run manual tests if executed directly
    run_manual_tests()

