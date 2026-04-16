#!/usr/bin/env python3
"""
main.py — Masumi SDK entry point.
Do not change SDK patterns or INPUT_SCHEMA structure.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import logging
from masumi import run
from agent import process_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Warn about missing keys at startup — but don't crash.
# email_generator raises at job time if OPENAI_API_KEY is absent.
# researcher falls back gracefully if TAVILY_API_KEY is absent.
for _var in ["OPENAI_API_KEY", "TAVILY_API_KEY"]:
    if not os.getenv(_var):
        logger.warning("Environment variable %s is not set.", _var)

INPUT_SCHEMA = {
    "input_data": [
        {
            "id": "prospect_name",
            "type": "text",
            "name": "Prospect Name",
            "data": {"placeholder": "Enter prospect's full name"},
        },
        {
            "id": "prospect_email",
            "type": "email",
            "name": "Prospect Email",
            "data": {"placeholder": "prospect@company.com"},
        },
        {
            "id": "prospect_role",
            "type": "text",
            "name": "Prospect Role",
            "data": {"placeholder": "e.g., VP of Sales"},
        },
        {
            "id": "company_name",
            "type": "text",
            "name": "Company Name",
            "data": {"placeholder": "Enter company name"},
        },
        {
            "id": "company_industry",
            "type": "text",
            "name": "Company Industry",
            "data": {"placeholder": "e.g., Technology"},
        },
        {
            "id": "company_size",
            "type": "option",
            "name": "Company Size",
            "data": {"values": ["startup", "small", "medium", "large", "enterprise"]},
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
                    "industry_trend",
                ]
            },
        },
        {
            "id": "intent_description",
            "type": "text",
            "name": "Intent Description",
            "data": {"placeholder": "Describe the intent signal — e.g. they just raised Series A"},
        },
    ]
}


def get_schema():
    return INPUT_SCHEMA


if __name__ == "__main__":
    run(
        start_job_handler=process_job,
        input_schema_handler=get_schema,
    )
