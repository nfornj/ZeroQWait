# Infisical Community Edition on K3s

This folder contains standalone manifests for Infisical Community Edition:

- `namespace.yaml` creates the `infisical` namespace.
- `deployment.yaml` creates the Infisical secret and deployment.
- `service.yaml` exposes the app internally as `http://infisical-svc:8080` inside the `infisical` namespace.
- `ingress.yaml` routes HTTP traffic to `infisical-svc` through Traefik.

These manifests are intentionally not added to the root Kustomization so existing manifests are not changed.

## Database

Infisical is configured to use the existing PostgreSQL service in the cluster:

```text
postgres.zeroqwait.svc.cluster.local:5432
```

Before applying, replace the placeholder `DATABASE_URL` in `deployment.yaml` with credentials and a database that Infisical can use, for example:

```text
postgresql://infisical:<password>@postgres.zeroqwait.svc.cluster.local:5432/infisical
```

Create the `infisical` database and user in PostgreSQL first, or change the URL to a database/user that already exists and is intended for Infisical.

Also replace these secret placeholders with strong random values:

- `ENCRYPTION_KEY`
- `AUTH_SECRET`
- `JWT_SECRET`

## Apply

From the repo root:

```bash
kubectl apply -f k8s-manifests/infisical/namespace.yaml
kubectl apply -f k8s-manifests/infisical/deployment.yaml
kubectl apply -f k8s-manifests/infisical/service.yaml
kubectl apply -f k8s-manifests/infisical/ingress.yaml
```

Check rollout:

```bash
kubectl rollout status deployment/infisical -n infisical
kubectl get pods,svc,ingress -n infisical
```

## First-Time Admin Setup

1. Open the Infisical URL routed by the ingress, such as `http://infisical.192.168.2.134.nip.io`.
2. Create the first administrator account from the setup screen.
3. Save recovery credentials and enable MFA for the admin account.
4. Create an organization and project for ZeroQwait secrets.
5. Add environments such as `development`, `staging`, and `production`.
6. Create service tokens or machine identities for workloads that need to read secrets.
7. After setup, update `SITE_URL` in `deployment.yaml` if you want Infisical to generate links with the public ingress host instead of `http://infisical-svc:8080`.

## Internal Access

From another pod in the `infisical` namespace, use:

```text
http://infisical-svc:8080
```

From another namespace, use the fully qualified service name:

```text
http://infisical-svc.infisical.svc.cluster.local:8080
```
