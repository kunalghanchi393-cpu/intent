import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from researcher import (
    research_company,
    ResearchResult,
    _build_queries,
    _extract_findings,
    _fallback,
)


# --- _build_queries ---

def test_build_queries_funding_event():
    queries = _build_queries("Acme", "Fintech", "funding_event", "Raised Series A", "VP Eng")
    assert any("funding" in q.lower() for q in queries)
    assert any("Acme" in q for q in queries)


def test_build_queries_job_change():
    queries = _build_queries("Acme", "SaaS", "job_change", "New CTO hired", "CTO")
    assert any("hiring" in q.lower() or "expansion" in q.lower() for q in queries)


def test_build_queries_unknown_signal_uses_base():
    queries = _build_queries("Acme", "Tech", "unknown_signal", "desc", "role")
    assert len(queries) == 2  # only base queries


# --- _extract_findings ---

def test_extract_findings_deduplicates():
    results = [
        {"content": "Acme raised $10M in Series A funding round.", "url": "https://a.com"},
        {"content": "Acme raised $10M in Series A funding round.", "url": "https://b.com"},
        {"content": "Acme expanded to Europe this quarter.", "url": "https://c.com"},
    ]
    findings, sources = _extract_findings(results)
    assert len(findings) == 2  # duplicate removed


def test_extract_findings_filters_short_content():
    results = [
        {"content": "short", "url": "https://a.com"},
        {"content": "This is a long enough content snippet about the company.", "url": "https://b.com"},
    ]
    findings, sources = _extract_findings(results)
    assert len(findings) == 1


def test_extract_findings_max_cap():
    results = [
        {"content": f"Finding number {i} about the company with enough text here.", "url": f"https://{i}.com"}
        for i in range(10)
    ]
    findings, sources = _extract_findings(results, max_findings=5)
    assert len(findings) == 5


# --- _fallback ---

def test_fallback_returns_correct_structure():
    result = _fallback("Acme", "They raised funding")
    assert isinstance(result, ResearchResult)
    assert result.research_successful is False
    assert result.company_name == "Acme"
    assert result.intent_evidence == "They raised funding"
    assert result.key_findings == []
    assert result.sources == []


# --- research_company (integration with mocked Tavily) ---

@pytest.mark.asyncio
async def test_research_company_no_api_key_returns_fallback():
    with patch.dict("os.environ", {"TAVILY_API_KEY": ""}):
        result = await research_company(
            company_name="Acme",
            company_industry="Tech",
            intent_signal="funding_event",
            intent_description="Raised Series A",
            prospect_role="VP Eng",
        )
    assert result.research_successful is False
    assert result.company_name == "Acme"


@pytest.mark.asyncio
async def test_research_company_tavily_exception_returns_fallback():
    with patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-testkey"}):
        with patch("researcher.TavilyClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.search.side_effect = Exception("Tavily network error")
            mock_client_cls.return_value = mock_client

            result = await research_company(
                company_name="Acme",
                company_industry="Tech",
                intent_signal="funding_event",
                intent_description="Raised Series A",
                prospect_role="VP Eng",
            )

    assert result.research_successful is False


@pytest.mark.asyncio
async def test_research_company_success():
    mock_response = {
        "results": [
            {
                "content": "Acme Corp raised $20M in Series B funding led by Sequoia Capital.",
                "url": "https://techcrunch.com/acme-series-b",
            },
            {
                "content": "Acme Corp is expanding its engineering team following recent investment.",
                "url": "https://acme.com/blog/hiring",
            },
        ]
    }

    with patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-testkey"}):
        with patch("researcher.TavilyClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.search.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await research_company(
                company_name="Acme Corp",
                company_industry="Fintech",
                intent_signal="funding_event",
                intent_description="Raised Series B",
                prospect_role="VP Engineering",
            )

    assert result.research_successful is True
    assert len(result.key_findings) > 0
    assert len(result.sources) > 0
    assert result.company_name == "Acme Corp"


@pytest.mark.asyncio
async def test_research_company_timeout_returns_fallback():
    """Verify that a Tavily timeout is handled gracefully."""
    with patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-testkey"}):
        with patch("researcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = asyncio.TimeoutError()

            result = await research_company(
                company_name="SlowCo",
                company_industry="Tech",
                intent_signal="funding_event",
                intent_description="Raised Series A",
                prospect_role="CTO",
            )

    # asyncio.wait_for raises TimeoutError which is caught per-query.
    # All queries fail → fallback returned.
    assert result.research_successful is False
    assert result.company_name == "SlowCo"


@pytest.mark.asyncio
async def test_research_company_partial_results():
    """If some queries fail but others succeed, we still get findings."""
    call_count = 0

    async def mock_to_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("First query failed")
        return {
            "results": [
                {
                    "content": "Acme just launched a new product line targeting enterprise customers.",
                    "url": "https://example.com/acme-launch",
                }
            ]
        }

    with patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-testkey"}):
        with patch("researcher.TavilyClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            with patch("researcher.asyncio.to_thread", side_effect=mock_to_thread):
                result = await research_company(
                    company_name="Acme",
                    company_industry="Tech",
                    intent_signal="company_growth",
                    intent_description="New product launch",
                    prospect_role="VP Sales",
                )

    assert result.research_successful is True
    assert len(result.key_findings) > 0


import asyncio
