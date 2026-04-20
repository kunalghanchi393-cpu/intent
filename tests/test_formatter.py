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
    assert "quality" in result
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


def test_format_result_scores_as_percentages():
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Engineering",
        company_name="Acme Corp",
        intent_signal="funding_event",
    )

    quality = result["quality"]
    assert quality["confidence"] == "88%"
    assert quality["personalization"] == "91%"


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

    assert "unavailable" in result["research"]["status"].lower()
    assert result["research"]["key_findings"] == ["Research unavailable — email based on provided context"]
    assert result["quality"]["research_backed"] == "No"


def test_format_result_research_successful_status():
    result = format_result(
        research=_make_research(successful=True),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="company_growth",
    )

    assert "successful" in result["research"]["status"].lower()
    assert "1 finding" in result["research"]["status"]


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
    # No milliseconds — should NOT have a dot before Z
    assert "." not in ts


def test_format_result_email_word_count_as_string():
    """Verify word_count is a human-readable string like '95 words'."""
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
    assert result["email"]["word_count"] == "95 words"


def test_format_result_intent_signal_human_readable():
    """Verify the intent_signal is converted to human-readable label."""
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="technology_adoption",
    )

    assert result["prospect"]["intent_signal"] == "Technology Adoption"


def test_format_result_intent_signal_job_change():
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="job_change",
    )

    assert result["prospect"]["intent_signal"] == "Job Change"


def test_format_result_follow_up_as_string():
    """Verify follow_up_in is a human-readable string like '3 days'."""
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="company_growth",
    )

    assert result["quality"]["follow_up_in"] == "3 days"


def test_format_result_full_key_structure():
    """Verify all expected keys are present in the new format."""
    result = format_result(
        research=_make_research(),
        email=_make_email(),
        prospect_name="John",
        prospect_email="john@acme.com",
        prospect_role="VP Sales",
        company_name="Acme",
        intent_signal="company_growth",
    )

    # Top-level keys
    assert set(result.keys()) == {
        "status", "prospect", "research", "email", "quality", "generated_at"
    }

    # Nested keys
    assert set(result["prospect"].keys()) == {"name", "role", "company", "intent_signal"}
    assert set(result["research"].keys()) == {"status", "key_findings", "summary"}
    assert set(result["email"].keys()) == {"subject", "body", "word_count"}
    assert set(result["quality"].keys()) == {
        "confidence", "personalization", "research_backed", "follow_up_in", "reasoning"
    }
