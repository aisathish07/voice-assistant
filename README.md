# Buddy - Voice Assistant

A Python voice assistant with wake word detection, local/online LLM support, and a friendly personality.

## Features

- 🎤 **Wake Word Detection** - "Hey Jarvis" using openWakeWord
- 🗣️ **VAD-based Listening** - Silero VAD detects when you stop speaking
- 🧠 **Dual LLM Support** - Local (Ollama) + Online (Gemini) with fallback
- 🔊 **High-Quality TTS** - edge-tts with pyttsx3 offline fallback
- 💬 **Friendly Personality** - Warm, conversational assistant

## Prerequisites

1. **Python 3.10+**
2. **Ollama** (for local LLM):
   ```bash
   # Install from https://ollama.ai
   ollama pull llama3.2
   ollama serve
   ```
3. **Gemini API Key** (for online fallback)

## Installation

```bash
cd c:\Users\h0093\Documents\new
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file:
```env
GEMINI_API_KEY=your_api_key_here
OLLAMA_MODEL=llama3.2
WHISPER_MODEL=base
```

## Usage

```bash
python main.py
```

Say "Hey Jarvis" to activate, speak your question, and wait for the response!

## Architecture

```
IDLE → WAKE (ding) → LISTENING (VAD) → PROCESSING → STREAMING (TTS)
  ↑                                                        ↓
  └────────────────────────────────────────────────────────┘
```
