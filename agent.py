#!/usr/bin/env python3
"""
Intent-Driven Cold Outreach Agent - Masumi SDK Integration
"""

import os
import json
import asyncio
import aiohttp
import logging
from typing import Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

OUTREACH_SERVICE_URL = os.getenv("OUTREACH_SERVICE_URL", "http://localhost:3000")
OUTREACH_TIMEOUT = int(os.getenv("OUTREACH_TIMEOUT_SECONDS", "10"))

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


async def process_job(job_request):
    """
    Masumi SDK calls this with a single job_request object.
    job_request.identifier_from_purchaser -> str
    job_request.input_data -> list or dict (normalize it)
    """
    try:
        identifier = job_request.identifier_from_purchaser
        logger.info(f"Processing job: {identifier}")
        
        # TEMP: log raw request shape to Railway logs
        logger.info(f"RAW job_request type: {type(job_request)}")
        logger.info(f"RAW job_request dict: {vars(job_request)}")

        # Normalize input regardless of shape Sokosumi sends
        input_data = normalize_input_data(job_request.input_data)
        logger.info(f"Normalized input_data: {input_data}")

        company_size = convert_option_value(
            input_data.get("company_size", "medium"),
            COMPANY_SIZE_OPTIONS
        )
        intent_signal_type = convert_option_value(
            input_data.get("intent_signal", "company_growth"),
            INTENT_SIGNAL_OPTIONS
        )

        logger.info("company_size resolved: %s", company_size)
        logger.info("intent_signal resolved: %s", intent_signal_type)

        prospect_data = {
            "role": data.get("prospect_role", ""),
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

        intent_description = input_data.get("intent_description", "Recent company activity")

        intent_signals = [
            {
                "type": intent_signal_type,
                "description": intent_description,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "relevanceScore": 0.8,
                "source": "User Input",
            },
            {
                "type": "company_growth",
                "description": f"Company size: {company_size}",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "relevanceScore": 0.6,
                "source": "Company Context"
            }
        ]

        outreach_request = {
            "prospectData": prospect_data,
            "intentSignals": intent_signals,
        }

        logger.info("Calling outreach service at %s", OUTREACH_SERVICE_URL)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OUTREACH_SERVICE_URL}/agent/outreach",
                json=outreach_request,
                timeout=aiohttp.ClientTimeout(total=OUTREACH_TIMEOUT)
            ) as response:
                if response.status != 200:
                    error_data = await response.text()
                    raise Exception(f"Node service error {response.status}: {error_data}")
                result = await response.json()

        logger.info("Outreach service response: %s", result)

        if not result.get("success"):
            raise Exception(result.get("error", "Unknown processing error"))

        output = result.get("data", {})

        # ✅ Return plain dict — NOT json.dumps()
        return {
            "intentConfidence": data.get("intentConfidence"),
            "reasoningSummary": data.get("reasoningSummary"),
            "recommendedMessage": data.get("recommendedMessage"),
            "alternativeMessages": data.get("alternativeMessages", []),
            "suggestedFollowUpTiming": data.get("suggestedFollowUpTiming"),
            "processingMetadata": data.get("processingMetadata", {})
        }

        # Task 4.4 — before return
        logger.debug(
            "Returning success | keys=%s | intentConfidence=%s",
            list(output.keys()),
            output["intentConfidence"],
        )

        return output

    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)
        raise
