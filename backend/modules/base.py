"""Defines the BaseModule contract that every vertical module must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModuleManifest:
	"""Describes a vertical module and its module dependencies."""

	name: str
	display_name: str
	version: str
	requires_modules: list[str] = field(default_factory=list)


class BaseModule(ABC):
	"""Abstract contract implemented by every tenant-loadable module."""

	@abstractmethod
	def name(self) -> str:
		"""Return the stable module key, for example "lawn_care"."""

	@abstractmethod
	def display_name(self) -> str:
		"""Return the human-readable module name, for example "Lawn Care"."""

	@abstractmethod
	def version(self) -> str:
		"""Return the semantic version for this module implementation."""

	@abstractmethod
	def run_schema_migration(self, tenant_id: str, db_session: Any) -> None:
		"""Run schema migration work for a tenant-scoped module installation."""

	@abstractmethod
	def run_seed(self, tenant_id: str, db_session: Any) -> None:
		"""Seed tenant-scoped default data for this module."""

	@abstractmethod
	def get_agent_skills(self) -> list[dict]:
		"""Return LangGraph-compatible tool definitions exposed by this module."""

	@abstractmethod
	def get_vertical_profile(self) -> dict:
		"""Return vocabulary and tone configuration compatible with vertical profiles."""