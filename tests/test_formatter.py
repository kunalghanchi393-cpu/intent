import pytest
from unittest.mock import MagicMock
from formatter import format_result


def _make_research(successful=True):
    m = MagicMock()
    m.research_successful = successful
    m.key_findings = ["Acme raised $10M Series A"] if successful else []
    m.research_summary = "Growing fintech startup" if successful else "Research unavailable"
    m.sources = ["https://techcrunch.com"] if successful else []
    return m


def _make_email():
    m = MagicMock()
    m.subject = "Congrats on the raise"
    m.body = "Hi John, saw Acme just closed a round..."
    m.reasoning = "Funding signals budget availability"
    m.confidence_score = 0.876
    m.personalization_score = 0.912
    m.follow_up_days = 3
    m.word_count = 95
    return m


def test_format_result_structure():
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Engineering",
        company_name="Acme Corp",
        intent_signal="funding_event",
    )

    assert result["status"] == "success"
    assert "prospect" in result
    assert "research" in result
    assert "email" in result
    assert "quality_metrics" in result
    assert "generated_at" in result


def test_format_result_no_prospect_email():
    """Prospect email must never appear in output."""
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Engineering",
        company_name="Acme Corp",
        intent_signal="funding_event",
    )

    assert "prospect_email" not in result["prospect"]
    assert "email_address" not in result["prospect"]
    # Ensure the email address string itself doesn't appear anywhere in prospect block
    assert "john@acme.com" not in str(result["prospect"])


def test_format_result_scores_rounded():
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Engineering",
        company_name="Acme Corp",
        intent_signal="funding_event",
    )

    metrics = result["quality_metrics"]
    assert metrics["confidence_score"] == 0.88
    assert metrics["personalization_score"] == 0.91


def test_format_result_research_failed():
    result = format_result(
        research=_make_research(successful=False),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="CTO",
        company_name="Acme",
        intent_signal="job_change",
    )

    assert result["research"]["successful"] is False
    assert result["research"]["findings"] == []
    assert result["research"]["sources_used"] == 0
    assert result["quality_metrics"]["research_backed"] is False


def test_format_result_sources_count():
    research = _make_research(successful=True)
    research.sources = ["https://a.com", "https://b.com", "https://c.com"]

    result = format_result(
        research=research,
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="company_growth",
    )

    assert result["research"]["sources_used"] == 3


def test_format_result_generated_at_format():
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="company_growth",
    )

    ts = result["generated_at"]
    assert ts.endswith("Z")
    assert "T" in ts


def test_format_result_email_word_count_included():
    """Verify word_count is present in the email section."""
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="company_growth",
    )

    assert "word_count" in result["email"]
    assert result["email"]["word_count"] == 95


def test_format_result_intent_signal_passthrough():
    """Verify the intent_signal is passed through correctly."""
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="technology_adoption",
    )

    assert result["intent_signal"] == "technology_adoption"
