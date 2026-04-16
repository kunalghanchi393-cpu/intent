#!/usr/bin/env python3
"""
researcher.py — Async web research via Tavily API.
Research failures are non-fatal: always returns a ResearchResult.
"""

import os
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List

from tavily import TavilyClient

logger = logging.getLogger(__name__)

RESEARCH_TIMEOUT = int(os.getenv("RESEARCH_TIMEOUT", "30"))


@dataclass
class ResearchResult:
    company_name: str
    key_findings: List[str]
    intent_evidence: str
    research_summary: str
    sources: List[str]
    research_successful: bool


def _fallback(company_name: str, intent_description: str) -> ResearchResult:
    return ResearchResult(
        company_name=company_name,
        key_findings=[],
        intent_evidence=intent_description,
        research_summary="Research unavailable — using provided context only.",
        sources=[],
        research_successful=False,
    )


def _build_queries(
    company_name: str,
    company_industry: str,
    intent_signal: str,
    intent_description: str,
    prospect_role: str,
) -> List[str]:
    base_queries = [
        f"{company_name} news 2025",
        f"{company_name} {company_industry} recent developments",
    ]
    intent_queries = {
        "job_change": [
            f"{company_name} hiring {prospect_role}",
            f"{company_name} team expansion",
        ],
        "funding_event": [
            f"{company_name} funding raised investment 2024 2025",
        ],
        "technology_adoption": [
            f"{company_name} technology infrastructure new tools",
        ],
        "company_growth": [
            f"{company_name} growth expansion revenue 2025",
        ],
        "industry_trend": [
            f"{company_industry} trends challenges 2025",
        ],
    }
    return base_queries + intent_queries.get(intent_signal, [])


def _extract_findings(results: list, max_findings: int = 5) -> tuple[List[str], List[str]]:
    """Extract deduplicated snippets and source URLs from Tavily results."""
    findings: List[str] = []
    sources: List[str] = []
    seen: set = set()

    for item in results:
        content = item.get("content", "").strip()
        url = item.get("url", "")

        if not content or len(content) < 30:
            continue

        # Deduplicate by first 80 chars
        key = content[:80].lower()
        if key in seen:
            continue
        seen.add(key)

        findings.append(content[:300])
        if url and url not in sources:
            sources.append(url)

        if len(findings) >= max_findings:
            break

    return findings, sources


def _pick_intent_evidence(findings: List[str], intent_description: str) -> str:
    """Return the most relevant finding, falling back to intent_description."""
    if findings:
        return findings[0]
    return intent_description


def _build_summary(company_name: str, findings: List[str]) -> str:
    if not findings:
        return "Research unavailable — using provided context only."
    combined = " ".join(findings[:2])
    # Truncate to ~300 chars for a clean 2-3 sentence summary
    if len(combined) > 300:
        combined = combined[:297] + "..."
    return f"Research on {company_name}: {combined}"


def _do_tavily_search(client: TavilyClient, query: str) -> dict:
    """Synchronous Tavily search — called via asyncio.to_thread()."""
    return client.search(
        query=query,
        search_depth="advanced",
        max_results=3,
    )


async def research_company(
    company_name: str,
    company_industry: str,
    intent_signal: str,
    intent_description: str,
    prospect_role: str,
) -> ResearchResult:
    """
    Run Tavily searches and return a ResearchResult.
    NEVER raises — all failures return a fallback ResearchResult.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set — skipping research")
        return _fallback(company_name, intent_description)

    masked_key = api_key[:4] + "..."
    logger.info("Starting Tavily research | key=%s | company=%s | intent=%s",
                masked_key, company_name, intent_signal)

    try:
        queries = _build_queries(
            company_name, company_industry, intent_signal, intent_description, prospect_role
        )

        client = TavilyClient(api_key=api_key)
        all_results: list = []

        for query in queries[:3]:  # Cap at 3 queries to stay within free tier
            try:
                # Run sync Tavily call in thread pool — never blocks event loop
                response = await asyncio.wait_for(
                    asyncio.to_thread(_do_tavily_search, client, query),
                    timeout=float(os.getenv("RESEARCH_TIMEOUT", "30")),
                )
                results = response.get("results", [])
                all_results.extend(results)
                logger.debug("Query '%s' returned %d results", query, len(results))
            except asyncio.TimeoutError:
                logger.warning("Tavily query timed out: '%s'", query)
                continue
            except Exception as exc:
                logger.warning("Tavily query failed: '%s' — %s", query, str(exc))
                continue

        if not all_results:
            logger.warning("No Tavily results returned — using fallback")
            return _fallback(company_name, intent_description)

        findings, sources = _extract_findings(all_results)

        if not findings:
            logger.warning("Tavily results had no usable content — using fallback")
            return _fallback(company_name, intent_description)

        intent_evidence = _pick_intent_evidence(findings, intent_description)
        summary = _build_summary(company_name, findings)

        logger.info("Research complete | findings=%d sources=%d", len(findings), len(sources))

        return ResearchResult(
            company_name=company_name,
            key_findings=findings,
            intent_evidence=intent_evidence,
            research_summary=summary,
            sources=sources,
            research_successful=True,
        )

    except Exception as exc:
        logger.error("Research failed unexpectedly: %s", str(exc), exc_info=True)
        return _fallback(company_name, intent_description)
