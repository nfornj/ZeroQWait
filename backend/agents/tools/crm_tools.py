"""Twenty CRM GraphQL API tools.

Plain async Python functions — no LangChain Tool wrappers.
Follows the same pattern as booking_tools.py and hr_tools.py.
"""

import os
from typing import Any, Dict, List, Optional

import httpx


async def _gql(query: str, variables: dict = {}) -> dict:
    """Execute a GraphQL query against the Twenty CRM API."""
    url = os.getenv("TWENTY_GRAPHQL_URL", "http://twenty:3000/graphql")
    api_key = os.getenv("TWENTY_API_KEY", "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            json={"query": query, "variables": variables},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise ValueError(f"Twenty GraphQL error: {data['errors']}")
        return data.get("data", {})


async def crm_get_people(limit: int = 20) -> list:
    """Get people list ordered by createdAt desc."""
    query = """
    query GetPeople($limit: Int) {
      people(first: $limit, orderBy: { createdAt: DescNullsLast }) {
        edges {
          node {
            id
            name { firstName lastName }
            emails { primaryEmail }
            phones { primaryPhoneNumber }
            city
            createdAt
            company { name }
          }
        }
      }
    }
    """
    data = await _gql(query, {"limit": limit})
    edges = data.get("people", {}).get("edges", [])
    results = []
    for edge in edges:
        node = edge.get("node", {})
        name = node.get("name") or {}
        first = name.get("firstName") or ""
        last = name.get("lastName") or ""
        results.append({
            "id": node.get("id"),
            "display_name": f"{first} {last}".strip(),
            "first_name": first,
            "last_name": last,
            "email": (node.get("emails") or {}).get("primaryEmail"),
            "phone": (node.get("phones") or {}).get("primaryPhoneNumber"),
            "city": node.get("city"),
            "created_at": node.get("createdAt"),
            "company": (node.get("company") or {}).get("name"),
        })
    return results


async def crm_search_person(name: str) -> list:
    """Search people by firstName OR lastName containing the name string."""
    query = """
    query SearchPerson($name: String!) {
      people(
        filter: {
          or: [
            { name: { firstName: { like: $name } } }
            { name: { lastName: { like: $name } } }
          ]
        }
      ) {
        edges {
          node {
            id
            name { firstName lastName }
            emails { primaryEmail }
            phones { primaryPhoneNumber }
            city
            createdAt
            company { name }
          }
        }
      }
    }
    """
    search_term = f"%{name}%"
    data = await _gql(query, {"name": search_term})
    edges = data.get("people", {}).get("edges", [])
    results = []
    for edge in edges:
        node = edge.get("node", {})
        n = node.get("name") or {}
        first = n.get("firstName") or ""
        last = n.get("lastName") or ""
        results.append({
            "id": node.get("id"),
            "display_name": f"{first} {last}".strip(),
            "first_name": first,
            "last_name": last,
            "email": (node.get("emails") or {}).get("primaryEmail"),
            "phone": (node.get("phones") or {}).get("primaryPhoneNumber"),
            "city": node.get("city"),
            "created_at": node.get("createdAt"),
            "company": (node.get("company") or {}).get("name"),
        })
    return results


async def crm_get_companies(limit: int = 20) -> list:
    """Get companies list ordered by createdAt desc."""
    query = """
    query GetCompanies($limit: Int) {
      companies(first: $limit, orderBy: { createdAt: DescNullsLast }) {
        edges {
          node {
            id
            name
            domainName { primaryLinkUrl }
            employees
            city
            createdAt
            annualRecurringRevenue { amountMicros currencyCode }
            people { totalCount }
          }
        }
      }
    }
    """
    data = await _gql(query, {"limit": limit})
    edges = data.get("companies", {}).get("edges", [])
    results = []
    for edge in edges:
        node = edge.get("node", {})
        arr = node.get("annualRecurringRevenue") or {}
        results.append({
            "id": node.get("id"),
            "name": node.get("name"),
            "domain": (node.get("domainName") or {}).get("primaryLinkUrl"),
            "employees": node.get("employees"),
            "city": node.get("city"),
            "created_at": node.get("createdAt"),
            "arr_dollars": (arr.get("amountMicros") or 0) / 1_000_000,
            "arr_currency": arr.get("currencyCode"),
            "people_count": (node.get("people") or {}).get("totalCount", 0),
        })
    return results


async def crm_get_opportunities(limit: int = 20, stage: Optional[str] = None) -> list:
    """Get opportunities list, optionally filtered by stage."""
    filter_clause = ""
    variables: Dict[str, Any] = {"limit": limit}
    if stage:
        filter_clause = ', filter: { stage: { eq: $stage } }'
        variables["stage"] = stage

    query = f"""
    query GetOpportunities($limit: Int{', $stage: String' if stage else ''}) {{
      opportunities(first: $limit, orderBy: {{ createdAt: DescNullsLast }}{filter_clause}) {{
        edges {{
          node {{
            id
            name
            amount {{ amountMicros currencyCode }}
            closeDate
            stage
            pointOfContact {{ name {{ firstName lastName }} }}
            company {{ name }}
          }}
        }}
      }}
    }}
    """
    data = await _gql(query, variables)
    edges = data.get("opportunities", {}).get("edges", [])
    results = []
    for edge in edges:
        node = edge.get("node", {})
        amount = node.get("amount") or {}
        micros = amount.get("amountMicros") or 0
        poc = node.get("pointOfContact") or {}
        poc_name = poc.get("name") or {}
        results.append({
            "id": node.get("id"),
            "name": node.get("name"),
            "amount_dollars": micros / 1_000_000 if micros else 0.0,
            "currency": amount.get("currencyCode"),
            "close_date": node.get("closeDate"),
            "stage": node.get("stage"),
            "point_of_contact": f"{poc_name.get('firstName', '')} {poc_name.get('lastName', '')}".strip(),
            "company": (node.get("company") or {}).get("name"),
        })
    return results


async def crm_get_notes(limit: int = 20) -> list:
    """Get notes ordered by createdAt desc."""
    query = """
    query GetNotes($limit: Int) {
      notes(first: $limit, orderBy: { createdAt: DescNullsLast }) {
        edges {
          node {
            id
            title
            body
            createdAt
            noteTargets {
              edges {
                node {
                  person { id name { firstName lastName } }
                  company { id name }
                }
              }
            }
          }
        }
      }
    }
    """
    data = await _gql(query, {"limit": limit})
    edges = data.get("notes", {}).get("edges", [])
    results = []
    for edge in edges:
        node = edge.get("node", {})
        targets = []
        for te in (node.get("noteTargets") or {}).get("edges", []):
            tn = te.get("node", {})
            person = tn.get("person")
            company = tn.get("company")
            if person:
                pn = person.get("name") or {}
                targets.append({
                    "type": "person",
                    "id": person.get("id"),
                    "name": f"{pn.get('firstName', '')} {pn.get('lastName', '')}".strip(),
                })
            if company:
                targets.append({
                    "type": "company",
                    "id": company.get("id"),
                    "name": company.get("name"),
                })
        results.append({
            "id": node.get("id"),
            "title": node.get("title"),
            "body": node.get("body"),
            "created_at": node.get("createdAt"),
            "targets": targets,
        })
    return results


async def crm_get_tasks(limit: int = 20, status: Optional[str] = None) -> list:
    """Get tasks, optionally filtered by status."""
    filter_clause = ""
    variables: Dict[str, Any] = {"limit": limit}
    if status:
        filter_clause = ', filter: { status: { eq: $status } }'
        variables["status"] = status

    query = f"""
    query GetTasks($limit: Int{', $status: String' if status else ''}) {{
      tasks(first: $limit, orderBy: {{ createdAt: DescNullsLast }}{filter_clause}) {{
        edges {{
          node {{
            id
            title
            status
            dueAt
            assignee {{ name {{ firstName lastName }} }}
            taskTargets {{
              edges {{
                node {{
                  person {{ id name {{ firstName lastName }} }}
                  company {{ id name }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    data = await _gql(query, variables)
    edges = data.get("tasks", {}).get("edges", [])
    results = []
    for edge in edges:
        node = edge.get("node", {})
        assignee = node.get("assignee") or {}
        an = assignee.get("name") or {}
        targets = []
        for te in (node.get("taskTargets") or {}).get("edges", []):
            tn = te.get("node", {})
            person = tn.get("person")
            company = tn.get("company")
            if person:
                pn = person.get("name") or {}
                targets.append({
                    "type": "person",
                    "id": person.get("id"),
                    "name": f"{pn.get('firstName', '')} {pn.get('lastName', '')}".strip(),
                })
            if company:
                targets.append({
                    "type": "company",
                    "id": company.get("id"),
                    "name": company.get("name"),
                })
        results.append({
            "id": node.get("id"),
            "title": node.get("title"),
            "status": node.get("status"),
            "due_at": node.get("dueAt"),
            "assignee": f"{an.get('firstName', '')} {an.get('lastName', '')}".strip(),
            "targets": targets,
        })
    return results


async def crm_get_pipeline_summary() -> dict:
    """Get pipeline summary grouped by stage with counts and values."""
    opportunities = await crm_get_opportunities(limit=100)
    by_stage: Dict[str, Dict[str, Any]] = {}
    total_value = 0.0
    for opp in opportunities:
        stage = opp.get("stage") or "Unknown"
        amount = opp.get("amount_dollars", 0.0)
        if stage not in by_stage:
            by_stage[stage] = {"count": 0, "value": 0.0}
        by_stage[stage]["count"] += 1
        by_stage[stage]["value"] += amount
        total_value += amount
    return {
        "by_stage": by_stage,
        "total_value": total_value,
        "total_count": len(opportunities),
    }


async def crm_get_person_details(person_id: str) -> dict:
    """Get full details for a single person by ID."""
    query = """
    query GetPersonDetails($id: ID!) {
      person(id: $id) {
        id
        name { firstName lastName }
        emails { primaryEmail additionalEmails }
        phones { primaryPhoneNumber additionalPhones }
        city
        jobTitle
        createdAt
        updatedAt
        company { id name domainName { primaryLinkUrl } }
        noteTargets { edges { node { note { id title body createdAt } } } }
        taskTargets { edges { node { task { id title status dueAt } } } }
      }
    }
    """
    data = await _gql(query, {"id": person_id})
    person = data.get("person", {})
    if not person:
        return {"error": f"Person with id={person_id} not found"}

    name = person.get("name") or {}
    first = name.get("firstName") or ""
    last = name.get("lastName") or ""

    notes = []
    for ne in (person.get("noteTargets") or {}).get("edges", []):
        note = (ne.get("node") or {}).get("note") or {}
        if note:
            notes.append({
                "id": note.get("id"),
                "title": note.get("title"),
                "body": note.get("body"),
                "created_at": note.get("createdAt"),
            })

    tasks = []
    for te in (person.get("taskTargets") or {}).get("edges", []):
        task = (te.get("node") or {}).get("task") or {}
        if task:
            tasks.append({
                "id": task.get("id"),
                "title": task.get("title"),
                "status": task.get("status"),
                "due_at": task.get("dueAt"),
            })

    company = person.get("company") or {}
    return {
        "id": person.get("id"),
        "display_name": f"{first} {last}".strip(),
        "first_name": first,
        "last_name": last,
        "email": (person.get("emails") or {}).get("primaryEmail"),
        "additional_emails": (person.get("emails") or {}).get("additionalEmails"),
        "phone": (person.get("phones") or {}).get("primaryPhoneNumber"),
        "additional_phones": (person.get("phones") or {}).get("additionalPhones"),
        "city": person.get("city"),
        "job_title": person.get("jobTitle"),
        "created_at": person.get("createdAt"),
        "updated_at": person.get("updatedAt"),
        "company": {
            "id": company.get("id"),
            "name": company.get("name"),
            "domain": (company.get("domainName") or {}).get("primaryLinkUrl"),
        } if company.get("id") else None,
        "notes": notes,
        "tasks": tasks,
    }
