# Input Parser (The "Whisper" Layer)

## Overview
Converts voice input to structured intent (JSON) using speech-to-text and LLM-powered intent mapping.

## Technology
* **STT:** OpenAI Whisper-v3 or Deepgram for speech-to-text
* **Intent Mapping:** LLM to parse prose to query schema

## Key Functions
- Convert voice commands to structured queries
- Handle vague inputs with defaults (Home City, Favorite Genres)
- Extract event preferences and constraints

## Edge Cases
- **Vague Input:** Default to user's "Home City" and "Favorite Genres" from database
- **Ambiguous Intent:** Request clarification from user
