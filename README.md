# Intent-Driven Cold Outreach Agent

A Masumi SDK-based AI agent that generates hyper-personalized cold outreach emails using real-time company research and intent signals. Built for the Masumi/Sokosumi marketplace.

## Features

- **Real-time research** — Tavily API searches for recent company news, funding, hiring, and tech adoption
- **Intent-driven personalization** — Emails reference specific, verifiable facts about the prospect's company
- **Quality guardrails** — Banned phrase detection, word count enforcement, and confidence scoring
- **Non-blocking async** — Tavily sync calls wrapped in `asyncio.to_thread()` so Railway's event loop is never blocked
- **Graceful degradation** — Research failures are non-fatal; the agent still generates a useful email from provided context
- **Privacy-first** — Prospect email addresses are never logged or included in output

## Architecture

```
main.py              → Masumi SDK entry point + env validation
agent.py             → Orchestration: normalize → research → generate → format
researcher.py        → Async Tavily research (non-fatal failures)
email_generator.py   → OpenAI gpt-4o-mini email generation (fatal failures)
formatter.py         → Clean output formatting for buyers
```

## Setup

### Prerequisites

- Python 3.11+
- OpenAI API key ([platform.openai.com](https://platform.openai.com))
- Tavily API key ([tavily.com](https://tavily.com) — 1,000 free searches/month)
- Masumi SDK credentials

### Installation

```bash
git clone https://github.com/kp183/intent.git
cd intent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

**Required:**
- `OPENAI_API_KEY` — OpenAI API key
- `TAVILY_API_KEY` — Tavily search API key
- `AGENT_IDENTIFIER` — Masumi agent identifier

**Set by Railway (do not change):**
- `PAYMENT_API_KEY` — Masumi payment key
- `SELLER_VKEY` — Seller verification key
- `NETWORK` — `Preprod` or `Mainnet`

**Optional tuning:**
- `OPENAI_TIMEOUT` — OpenAI request timeout in seconds (default: 60)
- `RESEARCH_TIMEOUT` — Tavily search timeout in seconds (default: 30)

## Running

### Local Development

```bash
python main.py
```

The agent starts on `http://0.0.0.0:8081`. Expose publicly with:

```bash
ngrok http 8081
```

### Deploy to Railway

1. Push to GitHub
2. Connect repo in Railway dashboard
3. Add environment variables in Railway → Variables tab
4. Railway auto-detects Python and deploys using the Procfile

## API Endpoints

- `GET /docs` — API documentation
- `GET /availability` — Health check
- `GET /input_schema` — Returns accepted input fields
- `POST /start_job` — Starts an outreach generation job

## Input Schema

| Field | Type | Description |
|-------|------|-------------|
| `prospect_name` | text | Prospect's full name |
| `prospect_email` | email | Prospect's email (used internally, never in output) |
| `prospect_role` | text | Job title (e.g., VP of Engineering) |
| `company_name` | text | Company name |
| `company_industry` | text | Industry sector |
| `company_size` | option | startup, small, medium, large, enterprise |
| `intent_signal` | option | job_change, funding_event, technology_adoption, company_growth, industry_trend |
| `intent_description` | text | Free-text description of the intent signal |

## Output Format

```json
{
  "status": "success",
  "prospect": {
    "name": "John Smith",
    "role": "VP of Engineering",
    "company": "Acme Corp"
  },
  "intent_signal": "funding_event",
  "research": {
    "successful": true,
    "findings": [
      "Acme Corp raised $12M Series A in November 2024 (TechCrunch)",
      "Headcount grew from 45 to 120 employees in 12 months"
    ],
    "summary": "Research on Acme Corp: ...",
    "sources_used": 3
  },
  "email": {
    "subject": "Congrats on the raise, John",
    "body": "Hi John,\n\nSaw the Series A news — congrats...",
    "word_count": 127
  },
  "quality_metrics": {
    "confidence_score": 0.91,
    "personalization_score": 0.94,
    "recommended_follow_up_days": 3,
    "reasoning": "Funding creates a 72-hour window where new budget decisions are made.",
    "research_backed": true
  },
  "generated_at": "2025-01-15T10:30:00.000Z"
}
```

## Testing

```bash
pytest tests/ -v
```

## License

MIT
