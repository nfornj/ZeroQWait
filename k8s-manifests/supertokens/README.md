# SuperTokens Core on K3s

This folder deploys SuperTokens Core for the existing FastAPI and React SuperTokens integration.

- `secret.yaml` is a template for the Core database and API key values.
- `deployment.yaml` runs SuperTokens Core in the `zeroqwait` namespace.
- `service.yaml` exposes the internal backend URL `http://supertokens-svc:3567`.
- The Core uses the existing PostgreSQL service at `postgres.zeroqwait.svc.cluster.local:5432`.

Before applying, create a database/user for SuperTokens in the existing cluster PostgreSQL and store the credentials in `supertokens-secret`:

```bash
kubectl create secret generic supertokens-secret -n zeroqwait \
  --from-literal=POSTGRESQL_CONNECTION_URI='postgresql://<user>:<password>@postgres.zeroqwait.svc.cluster.local:5432/supertokens' \
  --from-literal=API_KEYS='<supertokens-api-key>'
```

Then deploy:

```bash
kubectl apply -f k8s-manifests/supertokens/secret.yaml
kubectl apply -f k8s-manifests/supertokens/deployment.yaml
kubectl apply -f k8s-manifests/supertokens/service.yaml
kubectl rollout status deployment/supertokens -n zeroqwait
```

Configure the backend with:

```env
SUPERTOKENS_CONNECTION_URI=http://supertokens-svc:3567
SUPERTOKENS_API_KEY=<supertokens-api-key>
```
