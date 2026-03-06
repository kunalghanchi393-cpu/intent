#!/usr/bin/env python3
"""
Intent-Driven Cold Outreach Agent - Masumi SDK Integration
Business logic only.
Masumi SDK handles protocol, payments, blockchain, lifecycle.
"""

import os
import json
import aiohttp
import logging
from typing import Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

OUTREACH_SERVICE_URL = os.getenv("OUTREACH_SERVICE_URL", "http://localhost:3000")
OUTREACH_TIMEOUT = int(os.getenv("OUTREACH_TIMEOUT", "30"))

COMPANY_SIZE_OPTIONS = ["startup", "small", "medium", "large", "enterprise"]
INTENT_SIGNAL_OPTIONS = [
    "job_change",
    "funding_event",
    "technology_adoption",
    "company_growth",
    "industry_trend"
]


def normalize_input_data(raw: Any) -> dict:
    """
    Sokosumi may send input_data as either:
      - A list: [{"id": "prospect_name", "value": "John"}]
      - A dict: {"prospect_name": "John"}
    This normalizes both into a flat dict.
    """
    if isinstance(raw, list):
        return {item["id"]: item.get("value") for item in raw if "id" in item}
    if isinstance(raw, dict):
        return raw
    logger.warning(f"Unexpected input_data type: {type(raw)}, defaulting to empty dict")
    return {}


def convert_option_value(value: Any, options: List[str]) -> str:
    """Handle string, list index, or int index formats for option fields."""
    if isinstance(value, str) and value in options:
        return value
    if isinstance(value, list) and len(value) > 0:
        index = value[0]
        if isinstance(index, int) and 0 <= index < len(options):
            return options[index]
        if isinstance(index, str) and index in options:
            return index
    if isinstance(value, int) and 0 <= value < len(options):
        return options[value]
    logger.warning(f"Invalid option value '{value}', defaulting to '{options[0]}'")
    return options[0]


async def process_job(identifier_from_purchaser, input_data):

    identifier = job_request.identifier_from_purchaser
    input_data = job_request.input_data

    logger.info(f"Processing job {identifier}")
    logger.info(f"Input data received: {input_data}")

    try:

        input_data = normalize_input_data(input_data)

        company_size = convert_option_value(
            input_data.get("company_size", "medium"),
            COMPANY_SIZE_OPTIONS
        )

        intent_signal_type = convert_option_value(
            input_data.get("intent_signal", "company_growth"),
            INTENT_SIGNAL_OPTIONS
        )

        prospect_data = {
            "role": input_data.get("prospect_role", ""),
            "companyContext": {
                "name": input_data.get("company_name", ""),
                "industry": input_data.get("company_industry", "Technology"),
                "size": company_size
            },
            "contactDetails": {
                "name": input_data.get("prospect_name", ""),
                "email": input_data.get("prospect_email", "")
            }
        }

        intent_description = input_data.get("intent_description", "Recent activity")

        intent_signals = [
            {
                "type": intent_signal_type,
                "description": intent_description,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "relevanceScore": 0.8,
                "source": "User Input"
            }
        ]

        outreach_request = {
            "prospectData": prospect_data,
            "intentSignals": intent_signals
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OUTREACH_SERVICE_URL}/agent/outreach",
                json=outreach_request,
                timeout=aiohttp.ClientTimeout(total=OUTREACH_TIMEOUT)
            ) as response:

                result = await response.json()

        return {
            "result": result
        }

    except Exception as e:
        logger.error(f"Job failed: {e}")
        raise

  
