"""Salon vertical module package for hair, beauty, and appointment-driven shop workflows."""

from __future__ import annotations

from typing import Any

from modules.base import BaseModule, ModuleManifest
from modules.registry import register_module

from . import agent_skills, schema, seed


@register_module
class SalonModule(BaseModule):
	"""Salon vertical module for beauty, hair, nail, and waxing workflows."""

	requires_modules = ["core"]
	manifest = ModuleManifest(
		name="salon",
		display_name="Salon",
		version="1.0.0",
		requires_modules=requires_modules,
	)

	def name(self) -> str:
		return "salon"

	def display_name(self) -> str:
		return "Salon"

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
			"label": "Hair Salon",
			"vocabulary": "clients, appointments, stylists, coloring, blowout, treatment, waxing, manicure, pedicure",
			"tone": "warm, polished, welcoming",
			"example_services": "haircut, blowout, keratin treatment, colour and highlights, waxing, mani, pedi",
		}


__all__ = ["SalonModule"]