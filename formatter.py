#!/usr/bin/env python3
"""
formatter.py — Format final output for Masumi.
Never includes prospect email, raw API responses, or internal tracebacks.
"""

from datetime import datetime, timezone

from researcher import ResearchResult
from email_generator import EmailResult


def format_result(
    research: ResearchResult,
    email: EmailResult,
    prospect_name: str,
    prospect_email: str,  # accepted but intentionally excluded from output
    prospect_role: str,
    company_name: str,
    intent_signal: str,
) -> dict:
    return {
        "status": "success",
        "prospect": {
            "name": prospect_name,
            "role": prospect_role,
            "company": company_name,
            # prospect_email intentionally omitted — privacy
        },
        "intent_signal": intent_signal,
        "research": {
            "successful": research.research_successful,
            "findings": research.key_findings,
            "summary": research.research_summary,
            "sources_used": len(research.sources),
        },
        "email": {
            "subject": email.subject,
            "body": email.body,
            "word_count": email.word_count,
        },
        "quality_metrics": {
            "confidence_score": round(email.confidence_score, 2),
            "personalization_score": round(email.personalization_score, 2),
            "recommended_follow_up_days": email.follow_up_days,
            "reasoning": email.reasoning,
            "research_backed": research.research_successful,
        },
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }
