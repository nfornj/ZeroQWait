"""Expose core receptionist, finance, and HR agent skill metadata."""

from __future__ import annotations

from typing import Iterable


def get_agent_skills() -> list[dict]:
	"""Return core specialist operations as LangGraph-compatible skill metadata."""
	from agents import finance, hr, receptionist

	return [
		*_build_agent_skill_dicts(
			agent_name="receptionist",
			operations=receptionist.SUPPORTED_OPERATIONS,
			planner_instructions=receptionist.PLANNER_INSTRUCTIONS,
		),
		*_build_agent_skill_dicts(
			agent_name="finance",
			operations=finance.SUPPORTED_OPERATIONS,
			planner_instructions=finance.PLANNER_INSTRUCTIONS,
		),
		*_build_agent_skill_dicts(
			agent_name="hr",
			operations=hr.SUPPORTED_OPERATIONS,
			planner_instructions=hr.PLANNER_INSTRUCTIONS,
		),
	]


def _build_agent_skill_dicts(
	*,
	agent_name: str,
	operations: Iterable[str],
	planner_instructions: str,
) -> list[dict]:
	descriptions = _parse_operation_descriptions(planner_instructions)
	return [
		{
			"name": operation,
			"description": descriptions.get(
				operation,
				f"Core {agent_name} operation: {operation.replace('_', ' ')}.",
			),
			"agent": agent_name,
		}
		for operation in operations
	]


def _parse_operation_descriptions(planner_instructions: str) -> dict[str, str]:
	descriptions: dict[str, str] = {}
	for raw_line in planner_instructions.splitlines():
		line = raw_line.strip()
		if not line.startswith("- ") or ":" not in line:
			continue
		name, description = line[2:].split(":", 1)
		operation_name = name.strip()
		if operation_name:
			descriptions[operation_name] = description.strip()
	return descriptions