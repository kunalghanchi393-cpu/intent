#!/usr/bin/env python3

from dotenv import load_dotenv
load_dotenv()

from masumi import run
from agent import process_job

# 👇 ADD THESE IMPORTS
from fastapi import Request
import logging

logger = logging.getLogger(__name__)


# ---- INPUT SCHEMA ----
INPUT_SCHEMA = {
    "input_data": [
        {"id": "prospect_name", "type": "string", "name": "Prospect Name"},
        {"id": "prospect_email", "type": "string", "name": "Prospect Email"},
        {"id": "prospect_role", "type": "string", "name": "Prospect Role"},
        {"id": "company_name", "type": "string", "name": "Company Name"},
        {"id": "company_industry", "type": "string", "name": "Company Industry"},
        {
            "id": "company_size",
            "type": "options",
            "name": "Company Size",
            "options": ["startup", "small", "medium", "large", "enterprise"]
        },
        {
            "id": "intent_signal",
            "type": "options",
            "name": "Intent Signal Type",
            "options": [
                "job_change",
                "funding_event",
                "technology_adoption",
                "company_growth",
                "industry_trend"
            ]
        },
        {"id": "intent_description", "type": "string", "name": "Intent Description"}
    ]
}


def get_schema():
    return INPUT_SCHEMA


# 👇 DEBUG MIDDLEWARE
async def log_request_middleware(request: Request, call_next):

    body = await request.body()

    logger.info("======= RAW REQUEST RECEIVED =======")
    logger.info(f"PATH: {request.url.path}")
    logger.info(f"METHOD: {request.method}")
    logger.info(f"BODY: {body.decode('utf-8')}")
    logger.info("====================================")

    response = await call_next(request)
    return response


if __name__ == "__main__":

    server = run(
        start_job_handler=process_job,
        input_schema_handler=get_schema
    )

    # attach middleware
    server.app.middleware("http")(log_request_middleware)
