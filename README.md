# Aria — AI Voice Receptionist for Clinics

Aria is an AI-powered phone receptionist that answers incoming calls for clinics,
holds a natural spoken conversation with the caller, and answers questions about
the clinic (hours, services, location, insurance) — without giving medical advice.

It runs as a small Flask web service that Twilio calls into. Speech is transcribed
by Twilio, answered by a Groq-hosted LLM, and spoken back to the caller.

## How it works

```
Caller ──dials──▶ Twilio number ──POST /incoming-call──▶ Aria (Flask)
                                                            │
   caller speaks ──▶ Twilio speech-to-text ──POST /handle-speech──▶ Groq LLM
                                                            │
   Aria's reply ◀── Twilio text-to-speech ◀────────────────┘  (loops until goodbye)
```

1. **Incoming call** — Twilio hits `POST /incoming-call`. Aria looks up which clinic
   was called (by the dialed number), greets the caller, and starts listening.
2. **Conversation turn** — each time the caller speaks, Twilio sends the transcript to
   `POST /handle-speech`. Aria adds it to the call's history, asks the Groq LLM for a
   reply, speaks it back, and keeps listening.
3. **Ending** — if the caller says something like "goodbye", "bye", "thank you", or
   "that's all", Aria says its final line and hangs up.

## Multi-clinic support

One deployment can serve several clinics. Each Twilio phone number is mapped to a
clinic profile, so the same code answers as the right clinic with the right details
and the right guardrails (dental / medical / chiropractic).

- `CLINICS` — the clinic profiles (name, address, hours, services, team, insurance).
- `NUMBER_TO_CLINIC` — maps each Twilio number to a clinic key. Unknown numbers fall
  back to the `medical` profile.
- `build_prompt()` — builds the system prompt: shared rules (stay brief, phone-friendly,
  never give medical advice) plus clinic-type-specific rules and the clinic's info.

## Tech stack

- **Flask** — web server
- **Twilio Voice** (`VoiceResponse`, `Gather`) — telephony + speech-to-text + text-to-speech
- **Groq** — LLM inference (`llama-3.3-70b-versatile`)
- **Gunicorn** — production WSGI server (see `Procfile`)

## Endpoints

| Method | Route             | Purpose                                         |
|--------|-------------------|-------------------------------------------------|
| POST   | `/incoming-call`  | Twilio webhook for a new call; greets the caller |
| POST   | `/handle-speech`  | Twilio webhook for each spoken turn              |
| GET    | `/health`         | Health check (`Aria is running!`)               |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

| Variable        | Required | Description                                   |
|-----------------|----------|-----------------------------------------------|
| `GROQ_API_KEY`  | yes      | API key for Groq LLM inference                |
| `PORT`          | no       | Port to bind (defaults to `5000`)             |

```bash
export GROQ_API_KEY="your-groq-api-key"
```

### 3. Run locally

```bash
python app.py
```

To let Twilio reach your local server, expose it with a tunnel (e.g. `ngrok http 5000`)
and point your Twilio number's voice webhook at `https://<your-tunnel>/incoming-call`.

## Deployment

The included `Procfile` runs Aria under Gunicorn:

```
web: gunicorn app:app
```

This deploys on any Procfile-based host (Render, Railway, Heroku, etc.). Set
`GROQ_API_KEY` in the host's environment, then set your Twilio number's voice webhook to:

```
https://<your-app-url>/incoming-call
```

## Configuration notes

- Update `CLINICS` and `NUMBER_TO_CLINIC` with your real clinic details and Twilio numbers.
- Aria is instructed to keep replies short (under two sentences) since it's a phone call,
  and to never give medical, dental, or diagnostic advice — deferring to 911 / in-person
  care for emergencies.
- Conversation history is kept in memory per call, so it resets on restart and is not
  shared across server instances.
