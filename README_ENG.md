# Vinmec ReAct Agent

A virtual assistant for **Vinmec** hospital built on a **hand-crafted ReAct Agent** (Thought → Action → Observation). The agent calls tools to retrieve real data instead of hallucinating answers like a plain chatbot.

**Author:** Nguyen Hoang Long — 2A202600785

---

## Features

- Look up examination prices and estimate costs after insurance
- Find the nearest Vinmec facility + Google Maps directions
- Check doctor availability by specialty and book appointments
- Infer the correct medical specialty from symptoms described by the user
- Emergency support: call 115, provide immediate first-aid instructions
- Reject out-of-scope questions (medical guardrail)
- Web demo (Flask) with ReAct trace, map card, and emergency card

---

## Requirements

- Python **3.10+**
- (Optional) [Ollama](https://ollama.com) for running a local LLM

---

## Installation

```bash
# 1. Clone the repo
git clone <repo-url>
cd Vinmec_Booking_Agent

# 2. Create a virtual environment (recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Environment Configuration

Copy the example file and fill in your API keys:

```bash
cp .env.example .env
```

Contents of `.env`:

```env
# Choose a provider: openai | google | openrouter | local
DEFAULT_PROVIDER=openrouter

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# OpenAI
OPENAI_API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4o

# OpenRouter (multiple models, one API key)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=google/gemini-3.1-flash-lite

# Local LLM via Ollama
OLLAMA_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
```

> Only fill in the key for the provider you intend to use.

---

## Running the App

### CLI (terminal)

```bash
python main.py
```

Type a question or press Enter to use the default sample question.

### Web Demo (Flask)

```bash
python app.py
```

Open your browser at **http://localhost:5000**

The web interface supports:
- Real-time chat with the agent
- Automatic GPS location request from the browser
- ReAct trace display (Thought / Action / Observation)
- Google Maps directions card
- Emergency card with first-aid instructions
- Per-turn metrics: steps, tokens, latency, cost

---

## Running with a Local LLM (Ollama)

```bash
# 1. Install Ollama: https://ollama.com/download

# 2. Pull the model
ollama pull llama3.1:8b

# 3. Set the provider in .env
DEFAULT_PROVIDER=local

# 4. Run as usual
python main.py
# or
python app.py
```

> Llama 3.1 8B requires ~5 GB of RAM. Ollama automatically starts as a service on Windows boot.

---

## Running Tests

```bash
# Full 16-case test suite (Easy → Very Hard)
python tests/test_case.py

# Test the Ollama provider only
python tests/test_local.py
```

Sample output:

```
=== RUNNING 16 CASES | model: google/gemini-3.1-flash-lite ===

[L1-01 | 1-Easy     | PASS ✅] Look up price for one service
[L2-02 | 2-Medium   | PASS ✅] Price + insurance (Vinmec Care -70%)
[L3-01 | 3-Hard     | PASS ✅] Find nearest facility (geolocation)
[L4-03 | 4-VeryHard | PASS ✅] Emergency chest pain: 115 + first aid
...

================================================================
  TOTAL   : 16/16 (100%)
  Tokens  : 100524 | Avg Latency: 1643 ms | Cost: $1.0052
================================================================
```

---

## Project Structure

```
Vinmec_Booking_Agent/
├── main.py                         # CLI entry point
├── app.py                          # Web demo (Flask)
├── requirements.txt
├── .env.example
│
├── src/
│   ├── agent/agent.py              # ReActAgent — the ReAct loop
│   ├── core/
│   │   ├── llm_provider.py         # Abstract base class
│   │   ├── openai_provider.py
│   │   ├── gemini_provider.py
│   │   ├── openrouter_provider.py
│   │   └── local_provider.py       # Ollama provider
│   ├── tools/
│   │   ├── vinmec_tools.py         # 8 tool definitions
│   │   └── vinmec_data.json        # Mock data (facilities, prices, schedules, first aid)
│   └── telemetry/
│       ├── logger.py               # Structured JSON logging
│       └── metrics.py              # Token / latency / cost tracking
│
├── templates/index.html            # Web chat UI
├── tests/
│   ├── test_case.py                # 16 tiered test cases
│   └── test_local.py               # Ollama provider test
└── report/
    └── individual_reports/
        └── REPORT_Nguyen_Hoang_Long_2A202600785.md
```

---

## Supported Providers

| `DEFAULT_PROVIDER` | Default Model | Requirement |
|---|---|---|
| `google` | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| `openrouter` | `google/gemini-3.1-flash-lite` | `OPENROUTER_API_KEY` |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| `local` | `llama3.1:8b` | Ollama running locally |

---

## Agent Tools (8 total)

| Tool | Function |
|---|---|
| `get_current_location` | Locate the user (GPS → IP → fallback) |
| `find_nearest_vinmec` | Nearest Vinmec facility (Haversine distance) |
| `get_service_price` | Look up examination price |
| `apply_insurance` | Calculate cost after insurance discount |
| `check_doctor_availability` | Check doctor schedule by specialty |
| `book_appointment` | Book an appointment + generate confirmation code |
| `get_emergency_contact` | Emergency number 115 + nearest facility |
| `get_first_aid` | First-aid instructions by condition |
