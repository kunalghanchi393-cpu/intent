#!/usr/bin/env python3
"""
researcher.py — Async web research via Tavily API.
Research failures are non-fatal: always returns a ResearchResult.
"""

import os
import re
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


def clean_snippet(text: str) -> str:
    """
    Clean raw Tavily snippet into a readable sentence.
    Strips markdown, headers, excess whitespace, URLs.
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove markdown headers (## Heading, # Heading)
    text = re.sub(r'#{1,6}\s+', '', text)

    # Remove markdown bold and italic (**text**, *text*, __text__)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)

    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)

    # Remove markdown list markers (- item, * item, 1. item)
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # Collapse multiple newlines and tabs into single space
    text = re.sub(r'[\n\r\t]+', ' ', text)

    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Remove navigation/menu patterns ("Overview News Stories About X")
    text = re.sub(r'^(Overview|Contents|Stories|About|Home|Menu|Nav)\s+', '', text, flags=re.IGNORECASE)

    # Remove repeated "Product X Product Y Product Z" patterns
    text = re.sub(r'(Product\s+\w+[\w\s]*?){2,}', '', text, flags=re.IGNORECASE)

    # Remove "Published: date by author In category" patterns
    text = re.sub(r'Published:\s+\w+\s+\d+,\s+\d{4}\s+by\s+[\w\s]+In\s+[\w\s]+', '', text, flags=re.IGNORECASE)

    # Remove lines that are just navigation labels (short fragments under 30 chars before any real content)
    lines = text.split('.')
    lines = [l.strip() for l in lines if len(l.strip()) > 30]
    text = '. '.join(lines)
    if text and not text.endswith('.'):
        text = text + '.'

    # Collapse multiple spaces again after removals
    text = re.sub(r' {2,}', ' ', text)
    text = text.strip()

    # Truncate to 200 chars max
    if len(text) > 200:
        text = text[:200]
        # Try to cut at last complete sentence
        last_period = text.rfind('.')
        if last_period > 80:
            text = text[:last_period + 1]
        else:
            # Cut at last word boundary
            last_space = text.rfind(' ')
            if last_space > 80:
                text = text[:last_space] + '...'

    # Discard if too short after all cleaning — it's garbage
    if len(text) < 40:
        return ""

    return text


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

        cleaned = clean_snippet(content[:300])
        # Discard empty or too-short results after cleaning
        if cleaned and len(cleaned) > 40:
            findings.append(cleaned)
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
    summary = f"Research on {company_name}: {combined}"
    return clean_snippet(summary)


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
