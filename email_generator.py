#!/usr/bin/env python3
"""
email_generator.py — Async cold email generation via OpenAI gpt-4o-mini.
Failures here ARE fatal — they propagate up so Masumi marks the job failed.
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
    "Respond ONLY with valid JSON — no markdown fences, no explanation, no "
    "preamble."
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
    """Handle both clean JSON and markdown-wrapped JSON from OpenAI."""
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
            f"\nREAL COMPANY RESEARCH (you MUST reference at least one of these "
            f"specific facts in the email body — do NOT make up facts):\n"
            f"{findings_text}\n\n"
            f"Most relevant finding to reference: {research.intent_evidence}\n"
        )
    return (
        f"\nCONTEXT PROVIDED BY BUYER (use this as the basis for personalization):\n"
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
You are writing as a senior SDR at a top-tier SaaS company. Your tone is
confident, specific, and human. You sound like a real person who genuinely
researched this prospect — not like a mass email tool.

PROSPECT DETAILS:
- Name: {prospect_name}
- Role: {prospect_role}
- Company: {company_name}
- Industry: {company_industry}
- Company size: {company_size}
- Intent signal: {intent_signal}
- Intent description: {intent_description}
{research_context}
ABSOLUTE RULES (violating any of these is unacceptable):
1. The email MUST be under 150 words total. Brevity is power.
2. Do NOT start the email with "I hope", "I wanted to", "I came across", or
   any greeting beyond "Hi {prospect_name},".
3. The subject line MUST create curiosity — it should NOT state what you want
   or pitch anything. Think of it as a text message a colleague would send.
   Keep it under 50 characters.
4. Reference at least ONE specific fact from the research above. If no research
   is available, reference the intent signal specifically.
5. Do NOT mention AI, automation, chatbots, or any tools by name.
6. Include exactly ONE clear, low-friction CTA (e.g., "Worth a 15-min call
   this week?" — not "I'd love to schedule a demo").
7. Write in short paragraphs (2-3 sentences max each).
8. Do NOT use any of these banned phrases: {banned}
9. The email must sound like it was written by a human in under 2 minutes —
   casual, direct, not over-polished.

Respond with this exact JSON structure:
{{
  "subject": "subject line under 50 chars — curiosity-driven, no pitch",
  "body": "full email body — under 150 words, references specific facts",
  "reasoning": "one sentence explaining why this angle will resonate with this specific prospect",
  "confidence_score": 0.87,
  "personalization_score": 0.91,
  "follow_up_days": 3
}}"""


def _check_banned_phrases(email_result: EmailResult) -> None:
    body_lower = email_result.body.lower()
    subject_lower = email_result.subject.lower()
    combined = body_lower + " " + subject_lower
    for phrase in BANNED_PHRASES:
        if phrase in combined:
            logger.warning("Banned phrase detected in output: '%s'", phrase)


async def generate_email(
    research: ResearchResult,
    prospect_name: str,
    prospect_email: str,  # accepted but never logged or included in output
    prospect_role: str,
    company_name: str,
    company_industry: str,
    company_size: str,
    intent_signal: str,
    intent_description: str,
) -> EmailResult:
    """
    Generate a cold email using OpenAI gpt-4o-mini.
    Raises on failure — callers must handle this as a fatal job error.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — cannot generate email")

    logger.info("Starting email generation | company=%s | intent=%s", company_name, intent_signal)

    client = AsyncOpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT)

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

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=600,
            ),
            timeout=OPENAI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error("OpenAI request timed out after %ds", OPENAI_TIMEOUT)
        raise RuntimeError(f"OpenAI timed out after {OPENAI_TIMEOUT} seconds")
    except Exception as exc:
        logger.error("OpenAI API error: %s", str(exc), exc_info=True)
        raise RuntimeError(f"OpenAI API error: {str(exc)}")

    raw_content = response.choices[0].message.content or ""

    try:
        parsed = _parse_json_response(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse OpenAI JSON response: %s", str(exc))
        raise RuntimeError(f"Invalid JSON from OpenAI: {str(exc)}")

    subject = parsed.get("subject", "")
    body = parsed.get("body", "")

    if not subject or not body:
        raise RuntimeError("OpenAI returned empty subject or body")

    word_count = len(body.split())

    email_result = EmailResult(
        subject=subject,
        body=body,
        reasoning=parsed.get("reasoning", ""),
        confidence_score=float(parsed.get("confidence_score", 0.0)),
        personalization_score=float(parsed.get("personalization_score", 0.0)),
        follow_up_days=int(parsed.get("follow_up_days", 3)),
        word_count=word_count,
    )

    _check_banned_phrases(email_result)

    # Log subject and word count only — never log the full body
    logger.info("Email generated | subject='%s' | words=%d", email_result.subject, email_result.word_count)

    return email_result
