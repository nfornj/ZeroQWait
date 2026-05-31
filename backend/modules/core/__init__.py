"""Core module package for baseline ZeroQWait tenant capabilities."""

from __future__ import annotations

from typing import Any

from modules.base import BaseModule, ModuleManifest
from modules.registry import register_module

from . import agent_skills, schema, seed


@register_module
class CoreModule(BaseModule):
	"""Baseline module installed for every ZeroQWait tenant."""

	requires_modules: list[str] = []
	manifest = ModuleManifest(
		name="core",
		display_name="Core",
		version="1.0.0",
		requires_modules=requires_modules,
	)

	def name(self) -> str:
		return "core"

	def display_name(self) -> str:
		return "Core"

	def version(self) -> str:
		return "1.0.0"

	def run_schema_migration(self, tenant_id: str, db_session: Any) -> None:
		schema.run_schema_migration(tenant_id, db_session)

	def run_seed(self, tenant_id: str, db_session: Any) -> None:
		seed.run_seed(tenant_id, db_session)

	def get_agent_skills(self) -> list[dict]:
		return agent_skills.get_agent_skills()

	def get_vertical_profile(self) -> dict:
		return {
			"label": "Service Business",
			"vocabulary": "customers, appointments, services, staff",
			"tone": "professional, helpful, concise",
			"example_services": "standard service, consultation, follow-up",
		}


__all__ = ["CoreModule"]