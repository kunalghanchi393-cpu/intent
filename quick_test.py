"""
Quick end-to-end tests for process_job.
Run with: python quick_test.py
"""
import asyncio
import os
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
    print("\n=== TEST 1: Live call ===")
    result = await process_job("test-identifier-001", LIVE_INPUT)
    print(f"Result keys: {list(result.keys())}")
    print(f"intentConfidence: {result.get('intentConfidence')}")
    print(f"status: {result.get('processingMetadata', {}).get('status')}")
    print(f"recommendedMessage (first 200 chars):\n{result.get('recommendedMessage', '')[:200]}")

    assert isinstance(result, dict), "Result must be a dict"
    assert "recommendedMessage" in result, "Missing recommendedMessage"
    assert "processingMetadata" in result, "Missing processingMetadata"
    assert result["processingMetadata"]["status"] != "fallback", (
        f"Got fallback — check OUTREACH_SERVICE_URL. Error: {result['processingMetadata'].get('error')}"
    )
    print("PASS")


async def test_fallback():
    print("\n=== TEST 2: Fallback (dead URL) ===")
    # Override URL to a dead endpoint for this test
    os.environ["OUTREACH_SERVICE_URL"] = "http://localhost:9999/dead"

    # Re-import to pick up new env var — patch module-level constant directly
    import agent
    original_url = agent.OUTREACH_SERVICE_URL
    agent.OUTREACH_SERVICE_URL = "http://localhost:9999/dead"

    try:
        result = await process_job("test-identifier-fallback", LIVE_INPUT)
        print(f"Result keys: {list(result.keys())}")
        print(f"status: {result.get('processingMetadata', {}).get('status')}")
        print(f"error: {result.get('processingMetadata', {}).get('error')}")

        assert isinstance(result, dict), "Result must be a dict"
        assert result["processingMetadata"]["status"] == "fallback", "Expected fallback status"
        assert result["processingMetadata"]["error"], "error field must not be empty"
        assert result["intentConfidence"] == 0.0, "intentConfidence must be 0.0 on fallback"
        assert isinstance(result["alternativeMessages"], list), "alternativeMessages must be a list"
        print("PASS")
    finally:
        agent.OUTREACH_SERVICE_URL = original_url


async def main():
    await test_live()
    await test_fallback()
    print("\nAll tests passed.")


asyncio.run(main())
