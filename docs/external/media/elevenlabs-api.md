# ElevenLabs API Reference

Official documentation: https://elevenlabs.io/docs/api-reference

Last updated: 2025-12-06

## Authentication

All requests require the `xi-api-key` header with your ElevenLabs API key.

```
xi-api-key: your_api_key_here
```

## Base URL

```
https://api.elevenlabs.io/v1
```

---

## Text-to-Speech API

### Convert Text to Speech

**Endpoint:** `POST /text-to-speech/{voice_id}`

Converts text into speech using a voice of your choice and returns audio.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `voice_id` | string | Yes | Identifier for the voice to use |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `enable_logging` | boolean | No | Activates zero retention mode for enterprise customers |
| `optimize_streaming_latency` | integer (0-4) | No | Latency optimization level. 4 disables text normalization |
| `output_format` | string | No | Audio codec and quality specification |

#### Request Body

```json
{
  "text": "Hello world!",
  "model_id": "eleven_multilingual_v2",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": true
  }
}
```

**Required Fields:**
- `text` (string): The content to synthesize

**Optional Fields:**
- `model_id` (string): Model selection (default: "eleven_monolingual_v1")
- `language_code` (string | null): Language code for multilingual models
- `voice_settings` (object): Voice configuration
  - `stability` (float 0-1): Voice stability. Higher = more consistent
  - `similarity_boost` (float 0-1): Speaker similarity. Higher = more similar
  - `style` (float 0-1): Style exaggeration. Higher = more expressive
  - `use_speaker_boost` (boolean): Enable speaker boost for clearer audio
  - `speed` (float): Speech speed multiplier
- `pronunciation_dictionary_locators` (array): Custom pronunciation mappings
- `seed` (integer | null): Random seed for reproducibility
- `previous_text` (string | null): Context from previous text
- `next_text` (string | null): Context from next text
- `apply_text_normalization` (enum): "auto", "on", "off"

#### Response

- **200 Success:** Binary audio file (application/octet-stream)
- **422 Error:** Validation error response

---

### Stream Text to Speech

**Endpoint:** `POST /text-to-speech/{voice_id}/stream`

Converts text into speech and returns audio as a continuous stream.

#### Parameters

Same as Convert Text to Speech endpoint.

#### Response

- **200 Success:** `text/event-stream` content type, audio data as binary stream

---

## Output Format Options

Formats follow `codec_samplerate_bitrate` pattern:

### MP3 Formats
- `mp3_22050_32` - MP3 at 22.05kHz, 32kbps
- `mp3_44100_64` - MP3 at 44.1kHz, 64kbps
- `mp3_44100_96` - MP3 at 44.1kHz, 96kbps
- `mp3_44100_128` - MP3 at 44.1kHz, 128kbps (default)
- `mp3_44100_192` - MP3 at 44.1kHz, 192kbps (Creator+ tier)

### PCM Formats
- `pcm_8000` - PCM at 8kHz, 16-bit
- `pcm_16000` - PCM at 16kHz, 16-bit
- `pcm_22050` - PCM at 22.05kHz, 16-bit
- `pcm_24000` - PCM at 24kHz, 16-bit
- `pcm_44100` - PCM at 44.1kHz, 16-bit (Pro tier)
- `pcm_48000` - PCM at 48kHz, 16-bit (Pro tier)

### Opus Formats
- `opus_48000_32` - Opus at 48kHz, 32kbps
- `opus_48000_64` - Opus at 48kHz, 64kbps
- `opus_48000_96` - Opus at 48kHz, 96kbps
- `opus_48000_128` - Opus at 48kHz, 128kbps
- `opus_48000_192` - Opus at 48kHz, 192kbps

### Telephony Formats
- `ulaw_8000` - u-law at 8kHz
- `alaw_8000` - a-law at 8kHz

---

## Available Models

| Model ID | Description |
|----------|-------------|
| `eleven_multilingual_v2` | Best quality, supports 29 languages |
| `eleven_multilingual_v1` | Original multilingual model |
| `eleven_monolingual_v1` | English only, fastest |
| `eleven_turbo_v2` | Low latency, English optimized |
| `eleven_turbo_v2_5` | Newest turbo model |

---

## Voices API

### List All Voices

**Endpoint:** `GET /voices`

Returns all available voices including premade and custom voices.

#### Response

```json
{
  "voices": [
    {
      "voice_id": "21m00Tcm4TlvDq8ikWAM",
      "name": "Rachel",
      "category": "premade",
      "description": "A calm female voice",
      "labels": {
        "accent": "american",
        "gender": "female",
        "age": "young"
      },
      "preview_url": "https://...",
      "settings": {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": true
      }
    }
  ]
}
```

### Get Voice

**Endpoint:** `GET /voices/{voice_id}`

Returns details for a specific voice.

### Get Voice Settings

**Endpoint:** `GET /voices/{voice_id}/settings`

Returns default settings for a voice.

---

## User/Subscription

### Get Subscription Info

**Endpoint:** `GET /user/subscription`

Returns subscription details including character quota and usage.

---

## Pricing (as of early 2025)

Per 1000 characters:

| Tier | Price per 1K chars |
|------|-------------------|
| Free | $0.00 |
| Starter | $0.30 |
| Creator | $0.22 |
| Pro | $0.18 |
| Scale | $0.11 |
| Business | $0.07 |

---

## Default Voice IDs

Common premade voices for quick reference:

| Name | Voice ID | Description |
|------|----------|-------------|
| Rachel | 21m00Tcm4TlvDq8ikWAM | Female, American, calm |
| Drew | 29vD33N1CtxCmqQRPOHJ | Male, American, conversational |
| Clyde | 2EiwWnXFnvU5JabPnv8n | Male, American, war veteran |
| Domi | AZnzlk1XvdvUeBnXmlld | Female, American, strong |
| Dave | CYw3kZ02Hs0563khs1Fj | Male, British, conversational |
| Fin | D38z5RcWu1voky8WS1ja | Male, Irish, conversational |
| Bella | EXAVITQu4vr4xnSDxMaL | Female, American, soft |
| Antoni | ErXwobaYiN019PkySvjV | Male, American, well-rounded |
| Josh | TxGEqnHWrfWFTfGW9XjX | Male, American, deep |
| Arnold | VR6AewLTigWG4xSOukaG | Male, American, crisp |
| Adam | pNInz6obpgDQGcFmaJgB | Male, American, deep |
| Sam | yoZ06aMxZJJ28mfd3POQ | Male, American, raspy |

---

## Rate Limits

- Rate limits vary by subscription tier
- 429 responses include `Retry-After` header
- Implement exponential backoff for retries

---

## Error Responses

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "text"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 429 Rate Limit

```json
{
  "detail": "Rate limit exceeded"
}
```

Headers include:
- `Retry-After`: Seconds to wait before retrying
