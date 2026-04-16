#!/usr/bin/env python3
"""
email_generator.py — Async cold email generation.
Primary: OpenAI gpt-4o-mini (OPENAI_API_KEY)
Fallback: Groq llama-3.1-8b-instant (GROQ_API_KEY)
If the primary fails for any reason, automatically retries with the fallback.
"""

import os
import json
import asyncio
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

from researcher import ResearchResult

logger = logging.getLogger(__name__)

OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "60"))

# Provider configs — OpenAI-compatible APIs
PROVIDERS = [
    {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "base_url": None,  # default OpenAI endpoint
        "model": "gpt-4o-mini",
    },
    {
        "name": "Groq",
        "env_key": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
    },
]

BANNED_PHRASES = [
    "i hope this finds you",
    "i hope this email",
    "i wanted to reach out",
    "i came across your",
    "i'd love to",
    "synergies",
    "leverage",
    "game-changer",
    "cutting-edge",
    "touch base",
    "circle back",
    "on your radar",
    "innovative solution",
    "quick question",
    "just checking in",
    "revolutionize",
    "best-in-class",
    "paradigm",
    "disruptive",
    "world-class",
]

SYSTEM_PROMPT = (
    "You are an elite B2B cold email copywriter who has written copy for Gong, "
    "Outreach, and Apollo. You write emails that feel like they came from a "
    "thoughtful human who did real homework — never from a template. "
    "Your emails get 40%+ open rates because the subject lines create genuine "
    "curiosity, and 12%+ reply rates because the body references specific, "
    "verifiable facts about the prospect's company. "
    "You NEVER use filler phrases, corporate jargon, or AI-sounding language. "
    "Respond ONLY with valid JSON — no markdown fences, no explanation, no preamble."
)


@dataclass
class EmailResult:
    subject: str
    body: str
    reasoning: str
    confidence_score: float
    personalization_score: float
    follow_up_days: int
    word_count: int


def _parse_json_response(raw: str) -> dict:
    """Handle both clean JSON and markdown-wrapped JSON."""
    raw = raw.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.split("```")[0]
    return json.loads(raw.strip())


def _build_research_context(
    research: ResearchResult,
    intent_signal: str,
    intent_description: str,
) -> str:
    if research.research_successful and research.key_findings:
        findings_text = "\n".join(f"- {f}" for f in research.key_findings)
        return (
            f"\nREAL COMPANY RESEARCH (reference at least one specific fact):\n"
            f"{findings_text}\n\n"
            f"Most relevant finding: {research.intent_evidence}\n"
        )
    return (
        f"\nCONTEXT PROVIDED BY BUYER:\n"
        f"- Intent signal: {intent_signal}\n"
        f"- Details: {intent_description}\n"
    )


def _build_user_prompt(
    research: ResearchResult,
    prospect_name: str,
    prospect_role: str,
    company_name: str,
    company_industry: str,
    company_size: str,
    intent_signal: str,
    intent_description: str,
) -> str:
    research_context = _build_research_context(research, intent_signal, intent_description)
    banned = ", ".join(f'"{p}"' for p in BANNED_PHRASES)

    return f"""Write a cold outreach email for the following prospect.

PROSPECT DETAILS:
- Name: {prospect_name}
- Role: {prospect_role}
- Company: {company_name}
- Industry: {company_industry}
- Company size: {company_size}
- Intent signal: {intent_signal}
- Intent description: {intent_description}
{research_context}
RULES:
1. Under 150 words total.
2. Subject line under 50 chars — curiosity-driven, no pitch.
3. Reference at least one specific fact from the research.
4. Exactly one low-friction CTA.
5. Do NOT use any of these banned phrases: {banned}
6. Sound like a real human, not a template.

Respond with this exact JSON:
{{
  "subject": "subject line",
  "body": "full email body",
  "reasoning": "one sentence why this angle works",
  "confidence_score": 0.87,
  "personalization_score": 0.91,
  "follow_up_days": 3
}}"""


def _check_banned_phrases(email_result: EmailResult) -> None:
    combined = (email_result.body + " " + email_result.subject).lower()
    for phrase in BANNED_PHRASES:
        if phrase in combined:
            logger.warning("Banned phrase detected in output: '%s'", phrase)


async def _call_provider(provider: dict, user_prompt: str) -> dict:
    """Call a single LLM provider. Raises on any failure."""
    api_key = os.getenv(provider["env_key"], "")
    if not api_key:
        raise RuntimeError(f"{provider['env_key']} is not set")

    kwargs = {"api_key": api_key, "timeout": OPENAI_TIMEOUT}
    if provider["base_url"]:
        kwargs["base_url"] = provider["base_url"]

    client = AsyncOpenAI(**kwargs)

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=provider["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=600,
        ),
        timeout=OPENAI_TIMEOUT,
    )

    raw = response.choices[0].message.content or ""
    return _parse_json_response(raw)


async def generate_email(
    research: ResearchResult,
    prospect_name: str,
    prospect_email: str,  # accepted but never logged or returned
    prospect_role: str,
    company_name: str,
    company_industry: str,
    company_size: str,
    intent_signal: str,
    intent_description: str,
) -> EmailResult:
    """
    Generate email using OpenAI first, Groq as fallback.
    Raises only if ALL providers fail.
    """
    user_prompt = _build_user_prompt(
        research=research,
        prospect_name=prospect_name,
        prospect_role=prospect_role,
        company_name=company_name,
        company_industry=company_industry,
        company_size=company_size,
        intent_signal=intent_signal,
        intent_description=intent_description,
    )

    last_error = None

    for provider in PROVIDERS:
        api_key = os.getenv(provider["env_key"], "")
        if not api_key:
            logger.info("Skipping %s — %s not set", provider["name"], provider["env_key"])
            continue

        logger.info("Trying provider: %s | model: %s", provider["name"], provider["model"])
        try:
            parsed = await _call_provider(provider, user_prompt)

            subject = parsed.get("subject", "")
            body = parsed.get("body", "")
            if not subject or not body:
                raise RuntimeError(f"{provider['name']} returned empty subject or body")

            email_result = EmailResult(
                subject=subject,
                body=body,
                reasoning=parsed.get("reasoning", ""),
                confidence_score=float(parsed.get("confidence_score", 0.0)),
                personalization_score=float(parsed.get("personalization_score", 0.0)),
                follow_up_days=int(parsed.get("follow_up_days", 3)),
                word_count=len(body.split()),
            )

            _check_banned_phrases(email_result)
            logger.info(
                "Email generated via %s | subject='%s' | words=%d",
                provider["name"], email_result.subject, email_result.word_count,
            )
            return email_result

        except asyncio.TimeoutError:
            last_error = f"{provider['name']} timed out after {OPENAI_TIMEOUT}s"
            logger.warning(last_error)
        except json.JSONDecodeError as exc:
            last_error = f"{provider['name']} returned invalid JSON: {exc}"
            logger.warning(last_error)
        except Exception as exc:
            last_error = f"{provider['name']} failed: {exc}"
            logger.warning(last_error)

    raise RuntimeError(
        f"All LLM providers failed. Last error: {last_error}. "
        "Set OPENAI_API_KEY or GROQ_API_KEY in Railway Variables."
    )
