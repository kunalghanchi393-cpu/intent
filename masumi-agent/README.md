# Intent-Driven Cold Outreach Agent

A Masumi SDK-based agent that generates personalized cold outreach messages based on prospect data and intent signals.

## Features

- Intent-driven message generation
- Personalized outreach based on prospect context
- Company size and industry analysis
- Multiple message alternatives
- Follow-up timing recommendations

## Setup

### Prerequisites

- Python 3.8+
- Masumi SDK credentials

### Installation

1. Clone the repository:
```bash
git clone https://github.com/kp183/intent.git
cd intent/masumi-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

Get your credentials from the Masumi admin interface:
- `AGENT_IDENTIFIER` - Your agent's unique identifier (120 characters)
- `SELLER_VKEY` - Your seller verification key
- `PAYMENT_API_KEY` - Your payment API key

## Running the Agent

### Start the agent:
```bash
python main.py
```

The agent will start on `http://0.0.0.0:8081`

### Expose publicly with ngrok:
```bash
ngrok http 8081
```

## API Endpoints

- **API Documentation**: `/docs`
- **Availability Check**: `/availability`
- **Input Schema**: `/input_schema`
- **Start Job**: `/start_job`

## Input Schema

The agent accepts the following inputs:

- `prospect_name` (string) - Name of the prospect
- `prospect_email` (string) - Email address
- `prospect_role` (string) - Job role/title
- `company_name` (string) - Company name
- `company_industry` (string) - Industry sector
- `company_size` (options) - startup, small, medium, large, enterprise
- `intent_signal` (options) - job_change, funding_event, technology_adoption, company_growth, industry_trend
- `intent_description` (string) - Description of the intent signal

## Output

The agent returns:

- `intentConfidence` - Confidence score for the intent
- `reasoningSummary` - Analysis of the prospect
- `recommendedMessage` - Primary outreach message
- `alternativeMessages` - Alternative message options
- `suggestedFollowUpTiming` - Recommended follow-up schedule
- `processingMetadata` - Processing details

## Architecture

- `agent.py` - Business logic for outreach generation
- `main.py` - Masumi SDK entry point
- Integrates with Node.js outreach service for message generation

## License

MIT
