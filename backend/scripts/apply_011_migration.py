#!/usr/bin/env python3
"""
apply_011_migration.py
Applies migration 011 (platform schema separation) to the K3s PostgreSQL instance.

Run from the project root:
    cd /home/neekrishrichu/projects/FastCuts
    python backend/scripts/apply_011_migration.py
"""

import os
import subprocess
import sys
import time
import pathlib
import base64

MIGRATION_FILE = pathlib.Path(__file__).parent.parent / "migrations" / "011_platform_schema.sql"
NAMESPACE = "zeroqwait"
FORWARD_PORT = 15432  # local port to forward to postgres:5432


def run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a command, returning CompletedProcess. Never opens a TTY."""
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=capture,
        text=True,
        env={**os.environ, "PAGER": "cat", "NO_COLOR": "1"},
    )
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed: {' '.join(cmd)}")
        print(f"  stdout: {result.stdout[:500]}")
        print(f"  stderr: {result.stderr[:500]}")
        sys.exit(1)
    return result


def find_postgres_pod() -> str:
    result = run(["sudo", "kubectl", "get", "pods", "-n", NAMESPACE,
                  "-o", "jsonpath={.items[*].metadata.name}"])
    pods = result.stdout.split()
    postgres_pods = [p for p in pods if "postgres" in p]
    if not postgres_pods:
        print(f"[ERROR] No postgres pod found in namespace {NAMESPACE}")
        print(f"  All pods: {pods}")
        sys.exit(1)
    print(f"[INFO] Found postgres pod: {postgres_pods[0]}")
    return postgres_pods[0]


def get_db_credentials() -> tuple[str, str, str]:
    """Returns (db_name, db_user, db_password)."""
    # Try reading from backend configmap
    cm = run(["sudo", "kubectl", "get", "configmap", "backend-configmap",
               "-n", NAMESPACE, "-o", "jsonpath={.data}"], check=False)
    db_name = "zeroqwait"
    db_user = "zeroqwait"
    db_password = "password"

    if cm.returncode == 0 and cm.stdout:
        import json
        try:
            data = json.loads(cm.stdout)
            db_name = data.get("DB_NAME", db_name)
            db_user = data.get("DB_USER", db_user)
        except Exception:
            pass

    # Try reading password from postgres-secret
    sec = run(["sudo", "kubectl", "get", "secret", "postgres-secret",
               "-n", NAMESPACE, "-o", "jsonpath={.data}"], check=False)
    if sec.returncode == 0 and sec.stdout:
        import json
        try:
            data = json.loads(sec.stdout)
            # Secrets are base64-encoded
            for key in ["POSTGRES_PASSWORD", "DB_PASSWORD", "password"]:
                if key in data:
                    db_password = base64.b64decode(data[key]).decode().strip()
                    break
        except Exception:
            pass

    # Try backend secret as fallback
    bsec = run(["sudo", "kubectl", "get", "secret", "backend-secret",
                "-n", NAMESPACE, "-o", "jsonpath={.data}"], check=False)
    if bsec.returncode == 0 and bsec.stdout:
        import json
        try:
            data = json.loads(bsec.stdout)
            for key in ["DB_PASSWORD", "POSTGRES_PASSWORD"]:
                if key in data:
                    db_password = base64.b64decode(data[key]).decode().strip()
                    break
        except Exception:
            pass

    print(f"[INFO] DB credentials: name={db_name!r} user={db_user!r} password=***")
    return db_name, db_user, db_password


def apply_migration_via_kubectl_exec(pod: str, db_name: str, db_user: str, db_password: str) -> None:
    """Copy SQL to pod and run psql against it."""
    print("[INFO] Copying migration SQL to pod...")
    run(["sudo", "kubectl", "cp",
         str(MIGRATION_FILE),
         f"{NAMESPACE}/{pod}:/tmp/011_platform_schema.sql"])

    print("[INFO] Applying migration in pod...")
    env_prefix = f"PGPASSWORD={db_password}"
    psql_cmd = (
        f"PGPASSWORD={db_password} psql -U {db_user} -d {db_name} "
        f"--no-psqlrc -A -q -f /tmp/011_platform_schema.sql"
    )
    result = run(
        ["sudo", "kubectl", "exec", "-n", NAMESPACE, pod, "--",
         "sh", "-c", psql_cmd],
        check=False,
    )
    print(f"[OUTPUT]\n{result.stdout}")
    if result.stderr:
        # psql prints NOTICE to stderr — filter for real errors
        errors = [l for l in result.stderr.splitlines() if "ERROR" in l.upper()]
        if errors:
            print(f"[PSQL ERRORS]\n" + "\n".join(errors))
            sys.exit(1)
        else:
            print(f"[PSQL NOTICES]\n{result.stderr[:1000]}")
    if result.returncode != 0:
        print(f"[ERROR] psql exited with code {result.returncode}")
        sys.exit(1)

    print("[INFO] Migration applied. Running verification...")
    verify_sql = (
        "SELECT table_schema, table_name "
        "FROM information_schema.tables "
        "WHERE table_name IN ('users','shops','shop_runtime_assignments','audit_logs') "
        "ORDER BY table_name;"
    )
    verify_cmd = (
        f"PGPASSWORD={db_password} psql -U {db_user} -d {db_name} "
        f"--no-psqlrc -A -F'|' -c \"{verify_sql}\""
    )
    v = run(
        ["sudo", "kubectl", "exec", "-n", NAMESPACE, pod, "--",
         "sh", "-c", verify_cmd],
        check=False,
    )
    print(f"[VERIFY]\n{v.stdout}")
    if v.stderr:
        print(f"[VERIFY STDERR]\n{v.stderr[:500]}")

    # Also check search_path setting
    sp_sql = "SHOW search_path;"
    sp_cmd = (
        f"PGPASSWORD={db_password} psql -U {db_user} -d {db_name} "
        f"--no-psqlrc -A -c \"{sp_sql}\""
    )
    sp = run(["sudo", "kubectl", "exec", "-n", NAMESPACE, pod, "--",
              "sh", "-c", sp_cmd], check=False)
    print(f"[SEARCH_PATH]\n{sp.stdout}")


def main():
    print(f"[INFO] Migration file: {MIGRATION_FILE}")
    if not MIGRATION_FILE.exists():
        print(f"[ERROR] Migration file not found: {MIGRATION_FILE}")
        sys.exit(1)

    pod = find_postgres_pod()
    db_name, db_user, db_password = get_db_credentials()
    apply_migration_via_kubectl_exec(pod, db_name, db_user, db_password)
    print("[DONE] Migration 011 complete.")


if __name__ == "__main__":
    main()
