#!/usr/bin/env python3
"""
Intent-Driven Cold Outreach Agent - Masumi SDK Integration
Business logic only.
Masumi SDK handles protocol, payments, blockchain, lifecycle.
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
OUTREACH_TIMEOUT = int(os.getenv("OUTREACH_TIMEOUT_SECONDS", "30"))

COMPANY_SIZE_OPTIONS = ["startup", "small", "medium", "large", "enterprise"]
INTENT_SIGNAL_OPTIONS = [
    "job_change",
    "funding_event",
    "technology_adoption",
    "company_growth",
    "industry_trend",
]


def normalize_input_data(raw: Any) -> dict:
    """
    Masumi may send input_data as either:
      - A list: [{"id": "prospect_name", "value": "John"}]
      - A dict: {"prospect_name": "John"}
    Normalizes both into a flat dict.
    """
    if isinstance(raw, list):
        return {item["id"]: item.get("value") for item in raw if "id" in item}
    if isinstance(raw, dict):
        return raw
    logger.warning("Unexpected input_data type: %s, defaulting to empty dict", type(raw))
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
    logger.warning("Invalid option value '%s', defaulting to '%s'", value, options[0])
    return options[0]


def _fallback_response(error_type: str, error_message: str, identifier: str) -> dict:
    """Return a valid structured fallback dict — never raises."""
    return {
        "intentConfidence": 0.0,
        "reasoningSummary": "Outreach service unavailable. Manual review required for this prospect.",
        "recommendedMessage": "Unable to generate message at this time. Please retry or review manually.",
        "alternativeMessages": [],
        "suggestedFollowUpTiming": "72h",
        "processingMetadata": {
            "status": "fallback",
            "error": f"{error_type}: {error_message}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputIdentifier": identifier,
        },
    }


def _format_message(text: str) -> str:
    """Ensure paragraph spacing and strip markdown symbols."""
    if not isinstance(text, str):
        return ""
    text = text.replace("**", "").replace("##", "").replace("# ", "")
    text = "\n\n".join(p.strip() for p in text.split("\n\n") if p.strip())
    return text


async def _wake_outreach_service(session: aiohttp.ClientSession, base_url: str) -> None:
    """
    Ping the outreach service health endpoint to wake it from Railway sleep.
    Silently ignores any errors — this is best-effort only.
    """
    try:
        health_url = f"{base_url.rstrip('/')}/health"
        async with session.get(
            health_url,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            logger.debug("Outreach service wake ping | status=%d", resp.status)
    except Exception as exc:
        logger.debug("Wake ping failed (non-critical): %s", exc)


async def process_job(identifier_from_purchaser: str, input_data: Any):
    """
    Masumi SDK calls this as start_handler(identifier_from_purchaser, input_data).
    Always returns a valid structured dict — never raises.
    """
    identifier = "<unknown>"

    try:
        identifier = identifier_from_purchaser or "<unknown>"
        raw_input_data = input_data if input_data is not None else {}

        # Normalize input regardless of shape Masumi sends
        input_data = normalize_input_data(raw_input_data)

        # Debug: after input normalization
        logger.debug(
            "Input normalized | identifier=%s | keys=%s",
            identifier,
            list(input_data.keys()),
        )

        company_size = convert_option_value(
            input_data.get("company_size", "medium"),
            COMPANY_SIZE_OPTIONS,
        )
        intent_signal_type = convert_option_value(
            input_data.get("intent_signal", "company_growth"),
            INTENT_SIGNAL_OPTIONS,
        )

        prospect_data = {
            "role": input_data.get("prospect_role", ""),
            "companyContext": {
                "name": input_data.get("company_name", ""),
                "industry": input_data.get("company_industry", "Technology"),
                "size": company_size,
            },
            "contactDetails": {
                "name": input_data.get("prospect_name", ""),
                "email": input_data.get("prospect_email", ""),
            },
        }

        intent_description = input_data.get("intent_description", "Recent company activity")
        now_iso = datetime.now(timezone.utc).isoformat()

        intent_signals = [
            {
                "type": intent_signal_type,
                "description": intent_description,
                "timestamp": now_iso,
                "relevanceScore": 0.8,
                "source": "User Input",
            },
            {
                "type": "company_growth",
                "description": f"Company size: {company_size}",
                "timestamp": now_iso,
                "relevanceScore": 0.6,
                "source": "Company Context",
            },
        ]

        outreach_request = {
            "prospectData": prospect_data,
            "intentSignals": intent_signals,
        }

        base_url = OUTREACH_SERVICE_URL.rstrip("/")
        url = f"{base_url}/agent/outreach"
        body_preview = json.dumps(outreach_request)[:500]

        # Debug: before HTTP call
        logger.debug("HTTP POST | url=%s | body_preview=%s", url, body_preview)

        timeout = aiohttp.ClientTimeout(total=OUTREACH_TIMEOUT)

        try:
            async with aiohttp.ClientSession() as session:
                # Wake the outreach service in case it's sleeping on Railway free tier
                await _wake_outreach_service(session, base_url)

                async with session.post(url, json=outreach_request, timeout=timeout) as response:
                    status = response.status

                    # Debug: after HTTP call
                    logger.debug("HTTP response | status=%d", status)

                    if status != 200:
                        body_snippet = (await response.text())[:300]
                        logger.error(
                            "Non-200 response | error_type=HTTPError | identifier=%s | status=%d | body=%s",
                            identifier, status, body_snippet,
                        )
                        return _fallback_response("HTTPError", f"status={status} body={body_snippet}", identifier)

                    try:
                        result = await response.json()
                    except json.JSONDecodeError as exc:
                        logger.error(
                            "JSON parse failed | error_type=JSONDecodeError | identifier=%s | message=%s",
                            identifier, str(exc),
                        )
                        return _fallback_response("JSONDecodeError", str(exc), identifier)

        except asyncio.TimeoutError as exc:
            logger.error(
                "Request timed out | error_type=TimeoutError | identifier=%s | message=%s",
                identifier, str(exc),
            )
            return _fallback_response("TimeoutError", str(exc), identifier)

        except aiohttp.ClientError as exc:
            logger.error(
                "Connection error | error_type=%s | identifier=%s | message=%s",
                type(exc).__name__, identifier, str(exc),
            )
            return _fallback_response(type(exc).__name__, str(exc), identifier)

        if not result.get("success"):
            err_msg = result.get("error", "Unknown processing error")
            logger.error(
                "Service returned failure | error_type=ServiceError | identifier=%s | message=%s",
                identifier, err_msg,
            )
            return _fallback_response("ServiceError", err_msg, identifier)

        data = result.get("data", {})

        recommended = _format_message(data.get("recommendedMessage", ""))
        alt_messages = data.get("alternativeMessages", [])
        if not isinstance(alt_messages, list):
            alt_messages = []

        output = {
            "intentConfidence": data.get("intentConfidence", 0.0),
            "reasoningSummary": data.get("reasoningSummary", ""),
            "recommendedMessage": recommended,
            "alternativeMessages": alt_messages,
            "suggestedFollowUpTiming": data.get("suggestedFollowUpTiming", ""),
            "processingMetadata": data.get("processingMetadata", {}),
        }

        # Debug: before return
        logger.debug(
            "Returning success | keys=%s | intentConfidence=%s",
            list(output.keys()),
            output["intentConfidence"],
        )

        return output

    except Exception as exc:
        logger.error(
            "Unexpected error | error_type=%s | identifier=%s | message=%s",
            type(exc).__name__, identifier, str(exc),
        )
        return _fallback_response(type(exc).__name__, str(exc), identifier)
