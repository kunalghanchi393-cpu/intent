import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from researcher import (
    research_company,
    ResearchResult,
    _build_queries,
    _extract_findings,
    _fallback,
    clean_snippet,
)


# --- clean_snippet ---

def test_clean_snippet_removes_markdown():
    raw = "## Big Heading\n\nSome **bold** text with\n\nmultiple lines"
    result = clean_snippet(raw)
    assert '#' not in result
    assert '**' not in result
    assert '\n' not in result
    assert len(result) > 0


def test_clean_snippet_truncates_long_text():
    raw = "A" * 300
    result = clean_snippet(raw)
    assert len(result) <= 200


def test_clean_snippet_handles_empty():
    assert clean_snippet("") == ""
    assert clean_snippet(None) == ""


def test_clean_snippet_removes_urls():
    raw = "Check out https://example.com/page for more info about the company."
    result = clean_snippet(raw)
    assert "https://" not in result
    assert "example.com" not in result


def test_clean_snippet_removes_list_markers():
    raw = "- Acme Corp raised ten million dollars in a new funding round recently\n* Acme Corp expanded to Europe this quarter successfully\n3. Acme Corp hired a new VP of Engineering last week"
    result = clean_snippet(raw)
    assert '- ' not in result
    assert '* ' not in result
    assert len(result) > 0


def test_clean_snippet_removes_navigation_prefix():
    raw = "Overview News Stories About Stripe News Stripe raises $6.5B in new funding round from major investors."
    result = clean_snippet(raw)
    assert result.startswith("Overview") is False
    assert "Stripe" in result


def test_clean_snippet_removes_repeated_product_labels():
    raw = "Product Stripe launches UAE Product Stripe acquires TaxJar Product Stripe Issuing in Europe now available."
    result = clean_snippet(raw)
    # Should be much shorter or empty after removing repeated Product patterns
    assert result.count("Product") <= 1


def test_clean_snippet_removes_published_byline():
    raw = "Published: Mar 8, 2026 by Mike Brown In Small Business News Stripe hits $1.9T in total payment volume processed."
    result = clean_snippet(raw)
    assert "Published" not in result
    assert "Mike Brown" not in result


def test_clean_snippet_discards_short_results():
    raw = "Read more"
    result = clean_snippet(raw)
    assert result == ""


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
        {"content": "Acme raised $10M in Series A funding round from top-tier investors.", "url": "https://a.com"},
        {"content": "Acme raised $10M in Series A funding round from top-tier investors.", "url": "https://b.com"},
        {"content": "Acme expanded its operations to Europe this quarter with a major push.", "url": "https://c.com"},
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


def test_extract_findings_cleans_markdown():
    """Verify findings are cleaned of markdown artifacts."""
    results = [
        {
            "content": "## Big News\n\n**Acme** raised $10M in their latest funding round, significantly boosting their valuation and market presence globally.",
            "url": "https://a.com",
        },
    ]
    findings, _ = _extract_findings(results)
    assert len(findings) == 1
    assert '##' not in findings[0]
    assert '**' not in findings[0]


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
