"""Module registry for loading and activating tenant-scoped vertical modules."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.types import JSON

from .base import BaseModule, ModuleManifest


class ModuleRegistry:
	"""Loads and manages active vertical modules for a tenant."""

	REGISTRY: dict[str, BaseModule] = {}

	def get_modules_for_tenant(self, tenant_id: str, db_session: Any) -> list[BaseModule]:
		"""Return registered module instances listed in the tenant's active_modules column."""
		module_names = self._get_active_module_names(tenant_id, db_session)
		return [self._get_registered_module(module_name) for module_name in module_names]

	def activate_modules_for_tenant(
		self,
		tenant_id: str,
		module_names: list[str],
		db_session: Any,
	) -> None:
		"""Validate, install, seed, and persist active modules for a tenant."""
		activation_order = self._resolve_activation_order(module_names)

		try:
			for module_name in activation_order:
				module = self._get_registered_module(module_name)
				module.run_schema_migration(tenant_id, db_session)
				module.run_seed(tenant_id, db_session)

			self._save_active_module_names(tenant_id, activation_order, db_session)
			db_session.commit()
		except Exception:
			db_session.rollback()
			raise

	def get_combined_agent_skills(self, tenant_id: str, db_session: Any) -> list[dict]:
		"""Return the merged LangGraph-compatible tool definitions for active modules."""
		skills: list[dict] = []
		for module in self.get_modules_for_tenant(tenant_id, db_session):
			skills.extend(module.get_agent_skills())
		return skills

	def _get_active_module_names(self, tenant_id: str, db_session: Any) -> list[str]:
		row = db_session.execute(
			text(
				"""
				SELECT active_modules
				FROM platform.shops
				WHERE id = :tenant_id
				"""
			),
			{"tenant_id": tenant_id},
		).fetchone()
		if row is None:
			raise ValueError(f"Tenant {tenant_id!r} was not found")
		return self._coerce_module_names(row[0])

	def _save_active_module_names(
		self,
		tenant_id: str,
		module_names: list[str],
		db_session: Any,
	) -> None:
		statement = text(
			"""
			UPDATE platform.shops
			SET active_modules = :active_modules
			WHERE id = :tenant_id
			"""
		).bindparams(bindparam("active_modules", type_=JSON))
		result = db_session.execute(
			statement,
			{"tenant_id": tenant_id, "active_modules": module_names},
		)
		if (result.rowcount or 0) == 0:
			raise ValueError(f"Tenant {tenant_id!r} was not found")

	def _resolve_activation_order(self, module_names: list[str]) -> list[str]:
		requested = self._dedupe_module_names(module_names)
		missing = [module_name for module_name in requested if module_name not in self.REGISTRY]
		if missing:
			raise ValueError(f"Unknown module(s): {', '.join(missing)}")

		requested_set = set(requested)
		visiting: set[str] = set()
		visited: set[str] = set()
		ordered: list[str] = []

		def visit(module_name: str, chain: list[str]) -> None:
			if module_name in visiting:
				cycle = " -> ".join([*chain, module_name])
				raise ValueError(f"Circular module dependency detected: {cycle}")
			if module_name in visited:
				return

			visiting.add(module_name)
			module = self._get_registered_module(module_name)
			for dependency_name in self._get_required_module_names(module):
				if dependency_name not in self.REGISTRY:
					raise ValueError(
						f"Module {module_name!r} requires unknown module {dependency_name!r}"
					)
				if dependency_name not in requested_set:
					raise ValueError(
						f"Module {module_name!r} requires module {dependency_name!r} to be active"
					)
				visit(dependency_name, [*chain, module_name])

			visiting.remove(module_name)
			visited.add(module_name)
			ordered.append(module_name)

		for module_name in requested:
			visit(module_name, [])
		return ordered

	def _get_registered_module(self, module_name: str) -> BaseModule:
		try:
			return self.REGISTRY[module_name]
		except KeyError as exc:
			raise ValueError(f"Unknown module: {module_name}") from exc

	def _get_required_module_names(self, module: BaseModule) -> list[str]:
		manifest = getattr(module, "manifest", None)
		if callable(manifest):
			manifest = manifest()
		if isinstance(manifest, ModuleManifest):
			return self._dedupe_module_names(manifest.requires_modules)

		requires_modules = getattr(module, "requires_modules", [])
		if callable(requires_modules):
			requires_modules = requires_modules()
		return self._dedupe_module_names(requires_modules or [])

	def _coerce_module_names(self, value: Any) -> list[str]:
		if value is None:
			return []
		if isinstance(value, str):
			value = json.loads(value)
		if not isinstance(value, list):
			raise ValueError("Tenant active_modules must be a JSON list")
		return self._dedupe_module_names(value)

	def _dedupe_module_names(self, module_names: list[str]) -> list[str]:
		deduped: list[str] = []
		seen: set[str] = set()
		for module_name in module_names:
			if not isinstance(module_name, str) or not module_name.strip():
				raise ValueError("Module names must be non-empty strings")
			normalized = module_name.strip()
			if normalized in seen:
				continue
			seen.add(normalized)
			deduped.append(normalized)
		return deduped


def register_module(module_target: type[BaseModule] | BaseModule) -> type[BaseModule] | BaseModule:
	"""Register a BaseModule subclass or instance in the global module registry."""
	module = module_target() if isinstance(module_target, type) else module_target
	if not isinstance(module, BaseModule):
		raise TypeError("register_module expects a BaseModule subclass or instance")

	module_name = module.name()
	if not module_name or not module_name.strip():
		raise ValueError("Registered modules must provide a non-empty name")
	module_name = module_name.strip()
	if module_name in ModuleRegistry.REGISTRY:
		raise ValueError(f"Module {module_name!r} is already registered")

	ModuleRegistry.REGISTRY[module_name] = module
	return module_target