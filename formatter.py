#!/usr/bin/env python3
"""
formatter.py — Format final output for Masumi.
Never includes prospect email, raw API responses, or internal tracebacks.
"""

from datetime import datetime, timezone

from researcher import ResearchResult
from email_generator import EmailResult

# Human-readable labels for intent signals
INTENT_LABELS = {
    "job_change": "Job Change",
    "funding_event": "Funding Event",
    "technology_adoption": "Technology Adoption",
    "company_growth": "Company Growth",
    "industry_trend": "Industry Trend",
}


def format_result(
    research: ResearchResult,
    email: EmailResult,
    prospect_name: str,
    prospect_email: str,  # accepted but intentionally excluded from output
    prospect_role: str,
    company_name: str,
    intent_signal: str,
) -> dict:
    # Research status as readable sentence
    if research.research_successful:
        finding_count = len(research.key_findings)
        research_status = f"Research successful — {finding_count} finding{'s' if finding_count != 1 else ''}"
        key_findings = list(research.key_findings)
    else:
        research_status = "Research unavailable — email based on provided context"
        key_findings = ["Research unavailable — email based on provided context"]

    # Confidence and personalization as percentages
    confidence_pct = f"{round(email.confidence_score * 100)}%"
    personalization_pct = f"{round(email.personalization_score * 100)}%"

    # Word count as "N words" string
    word_count_str = f"{email.word_count} words"

    # Follow-up as "N days" string
    follow_up_str = f"{email.follow_up_days} days"

    # Research-backed as Yes/No
    research_backed_str = "Yes" if research.research_successful else "No"

    # Intent signal as human-readable label
    intent_label = INTENT_LABELS.get(intent_signal, intent_signal.replace("_", " ").title())

    # Clean ISO timestamp — no milliseconds
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "status": "success",

        "prospect": {
            "name": prospect_name,
            "role": prospect_role,
            "company": company_name,
            "intent_signal": intent_label,
            # prospect_email intentionally omitted — privacy
        },

        "research": {
            "status": research_status,
            "key_findings": key_findings,
            "summary": research.research_summary,
        },

        "email": {
            "subject": email.subject,
            "body": email.body,
            "word_count": word_count_str,
        },

        "quality": {
            "confidence": confidence_pct,
            "personalization": personalization_pct,
            "research_backed": research_backed_str,
            "follow_up_in": follow_up_str,
            "reasoning": email.reasoning,
        },

        "generated_at": generated_at,
    }
