import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agent import normalize_input, convert_option, sanitize_input, process_job


# --- normalize_input ---

def test_normalize_input_dict():
    raw = {"prospect_name": "John", "company_name": "Acme"}
    assert normalize_input(raw) == raw


def test_normalize_input_list():
    raw = [{"id": "prospect_name", "value": "John"}, {"id": "company_name", "value": "Acme"}]
    result = normalize_input(raw)
    assert result["prospect_name"] == "John"
    assert result["company_name"] == "Acme"


def test_normalize_input_empty_list():
    assert normalize_input([]) == {}


def test_normalize_input_unknown_type():
    assert normalize_input(None) == {}


# --- convert_option ---

def test_convert_option_index_zero():
    assert convert_option([0], ["startup", "small", "medium"]) == "startup"


def test_convert_option_index_one():
    assert convert_option([1], ["startup", "small", "medium"]) == "small"


def test_convert_option_string():
    assert convert_option("startup", ["startup", "small"]) == "startup"


def test_convert_option_invalid_defaults():
    assert convert_option([99], ["startup", "small"]) == "startup"


def test_convert_option_empty_list_defaults():
    assert convert_option([], ["startup", "small"]) == "startup"


def test_convert_option_int():
    assert convert_option(2, ["startup", "small", "medium"]) == "medium"


# --- sanitize_input ---

def test_sanitize_input_removes_dangerous():
    assert '"""' not in sanitize_input('hello """world"""')
    assert "```" not in sanitize_input("```code```")
    assert "[INST]" not in sanitize_input("[INST]inject[/INST]")


def test_sanitize_input_max_length():
    long_text = "a" * 600
    assert len(sanitize_input(long_text)) == 500


def test_sanitize_input_non_string():
    assert sanitize_input(123) == ""
    assert sanitize_input(None) == ""


def test_sanitize_input_strips_whitespace():
    assert sanitize_input("  hello  ") == "hello"


def test_sanitize_input_custom_max_length():
    assert len(sanitize_input("a" * 600, max_length=100)) == 100


# --- process_job ---

def _make_mock_research(successful=True):
    m = MagicMock()
    m.research_successful = successful
    m.key_findings = ["Company raised $5M Series A"] if successful else []
    m.research_summary = "Growing fintech company" if successful else "Research unavailable"
    m.intent_evidence = "Recent funding round" if successful else "Recent activity"
    m.sources = ["https://techcrunch.com"] if successful else []
    return m


def _make_mock_email():
    m = MagicMock()
    m.subject = "Congrats on the Series A"
    m.body = "Hi John, saw Acme raised funding..."
    m.reasoning = "Funding means budget to spend"
    m.confidence_score = 0.88
    m.personalization_score = 0.92
    m.follow_up_days = 3
    m.word_count = 98
    return m


@pytest.mark.asyncio
async def test_process_job_success():
    mock_research = _make_mock_research(successful=True)
    mock_email = _make_mock_email()

    with patch("agent.research_company", AsyncMock(return_value=mock_research)), \
         patch("agent.generate_email", AsyncMock(return_value=mock_email)):

        result = await process_job(
            identifier_from_purchaser="test-123",
            input_data={
                "prospect_name": "John",
                "prospect_email": "john@acme.com",
                "prospect_role": "VP Engineering",
                "company_name": "Acme Corp",
                "company_industry": "Fintech",
                "company_size": [0],
                "intent_signal": [1],
                "intent_description": "They just raised Series A",
            },
        )

    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert "email" in result
    assert "subject" in result["email"]
    assert "body" in result["email"]
    assert "prospect_email" not in result["prospect"]  # PII must not leak


@pytest.mark.asyncio
async def test_process_job_research_failure_still_completes():
    """Research failing must NOT fail the job."""
    mock_research = _make_mock_research(successful=False)
    mock_email = _make_mock_email()
    mock_email.subject = "Quick thought on Acme"
    mock_email.body = "Hi John..."
    mock_email.confidence_score = 0.70
    mock_email.personalization_score = 0.65
    mock_email.follow_up_days = 4
    mock_email.word_count = 87

    with patch("agent.research_company", AsyncMock(return_value=mock_research)), \
         patch("agent.generate_email", AsyncMock(return_value=mock_email)):

        result = await process_job(
            "test-456",
            {
                "prospect_name": "John",
                "prospect_email": "john@acme.com",
                "prospect_role": "CTO",
                "company_name": "Acme",
                "company_industry": "SaaS",
                "company_size": [0],
                "intent_signal": [0],
                "intent_description": "Job change",
            },
        )

    assert result["status"] == "success"
    assert result["research"]["successful"] is False


@pytest.mark.asyncio
async def test_process_job_openai_failure_raises():
    """Email generation failing SHOULD raise so Masumi marks job failed."""
    mock_research = _make_mock_research(successful=False)

    with patch("agent.research_company", AsyncMock(return_value=mock_research)), \
         patch("agent.generate_email", AsyncMock(side_effect=RuntimeError("OpenAI API error"))):

        with pytest.raises(RuntimeError, match="OpenAI API error"):
            await process_job(
                "test-789",
                {
                    "prospect_name": "John",
                    "prospect_email": "john@acme.com",
                    "prospect_role": "CTO",
                    "company_name": "Acme",
                    "company_industry": "SaaS",
                    "company_size": [0],
                    "intent_signal": [0],
                    "intent_description": "Test",
                },
            )


@pytest.mark.asyncio
async def test_process_job_list_input_normalized():
    """Masumi may send input as a list of {id, value} dicts."""
    mock_research = _make_mock_research(successful=False)
    mock_email = _make_mock_email()

    with patch("agent.research_company", AsyncMock(return_value=mock_research)), \
         patch("agent.generate_email", AsyncMock(return_value=mock_email)):

        result = await process_job(
            "test-list",
            [
                {"id": "prospect_name", "value": "Jane"},
                {"id": "prospect_email", "value": "jane@corp.com"},
                {"id": "prospect_role", "value": "CEO"},
                {"id": "company_name", "value": "Corp Inc"},
                {"id": "company_industry", "value": "Healthcare"},
                {"id": "company_size", "value": [1]},
                {"id": "intent_signal", "value": [2]},
                {"id": "intent_description", "value": "Adopted new EHR system"},
            ],
        )

    assert result["status"] == "success"
    assert result["prospect"]["name"] == "Jane"


@pytest.mark.asyncio
async def test_process_job_output_has_all_required_keys():
    """Verify the full output structure matches what buyers expect."""
    mock_research = _make_mock_research(successful=True)
    mock_email = _make_mock_email()

    with patch("agent.research_company", AsyncMock(return_value=mock_research)), \
         patch("agent.generate_email", AsyncMock(return_value=mock_email)):

        result = await process_job(
            "test-structure",
            {
                "prospect_name": "Alice",
                "prospect_email": "alice@test.com",
                "prospect_role": "Head of Sales",
                "company_name": "TestCo",
                "company_industry": "SaaS",
                "company_size": "medium",
                "intent_signal": "company_growth",
                "intent_description": "Rapid headcount growth",
            },
        )

    # Top-level keys
    assert set(result.keys()) == {
        "status", "prospect", "intent_signal", "research",
        "email", "quality_metrics", "generated_at"
    }

    # Nested keys
    assert set(result["prospect"].keys()) == {"name", "role", "company"}
    assert set(result["research"].keys()) == {"successful", "findings", "summary", "sources_used"}
    assert set(result["email"].keys()) == {"subject", "body", "word_count"}
    assert set(result["quality_metrics"].keys()) == {
        "confidence_score", "personalization_score",
        "recommended_follow_up_days", "reasoning", "research_backed"
    }
    assert result["generated_at"].endswith("Z")


@pytest.mark.asyncio
async def test_process_job_email_never_in_output():
    """Double-check that prospect_email never leaks into any part of the output."""
    mock_research = _make_mock_research(successful=True)
    mock_email = _make_mock_email()

    with patch("agent.research_company", AsyncMock(return_value=mock_research)), \
         patch("agent.generate_email", AsyncMock(return_value=mock_email)):

        result = await process_job(
            "test-pii",
            {
                "prospect_name": "Bob",
                "prospect_email": "bob@secret.com",
                "prospect_role": "CTO",
                "company_name": "SecretCo",
                "company_industry": "Security",
                "company_size": "startup",
                "intent_signal": "funding_event",
                "intent_description": "Seed funding",
            },
        )

    # The email string must not appear ANYWHERE in the serialized output
    import json
    output_str = json.dumps(result)
    assert "bob@secret.com" not in output_str
