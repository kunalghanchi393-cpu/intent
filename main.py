#!/usr/bin/env python3
"""
masumi-agent - Main Entry Point
This is the entry point for the Masumi agent server.
"""

from dotenv import load_dotenv
load_dotenv()

from masumi import run
from agent import process_job

# Input schema — Masumi/Sokosumi format
INPUT_SCHEMA = {
    "input_data": [
        {
            "id": "prospect_name",
            "type": "text",
            "name": "Prospect Name",
            "data": {"placeholder": "Enter prospect's full name"}
        },
        {
            "id": "prospect_email",
            "type": "email",
            "name": "Prospect Email",
            "data": {"placeholder": "prospect@company.com"}
        },
        {
            "id": "prospect_role",
            "type": "text",
            "name": "Prospect Role",
            "data": {"placeholder": "e.g., VP of Sales"}
        },
        {
            "id": "company_name",
            "type": "text",
            "name": "Company Name",
            "data": {"placeholder": "Enter company name"}
        },
        {
            "id": "company_industry",
            "type": "text",
            "name": "Company Industry",
            "data": {"placeholder": "e.g., Technology, Healthcare"}
        },
        {
            "id": "company_size",
            "type": "option",
            "name": "Company Size",
            "data": {"values": ["startup", "small", "medium", "large", "enterprise"]}
        },
        {
            "id": "intent_signal",
            "type": "option",
            "name": "Intent Signal Type",
            "data": {
                "values": [
                    "job_change",
                    "funding_event",
                    "technology_adoption",
                    "company_growth",
                    "industry_trend"
                ]
            }
        },
        {
            "id": "intent_description",
            "type": "text",
            "name": "Intent Description",
            "data": {"placeholder": "Describe the intent signal"}
        }
    ]
}


def get_schema():
    return INPUT_SCHEMA


# Entry point — works both via `python main.py` and Railway's Procfile
run(
    start_job_handler=process_job,
    input_schema_handler=get_schema
)
