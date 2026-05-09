# Voice Assistant & GenAI

To provide a conversational and supportive environment, the Assistive Mirror integrates voice capabilities and Generative AI.

## Text-to-Speech (TTS)

Local, fallback text-to-speech is handled in `app.py` via system binaries:
1. `say` (macOS native)
2. `espeak-ng` (Linux/Raspberry Pi)
3. `pyttsx3` (Python library fallback)

When a step advances, the backend shells out to these local binaries to provide instantaneous auditory feedback ("Great job, now grab your comb").

## `voice_pipeline.py` & Speech Services

For more advanced, cloud-backed speech, the `speech_clients.py` and `vertex_speech.py` modules integrate with Google Cloud.
- **Speech-to-Text (STT)**: Transcribes the user's audio input.
- **Advanced TTS**: Utilizes Google Cloud TTS for highly natural, empathetic voices, which is particularly beneficial for users with neurodevelopmental conditions who respond better to natural intonation.

## Gemini Assistant (`gemini_assistant.py`)

The mirror is not just a hardcoded state machine; it includes dynamic coaching powered by Gemini 1.5 Pro.

### Implementation
The `VoiceAssistant` class initializes a Gemini chat session initialized with a strict system prompt. The prompt directs the AI to act as an encouraging, concise occupational therapy assistant.

### Flow
1. User asks a question ("I forgot how to hold the toothbrush") via the frontend microphone button.
2. The frontend POSTs the audio blob to `/voice/converse`.
3. The backend transcribes the audio (STT).
4. The transcript is sent to the Gemini chat session.
5. Gemini generates a contextually aware, supportive text response.
6. The text response is synthesized into audio (TTS) and returned to the frontend as a Base64 string for immediate playback.
