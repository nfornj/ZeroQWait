#!/usr/bin/env python3
"""
Minimal seed script for Twenty CRM — creates basic test data with only required fields.
Usage: python seed_crm_minimal.py --api-key <key>
"""

import asyncio
import httpx
import random
import os
import sys
from datetime import datetime

API_KEY = os.getenv("TWENTY_API_KEY", "")
GRAPHQL_URL = os.getenv("TWENTY_GRAPHQL_URL", "http://localhost:3001/graphql")

COMPANY_NAMES = [
    "TechCorp Solutions", "Blue Wave Analytics", "Green Leaf Consulting",
    "Swift Digital", "Harmony Systems", "Atlas Innovations",
    "Zenith Enterprises", "Prime Ventures", "Quantum Labs",
    "Nexus Group", "Nova Creative", "Summit Partners",
]

FIRST_NAMES = ["John", "Jane", "Michael", "Sarah", "David", "Emma", "James", "olivia",
               "Robert", "Sophia", "William", "Isabella", "Richard", "Mia"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
              "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez"]

OPPORTUNITY_NAMES = [
    "Website Redesign", "Marketing Campaign", "Annual Contract",
    "Consulting Engagement", "System Migration", "Training Program",
]

NOTES = [
    "Great meeting with the team. They are very interested.",
    "Discussed pricing and timeline. Client prefers phased approach.",
    "Budget approved. Ready to move forward.",
    "Waiting on legal review of contract.",
    "Client satisfied with initial demo. Scheduling follow-up.",
]


async def _gql(client: httpx.AsyncClient, query: str, variables: dict = None) -> dict:
    """Execute GraphQL query."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    resp = await client.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"GraphQL error: {data['errors']}")
    return data.get("data", {})


async def create_company(client: httpx.AsyncClient, name: str) -> str:
    """Create a company."""
    mutation = """
    mutation CreateCompany($name: String!) {
      createCompany(data: {name: $name}) {
        id
      }
    }
    """
    result = await _gql(client, mutation, {"name": name})
    return result.get("createCompany", {}).get("id", "")


async def create_person(client: httpx.AsyncClient, first: str, last: str, company_id: str = None) -> str:
    """Create a person."""
    mutation = """
    mutation CreatePerson($firstName: String!, $lastName: String!) {
      createPerson(data: {name: {firstName: $firstName, lastName: $lastName}}) {
        id
      }
    }
    """
    result = await _gql(client, mutation, {"firstName": first, "lastName": last})
    return result.get("createPerson", {}).get("id", "")


async def create_opportunity(client: httpx.AsyncClient, name: str, company_id: str = None) -> str:
    """Create an opportunity."""
    mutation = """
    mutation CreateOpportunity($name: String!) {
      createOpportunity(data: {name: $name}) {
        id
      }
    }
    """
    result = await _gql(client, mutation, {"name": name})
    return result.get("createOpportunity", {}).get("id", "")


async def main(num_companies: int = 10):
    """Seed CRM with test data."""
    if not API_KEY:
        print("ERROR: TWENTY_API_KEY not set")
        sys.exit(1)

    print(f"Twenty CRM Minimal Seed Script")
    print(f"  URL: {GRAPHQL_URL}")
    print(f"  Companies: {num_companies}")
    print()

    stats = {"companies": 0, "people": 0, "opportunities": 0, "errors": 0}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create companies
        print(f"Creating {num_companies} companies...")
        company_ids = []
        for i in range(num_companies):
            try:
                name = COMPANY_NAMES[i % len(COMPANY_NAMES)] + f" #{i+1}"
                cid = await create_company(client, name)
                if cid:
                    company_ids.append(cid)
                    stats["companies"] += 1
                    print(f"  ✓ {name}")
                else:
                    stats["errors"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"  ✗ Company {i}: {e}")

        # Create people
        print(f"\nCreating 3 people per company...")
        for cid in company_ids:
            for _ in range(3):
                try:
                    first = random.choice(FIRST_NAMES)
                    last = random.choice(LAST_NAMES)
                    pid = await create_person(client, first, last, cid)
                    if pid:
                        stats["people"] += 1
                except Exception as e:
                    stats["errors"] += 1

        # Create opportunities
        print(f"\nCreating 2 opportunities per company...")
        for cid in company_ids:
            for _ in range(2):
                try:
                    name = random.choice(OPPORTUNITY_NAMES)
                    oid = await create_opportunity(client, name, cid)
                    if oid:
                        stats["opportunities"] += 1
                except Exception as e:
                    stats["errors"] += 1

    print()
    print(f"=== RESULTS ===")
    print(f"  Companies: {stats['companies']}")
    print(f"  People: {stats['people']}")
    print(f"  Opportunities: {stats['opportunities']}")
    print(f"  Errors: {stats['errors']}")
    print()
    print("✓ Seed complete! Test data is now available in Twenty CRM.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed Twenty CRM with minimal test data")
    parser.add_argument("--api-key", default=API_KEY, help="Twenty API key")
    parser.add_argument("--url", default=GRAPHQL_URL, help="Twenty GraphQL URL")
    parser.add_argument("--companies", type=int, default=10, help="Number of companies to create")
    args = parser.parse_args()

    API_KEY = args.api_key
    GRAPHQL_URL = args.url

    asyncio.run(main(args.companies))
