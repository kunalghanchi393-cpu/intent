#!/usr/bin/env python3
"""
Intent-Driven Cold Outreach Agent - Masumi SDK Integration
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


def normalize_input(raw: Any) -> dict:
    """Handle both list and dict shapes for input_data."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {item["id"]: item.get("value") for item in raw if "id" in item}
    return {}


def convert_option(value: Any, options: List[str]) -> str:
    """
    Handles all option formats Sokosumi sends:
    - String: "startup"
    - List with index: [0]
    - List with string: ["startup"]
    - Int index: 0
    """
    if isinstance(value, str) and value in options:
        return value
    if isinstance(value, list) and len(value) > 0:
        v = value[0]
        if isinstance(v, int) and 0 <= v < len(options):
            return options[v]
        if isinstance(v, str) and v in options:
            return v
    if isinstance(value, int) and 0 <= value < len(options):
        return options[value]
    logger.warning("Invalid option '%s', defaulting to '%s'", value, options[0])
    return options[0]


# ✅ CORRECT: SDK calls with exactly 2 args (identifier_from_purchaser, input_data)
async def process_job(identifier_from_purchaser: str, input_data: dict):
    try:
        logger.info("process_job started — identifier: %s", identifier_from_purchaser)
        logger.info("raw input_data: %s", input_data)

        # Normalize input shape
        data = normalize_input(input_data)
        logger.info("normalized input_data: %s", data)

        # Resolve option fields — Sokosumi sends [0], [1] etc.
        company_size = convert_option(
            data.get("company_size", "medium"),
            COMPANY_SIZE_OPTIONS
        )
        intent_signal_type = convert_option(
            data.get("intent_signal", "company_growth"),
            INTENT_SIGNAL_OPTIONS
        )

        logger.info("company_size resolved: %s", company_size)
        logger.info("intent_signal resolved: %s", intent_signal_type)

        prospect_data = {
            "role": data.get("prospect_role", ""),
            "companyContext": {
                "name": data.get("company_name", ""),
                "industry": data.get("company_industry", "Technology"),
                "size": company_size
            },
            "contactDetails": {
                "name": data.get("prospect_name", ""),
                "email": data.get("prospect_email", "")
            }
        }

        intent_signals = [
            {
                "type": intent_signal_type,
                "description": data.get("intent_description", "Recent company activity"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "relevanceScore": 0.8,
                "source": "User Input"
            }
        ]

        outreach_request = {
            "prospectData": prospect_data,
            "intentSignals": intent_signals
        }

        logger.info("Calling outreach service at %s", OUTREACH_SERVICE_URL)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OUTREACH_SERVICE_URL}/agent/outreach",
                json=outreach_request,
                timeout=aiohttp.ClientTimeout(total=OUTREACH_TIMEOUT)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Outreach service error {response.status}: {error_text}")
                result = await response.json()

        logger.info("Outreach service response: %s", result)

        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error from outreach service"))

        output = result.get("data", {})

        # ✅ Return plain dict — NOT json.dumps()
        return {
            "intentConfidence": output.get("intentConfidence"),
            "reasoningSummary": output.get("reasoningSummary"),
            "recommendedMessage": output.get("recommendedMessage"),
            "alternativeMessages": output.get("alternativeMessages", []),
            "suggestedFollowUpTiming": output.get("suggestedFollowUpTiming"),
            "processingMetadata": output.get("processingMetadata", {})
        }

    except Exception as e:
        logger.error("Job failed: %s", e, exc_info=True)
        raise
