"""
Quick end-to-end smoke test for process_job.
Run with: python quick_test.py

Requires OPENAI_API_KEY and TAVILY_API_KEY set in .env or environment.
"""
import asyncio
import json
from dotenv import load_dotenv
load_dotenv()  # must happen before agent import so env vars are set

from agent import process_job

LIVE_INPUT = {
    "prospect_name": "Alex",
    "prospect_email": "alex@stripe.com",
    "prospect_role": "VP of Engineering",
    "company_name": "Stripe",
    "company_industry": "Fintech",
    "company_size": "enterprise",
    "intent_signal": "funding_event",
    "intent_description": "Series D $600M raise",
}


async def test_live():
    print("\n=== LIVE SMOKE TEST ===")
    result = await process_job("test-identifier-001", LIVE_INPUT)

    # Verify structure
    assert isinstance(result, dict), "Result must be a dict"
    assert result["status"] == "success", f"Expected status=success, got {result['status']}"
    assert "email" in result, "Missing 'email' key"
    assert "research" in result, "Missing 'research' key"
    assert "quality_metrics" in result, "Missing 'quality_metrics' key"
    assert "prospect" in result, "Missing 'prospect' key"
    assert "generated_at" in result, "Missing 'generated_at' key"

    # Verify PII is excluded
    assert "prospect_email" not in result["prospect"], "PII leak: prospect_email in output"
    assert "alex@stripe.com" not in json.dumps(result), "PII leak: email address in output"

    # Verify email content
    assert result["email"]["subject"], "Empty subject"
    assert result["email"]["body"], "Empty body"
    assert result["email"]["word_count"] > 0, "Word count should be > 0"
    assert result["email"]["word_count"] <= 200, f"Email too long: {result['email']['word_count']} words"

    print(f"Status: {result['status']}")
    print(f"Research successful: {result['research']['successful']}")
    print(f"Findings: {len(result['research']['findings'])}")
    print(f"Subject: {result['email']['subject']}")
    print(f"Word count: {result['email']['word_count']}")
    print(f"Confidence: {result['quality_metrics']['confidence_score']}")
    print(f"Personalization: {result['quality_metrics']['personalization_score']}")
    print("\n--- Full Output ---")
    print(json.dumps(result, indent=2))
    print("\nPASS ✓")


async def main():
    await test_live()
    print("\nSmoke test passed.")


asyncio.run(main())
