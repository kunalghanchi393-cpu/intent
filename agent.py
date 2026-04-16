#!/usr/bin/env python3
"""
agent.py — Core business logic for the Intent-Driven Cold Outreach Agent.
Called by Masumi SDK after payment is confirmed.
"""

import os
import logging
from typing import Any, List

from researcher import research_company, ResearchResult
from email_generator import generate_email
from formatter import format_result

logger = logging.getLogger(__name__)

COMPANY_SIZE_OPTIONS = ["startup", "small", "medium", "large", "enterprise"]
INTENT_SIGNAL_OPTIONS = [
    "job_change",
    "funding_event",
    "technology_adoption",
    "company_growth",
    "industry_trend",
]


def normalize_input(raw: Any) -> dict:
    """Handle both list and dict input shapes from Masumi/Sokosumi."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {item["id"]: item.get("value") for item in raw if "id" in item}
    return {}


def convert_option(value: Any, options: List[str]) -> str:
    """Convert [0], [1] index format, plain string, or int to option value."""
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
    logger.warning("Could not convert option value '%s', using default '%s'", value, options[0])
    return options[0]


def sanitize_input(text: Any, max_length: int = 500) -> str:
    """Sanitize user input to prevent prompt injection."""
    if not isinstance(text, str):
        return ""
    dangerous = ['"""', "'''", "```", "<|", "|>", "[INST]", "[/INST]", "<<SYS>>"]
    for d in dangerous:
        text = text.replace(d, "")
    return text.strip()[:max_length]


async def process_job(identifier_from_purchaser: str, input_data: dict):
    """
    Main job handler. Called by Masumi SDK after payment confirmed.
    MUST return plain dict. MUST NOT return json.dumps() string.
    """
    try:
        logger.info("Job started — id: %s", identifier_from_purchaser)

        # Step 1: Normalize input
        data = normalize_input(input_data)
        logger.info("Input normalized successfully")

        # Step 2: Extract and sanitize fields
        prospect_name      = sanitize_input(data.get("prospect_name", ""))
        prospect_email     = data.get("prospect_email", "")  # used internally only — never logged or returned
        prospect_role      = sanitize_input(data.get("prospect_role", ""))
        company_name       = sanitize_input(data.get("company_name", ""))
        company_industry   = sanitize_input(data.get("company_industry", "Technology"))
        intent_description = sanitize_input(data.get("intent_description", "Recent activity"), max_length=300)

        company_size  = convert_option(data.get("company_size", "medium"), COMPANY_SIZE_OPTIONS)
        intent_signal = convert_option(data.get("intent_signal", "company_growth"), INTENT_SIGNAL_OPTIONS)

        logger.info("Processing: company=%s intent=%s size=%s", company_name, intent_signal, company_size)

        # Step 3: Research — failure is non-fatal, returns fallback ResearchResult
        logger.info("Starting research phase...")
        research = await research_company(
            company_name=company_name,
            company_industry=company_industry,
            intent_signal=intent_signal,
            intent_description=intent_description,
            prospect_role=prospect_role,
        )
        logger.info(
            "Research complete — successful: %s findings: %d",
            research.research_successful,
            len(research.key_findings),
        )

        # Step 4: Generate email — failure IS fatal, raises so Masumi marks job failed
        logger.info("Starting email generation...")
        email = await generate_email(
            research=research,
            prospect_name=prospect_name,
            prospect_email=prospect_email,
            prospect_role=prospect_role,
            company_name=company_name,
            company_industry=company_industry,
            company_size=company_size,
            intent_signal=intent_signal,
            intent_description=intent_description,
        )
        logger.info("Email generated — subject: %s words: %d", email.subject, email.word_count)

        # Step 5: Format and return
        result = format_result(
            research=research,
            email=email,
            prospect_name=prospect_name,
            prospect_email=prospect_email,
            prospect_role=prospect_role,
            company_name=company_name,
            intent_signal=intent_signal,
        )

        logger.info("Job completed successfully — id: %s", identifier_from_purchaser)
        return result  # plain dict — NOT json.dumps()

    except Exception as e:
        logger.error("Job failed — id: %s error: %s", identifier_from_purchaser, str(e), exc_info=True)
        raise
