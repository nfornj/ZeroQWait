#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
NAMESPACE="${NAMESPACE:-zeroqwait}"
POD_NAME="${POD_NAME:-postgres-0}"

OLD_DB_NAME="${OLD_DB_NAME:-fastcuts_db}"
NEW_DB_NAME="${NEW_DB_NAME:-zeroqwait}"
OLD_DB_USER="${OLD_DB_USER:-fastcuts_user}"
NEW_DB_USER="${NEW_DB_USER:-zeroqwait}"
DB_PASSWORD="${DB_PASSWORD:-fastcuts_secure_password_change_in_production}"

if [[ "${CONFIRM_RENAME:-}" != "YES" ]]; then
  echo "Refusing to run without CONFIRM_RENAME=YES" >&2
  exit 1
fi

kctl() {
  sudo env KUBECONFIG="${KUBECONFIG_PATH}" kubectl "$@"
}

psql_old() {
  kctl exec -n "${NAMESPACE}" "${POD_NAME}" -- env \
    PGPASSWORD="${DB_PASSWORD}" \
    psql -v ON_ERROR_STOP=1 -U "${OLD_DB_USER}" -d postgres "$@"
}

psql_new() {
  kctl exec -n "${NAMESPACE}" "${POD_NAME}" -- env \
    PGPASSWORD="${DB_PASSWORD}" \
    psql -v ON_ERROR_STOP=1 -U "${NEW_DB_USER}" -d postgres "$@"
}

echo "==> Renaming Postgres database ${OLD_DB_NAME} -> ${NEW_DB_NAME}"
echo "==> Replacing Postgres role ${OLD_DB_USER} with ${NEW_DB_USER}"

psql_old -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${OLD_DB_NAME}' AND pid <> pg_backend_pid();"

if [[ "$(psql_old -Atc "SELECT 1 FROM pg_database WHERE datname = '${OLD_DB_NAME}' LIMIT 1;")" == "1" ]] \
  && [[ "$(psql_old -Atc "SELECT 1 FROM pg_database WHERE datname = '${NEW_DB_NAME}' LIMIT 1;")" != "1" ]]; then
  psql_old -c "ALTER DATABASE \"${OLD_DB_NAME}\" RENAME TO \"${NEW_DB_NAME}\";"
fi

if [[ "$(psql_old -Atc "SELECT 1 FROM pg_roles WHERE rolname = '${NEW_DB_USER}' LIMIT 1;")" != "1" ]]; then
  psql_old -c "CREATE ROLE \"${NEW_DB_USER}\" WITH LOGIN SUPERUSER PASSWORD '${DB_PASSWORD}';"
fi

psql_old -c "ALTER DATABASE \"${NEW_DB_NAME}\" OWNER TO \"${NEW_DB_USER}\";"
psql_new -c "ALTER ROLE \"${NEW_DB_USER}\" WITH LOGIN PASSWORD '${DB_PASSWORD}';"

echo "==> Database cutover completed"
echo "==> Note: legacy role ${OLD_DB_USER} is not dropped automatically because it can own cluster bootstrap objects (postgres/template DBs, system schemas)."