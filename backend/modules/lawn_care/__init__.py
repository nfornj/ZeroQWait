"""Lawn care vertical module package for field-service scheduling and outdoor service workflows."""

from __future__ import annotations

from typing import Any

from modules.base import BaseModule, ModuleManifest
from modules.registry import register_module

from . import agent_skills, schema, seed


@register_module
class LawnCareModule(BaseModule):
	"""Lawn care vertical module for recurring outdoor service workflows."""

	requires_modules = ["core"]
	manifest = ModuleManifest(
		name="lawn_care",
		display_name="Lawn Care",
		version="1.0.0",
		requires_modules=requires_modules,
	)

	def name(self) -> str:
		return "lawn_care"

	def display_name(self) -> str:
		return "Lawn Care"

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
			"label": "Lawn Care Service",
			"vocabulary": "customers, properties, recurring jobs, crews, mowing, edging, fertilizer, weather holds",
			"tone": "practical, reliable, weather-aware",
			"example_services": "lawn mow, edge and trim, fertilize, aeration, leaf cleanup, seasonal cleanup",
		}


__all__ = ["LawnCareModule"]