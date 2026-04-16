#!/usr/bin/env python3
"""
Seed Twenty CRM with 3 years of realistic test data for all shops.

Populates: People (contacts), Companies, Opportunities (deals/pipeline),
Notes, and Tasks — all with realistic dates spanning 3 years.

Usage:
    python seed_crm_data.py [--url URL] [--api-key KEY] [--dry-run]

Requires:
    TWENTY_GRAPHQL_URL and TWENTY_API_KEY env vars (or pass via CLI).
"""

import argparse
import asyncio
import os
import random
import sys
from datetime import datetime, timedelta

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GRAPHQL_URL = os.getenv("TWENTY_GRAPHQL_URL", "http://localhost:3001/graphql")
API_KEY = os.getenv("TWENTY_API_KEY", "")

YEARS_OF_HISTORY = 3
NOW = datetime.utcnow()
START_DATE = NOW - timedelta(days=365 * YEARS_OF_HISTORY)

# ---------------------------------------------------------------------------
# Realistic seed data pools
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Christopher",
    "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Margaret",
    "Mark", "Sandra", "Donald", "Ashley", "Steven", "Kimberly", "Andrew",
    "Emily", "Paul", "Donna", "Joshua", "Michelle", "Kevin", "Carol",
    "Brian", "Amanda", "George", "Dorothy", "Timothy", "Melissa", "Ronald",
    "Deborah", "Jason", "Stephanie", "Edward", "Rebecca", "Ryan", "Sharon",
    "Priya", "Arjun", "Wei", "Yuki", "Carlos", "Fatima", "Ahmed", "Olga",
    "Sofia", "Liam", "Noah", "Olivia", "Emma", "Ava", "Sophia", "Isabella",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Patel", "Sharma", "Kim", "Tanaka", "Chen", "Wang", "Zhang", "Singh",
    "Ivanov", "Mueller", "Rossi", "Larsen", "Johansson", "O'Brien",
]

COMPANY_NAMES = [
    "Bright Solutions LLC", "Summit Partners", "Nexus Consulting",
    "ClearPath Technologies", "Horizon Ventures", "Pinnacle Group",
    "BlueWave Digital", "GreenLeaf Services", "RedRock Industries",
    "SilverLine Corp", "GoldenGate Media", "IronClad Security",
    "SwiftCurrent Labs", "NorthStar Analytics", "Evergreen Capital",
    "Cobalt Software", "Ember Health", "Frostbyte Computing",
    "Atlas Global", "Zenith Partners", "Quantum Leap Inc",
    "Velocity Systems", "Apex Manufacturing", "TrueNorth Design",
    "Lighthouse Creative", "Bridgepoint Advisory", "Sapphire Strategies",
    "Crimson Dynamics", "Marble Arch Consulting", "Willow Creek Co",
    "Alpine Outdoors", "Sunset Hospitality", "Metro Dental Group",
    "Urban Barber Collective", "Classic Cuts Inc", "Premier Auto Care",
    "Elite Salon Group", "Quick Fix Plumbing", "Sparkle Clean Co",
    "FreshBrew Coffee", "Happy Paws Veterinary", "TechRepair Hub",
]

COMPANY_DOMAINS = [
    "brightsolutions.com", "summitpartners.io", "nexusconsulting.com",
    "clearpath.tech", "horizonventures.co", "pinnaclegroup.com",
    "bluewavedigital.com", "greenleafservices.com", "redrockindustries.com",
    "silverlinecorp.com", "goldengatemedia.com", "ironcladdev.com",
    "swiftcurrent.io", "northstaranalytics.com", "evergreencap.com",
    "cobaltsoftware.dev", "emberhealth.com", "frostbyte.io",
    "atlasglobal.com", "zenithpartners.co", "quantumleapinc.com",
    "velocitysystems.io", "apexmfg.com", "truenorthdesign.co",
    "lighthousecreative.com", "bridgepoint.co", "sapphirestrategies.com",
    "crimsondynamics.io", "marblearch.co", "willowcreek.com",
    "alpineoutdoors.com", "sunsethospitality.com", "metrodental.com",
    "urbanbarber.com", "classiccuts.com", "premierautocare.com",
    "elitesalon.com", "quickfixplumbing.com", "sparkleclean.com",
    "freshbrewcoffee.com", "happypawsvet.com", "techrepairhub.com",
]

CITIES = [
    "Toronto", "New York", "Los Angeles", "Chicago", "Houston",
    "Phoenix", "San Francisco", "Vancouver", "Montreal", "Calgary",
    "Miami", "Seattle", "Boston", "Denver", "Austin",
    "San Diego", "Dallas", "Atlanta", "Portland", "Minneapolis",
]

OPPORTUNITY_NAMES = [
    "Website Redesign", "Annual Maintenance Contract", "Marketing Campaign",
    "POS System Upgrade", "Loyalty Program Setup", "Holiday Promotion",
    "Staff Training Package", "Social Media Management", "Grand Opening Event",
    "Inventory Management System", "Customer Feedback Platform",
    "Mobile App Development", "SEO Optimization", "Interior Renovation",
    "Equipment Lease Renewal", "Franchise Expansion", "Gift Card Program",
    "Partnership Deal", "Bulk Product Order", "Subscription Box Launch",
    "Email Marketing Setup", "Analytics Dashboard", "Cloud Migration",
    "Branding Package", "VIP Membership Program",
]

STAGES = ["LEAD", "QUALIFIED", "MEETING", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
STAGE_WEIGHTS = [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.10]

TASK_STATUSES = ["TODO", "IN_PROGRESS", "DONE"]
TASK_TITLES = [
    "Follow up on proposal", "Schedule discovery call", "Send pricing sheet",
    "Review contract", "Prepare demo", "Update CRM records",
    "Send thank-you email", "Schedule next meeting", "Research competitor",
    "Draft partnership agreement", "Create case study",
    "Update contact information", "Send monthly newsletter",
    "Prepare quarterly report", "Review pending invoices",
    "Onboard new client", "Set up automated emails",
    "Audit customer feedback", "Plan next quarter strategy",
    "Renew service agreement",
]

NOTE_TITLES = [
    "Initial Discovery Call", "Meeting Notes", "Follow-up Summary",
    "Pricing Discussion", "Service Requirements", "Client Feedback",
    "Quarterly Review", "Project Update", "Budget Discussion",
    "Strategy Session", "Competitor Analysis", "Market Research",
    "Customer Success Check-in", "Onboarding Progress",
    "Contract Negotiation Notes", "Product Demo Feedback",
]

NOTE_BODIES = [
    "Client expressed interest in our premium plan. They currently use a competitor but are unhappy with the service quality.",
    "Discussed timeline for the project. Client wants to launch within 3 months. Budget is flexible but prefers phased approach.",
    "Great meeting — they are ready to move forward. Need to send proposal by end of week.",
    "Client is comparing us with two other vendors. Key differentiator: our AI-powered features.",
    "Follow-up call went well. They want a custom demo with their actual data next week.",
    "Budget approved internally. Waiting on legal review of our standard contract.",
    "Client shared positive feedback from their team. They want to expand to 3 more locations.",
    "Discussed Q3 performance metrics. Revenue up 15% since implementing our solution.",
    "Client requested additional training sessions for new staff members.",
    "Reviewed service agreement renewal terms. Client wants multi-year discount.",
    "Noted that the client is experiencing growth and may need to upgrade tier.",
    "Phone call: client inquired about adding new services to their current plan.",
    "Email exchange: confirmed next steps and deliverables for the upcoming project phase.",
    "On-site visit: observed their current workflow and identified areas for improvement.",
    "Strategic planning session — discussed goals for next fiscal year.",
    "Touch-base call — everything is running smoothly, no issues reported.",
]


def _random_date(min_date: datetime = START_DATE, max_date: datetime = NOW) -> str:
    """Return a random ISO date string between min_date and max_date."""
    delta = max_date - min_date
    random_days = random.randint(0, max(delta.days, 1))
    dt = min_date + timedelta(days=random_days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _random_email(first: str, last: str) -> str:
    domain = random.choice(["gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "protonmail.com"])
    suffix = random.randint(1, 999)
    return f"{first.lower()}.{last.lower()}{suffix}@{domain}"


def _random_phone() -> str:
    return f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"


def _random_amount() -> int:
    """Return amountMicros (dollars * 1_000_000)."""
    dollars = random.choice([500, 1000, 1500, 2000, 2500, 3000, 5000, 7500, 10000, 15000, 25000, 50000])
    return dollars * 1_000_000


# ---------------------------------------------------------------------------
# GraphQL mutations
# ---------------------------------------------------------------------------

async def _gql(client: httpx.AsyncClient, query: str, variables: dict = {}) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    resp = await client.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise ValueError(f"GraphQL error: {data['errors']}")
    return data.get("data", {})


async def create_company(client: httpx.AsyncClient, idx: int) -> str:
    name = COMPANY_NAMES[idx % len(COMPANY_NAMES)]
    domain = COMPANY_DOMAINS[idx % len(COMPANY_DOMAINS)]
    city = random.choice(CITIES)
    employees = random.randint(1, 200)
    arr = random.choice([0, 5000, 10000, 25000, 50000, 100000, 250000]) * 1_000_000

    mutation = """
    mutation CreateCompany($input: CompanyCreateInput!) {
      createCompany(data: $input) { id name }
    }
    """
    result = await _gql(client, mutation, {
        "input": {
            "name": name,
            "domainName": {"primaryLinkUrl": f"https://{domain}"},
            "employees": employees,
            "city": city,
            "annualRecurringRevenue": {"amountMicros": arr, "currencyCode": "USD"},
        }
    })
    return result.get("createCompany", {}).get("id", "")


async def create_person(client: httpx.AsyncClient, company_id: str = None) -> str:
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    email = _random_email(first, last)
    phone = _random_phone()
    city = random.choice(CITIES)

    mutation = """
    mutation CreatePerson($input: PersonCreateInput!) {
      createPerson(data: $input) { id }
    }
    """
    person_input: dict = {
        "name": {"firstName": first, "lastName": last},
        "emails": {"primaryEmail": email},
        "phones": {"primaryPhoneNumber": phone},
        "city": city,
    }
    if company_id:
        person_input["companyId"] = company_id

    result = await _gql(client, mutation, {"input": person_input})
    return result.get("createPerson", {}).get("id", "")


async def create_opportunity(client: httpx.AsyncClient, company_id: str = None, person_id: str = None) -> str:
    name = random.choice(OPPORTUNITY_NAMES) + f" #{random.randint(100, 9999)}"
    stage = random.choices(STAGES, weights=STAGE_WEIGHTS, k=1)[0]
    amount = _random_amount()
    close_date = _random_date(NOW - timedelta(days=365), NOW + timedelta(days=180))

    mutation = """
    mutation CreateOpportunity($input: OpportunityCreateInput!) {
      createOpportunity(data: $input) { id }
    }
    """
    opp_input: dict = {
        "name": name,
        "stage": stage,
        "amount": {"amountMicros": amount, "currencyCode": "USD"},
        "closeDate": close_date,
    }
    if company_id:
        opp_input["companyId"] = company_id
    if person_id:
        opp_input["pointOfContactId"] = person_id

    result = await _gql(client, mutation, {"input": opp_input})
    return result.get("createOpportunity", {}).get("id", "")


async def create_note(client: httpx.AsyncClient, person_id: str = None, company_id: str = None) -> str:
    title = random.choice(NOTE_TITLES)
    body = random.choice(NOTE_BODIES)

    mutation = """
    mutation CreateNote($input: NoteCreateInput!) {
      createNote(data: $input) { id }
    }
    """
    result = await _gql(client, mutation, {"input": {"title": title, "body": body}})
    note_id = result.get("createNote", {}).get("id", "")

    # Link note targets
    if note_id and (person_id or company_id):
        target_mutation = """
        mutation CreateNoteTarget($input: NoteTargetCreateInput!) {
          createNoteTarget(data: $input) { id }
        }
        """
        target_input: dict = {"noteId": note_id}
        if person_id:
            target_input["personId"] = person_id
        elif company_id:
            target_input["companyId"] = company_id
        try:
            await _gql(client, target_mutation, {"input": target_input})
        except Exception:
            pass  # Note target linking may fail if schema differs; note itself is created

    return note_id


async def create_task(client: httpx.AsyncClient, person_id: str = None, company_id: str = None) -> str:
    title = random.choice(TASK_TITLES)
    status = random.choice(TASK_STATUSES)
    due_at = _random_date(NOW - timedelta(days=30), NOW + timedelta(days=90))

    mutation = """
    mutation CreateTask($input: TaskCreateInput!) {
      createTask(data: $input) { id }
    }
    """
    result = await _gql(client, mutation, {"input": {"title": title, "status": status, "dueAt": due_at}})
    task_id = result.get("createTask", {}).get("id", "")

    if task_id and (person_id or company_id):
        target_mutation = """
        mutation CreateTaskTarget($input: TaskTargetCreateInput!) {
          createTaskTarget(data: $input) { id }
        }
        """
        target_input: dict = {"taskId": task_id}
        if person_id:
            target_input["personId"] = person_id
        elif company_id:
            target_input["companyId"] = company_id
        try:
            await _gql(client, target_mutation, {"input": target_input})
        except Exception:
            pass

    return task_id


# ---------------------------------------------------------------------------
# Main seeder
# ---------------------------------------------------------------------------

async def seed_crm_data(
    num_companies: int = 30,
    people_per_company: int = 3,
    standalone_people: int = 20,
    num_opportunities: int = 50,
    num_notes: int = 40,
    num_tasks: int = 30,
    dry_run: bool = False,
) -> dict:
    """Seed Twenty CRM with realistic data spanning 3 years."""

    if dry_run:
        print(f"[DRY RUN] Would create: {num_companies} companies, "
              f"{num_companies * people_per_company + standalone_people} people, "
              f"{num_opportunities} opportunities, {num_notes} notes, {num_tasks} tasks")
        return {"dry_run": True}

    stats = {
        "companies": 0,
        "people": 0,
        "opportunities": 0,
        "notes": 0,
        "tasks": 0,
        "errors": [],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Create companies
        print(f"Creating {num_companies} companies...")
        company_ids = []
        for i in range(num_companies):
            try:
                cid = await create_company(client, i)
                company_ids.append(cid)
                stats["companies"] += 1
                if (i + 1) % 10 == 0:
                    print(f"  Companies: {i + 1}/{num_companies}")
            except Exception as e:
                stats["errors"].append(f"Company {i}: {e}")

        # 2. Create people linked to companies
        print(f"Creating people ({people_per_company} per company)...")
        person_ids = []
        for cid in company_ids:
            for _ in range(people_per_company):
                try:
                    pid = await create_person(client, company_id=cid)
                    person_ids.append(pid)
                    stats["people"] += 1
                except Exception as e:
                    stats["errors"].append(f"Person (company {cid}): {e}")

        # 3. Create standalone people
        print(f"Creating {standalone_people} standalone people...")
        for _ in range(standalone_people):
            try:
                pid = await create_person(client)
                person_ids.append(pid)
                stats["people"] += 1
            except Exception as e:
                stats["errors"].append(f"Standalone person: {e}")

        # 4. Create opportunities
        print(f"Creating {num_opportunities} opportunities...")
        for i in range(num_opportunities):
            try:
                cid = random.choice(company_ids) if company_ids else None
                pid = random.choice(person_ids) if person_ids else None
                await create_opportunity(client, company_id=cid, person_id=pid)
                stats["opportunities"] += 1
                if (i + 1) % 10 == 0:
                    print(f"  Opportunities: {i + 1}/{num_opportunities}")
            except Exception as e:
                stats["errors"].append(f"Opportunity {i}: {e}")

        # 5. Create notes
        print(f"Creating {num_notes} notes...")
        for i in range(num_notes):
            try:
                target_type = random.choice(["person", "company"])
                if target_type == "person" and person_ids:
                    await create_note(client, person_id=random.choice(person_ids))
                elif company_ids:
                    await create_note(client, company_id=random.choice(company_ids))
                else:
                    await create_note(client)
                stats["notes"] += 1
            except Exception as e:
                stats["errors"].append(f"Note {i}: {e}")

        # 6. Create tasks
        print(f"Creating {num_tasks} tasks...")
        for i in range(num_tasks):
            try:
                target_type = random.choice(["person", "company"])
                if target_type == "person" and person_ids:
                    await create_task(client, person_id=random.choice(person_ids))
                elif company_ids:
                    await create_task(client, company_id=random.choice(company_ids))
                else:
                    await create_task(client)
                stats["tasks"] += 1
            except Exception as e:
                stats["errors"].append(f"Task {i}: {e}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Seed Twenty CRM with test data")
    parser.add_argument("--url", default=GRAPHQL_URL, help="Twenty GraphQL endpoint")
    parser.add_argument("--api-key", default=API_KEY, help="Twenty API key")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be created without making API calls")
    parser.add_argument("--companies", type=int, default=30)
    parser.add_argument("--people-per-company", type=int, default=3)
    parser.add_argument("--standalone-people", type=int, default=20)
    parser.add_argument("--opportunities", type=int, default=50)
    parser.add_argument("--notes", type=int, default=40)
    parser.add_argument("--tasks", type=int, default=30)
    args = parser.parse_args()

    global GRAPHQL_URL, API_KEY
    GRAPHQL_URL = args.url
    API_KEY = args.api_key

    if not API_KEY and not args.dry_run:
        print("ERROR: TWENTY_API_KEY not set. Use --api-key or set TWENTY_API_KEY env var.")
        sys.exit(1)

    print(f"Twenty CRM Seed Script")
    print(f"  URL: {GRAPHQL_URL}")
    print(f"  API Key: {'*' * 8}...{API_KEY[-4:] if len(API_KEY) >= 4 else '(not set)'}")
    print(f"  Dry Run: {args.dry_run}")
    print()

    stats = asyncio.run(seed_crm_data(
        num_companies=args.companies,
        people_per_company=args.people_per_company,
        standalone_people=args.standalone_people,
        num_opportunities=args.opportunities,
        num_notes=args.notes,
        num_tasks=args.tasks,
        dry_run=args.dry_run,
    ))

    print()
    print("=== SEED RESULTS ===")
    for key, value in stats.items():
        if key == "errors":
            if value:
                print(f"  Errors: {len(value)}")
                for err in value[:10]:
                    print(f"    - {err}")
                if len(value) > 10:
                    print(f"    ... and {len(value) - 10} more")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
