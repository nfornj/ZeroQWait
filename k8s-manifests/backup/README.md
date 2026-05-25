# PostgreSQL Backups To Backblaze B2

This folder defines a Kubernetes CronJob that backs up the shared PostgreSQL database to Backblaze B2 every day at 02:00 UTC.

## Files

- `cronjob.yaml` creates `postgres-b2-backup` in the `zeroqwait` namespace.
- The job runs `pg_dump`, compresses the SQL dump with `gzip`, uploads it with `aws s3 cp`, and keeps the newest 14 daily backups.
- Dumps include `--clean --if-exists`, so restoring a dump drops existing objects before recreating them.

## Required Secrets

The CronJob expects credentials to be available as Kubernetes Secrets. In production, these should be synced from Infisical into the `zeroqwait` namespace.

Database credentials are read from the existing `backend-secret`:

- `DB_USER`
- `DB_PASSWORD`

Backblaze B2 credentials are read from `zeroqwait-backup-secret`:

- `B2_ENDPOINT`, for example `https://s3.us-east-005.backblazeb2.com`
- `B2_BUCKET_NAME`
- `B2_KEY_ID`
- `B2_APP_KEY`
- `B2_REGION`, optional, defaults to `us-east-005`

For a one-off local cluster test, create the B2 secret manually. Do not commit real values:

```bash
kubectl create secret generic zeroqwait-backup-secret \
  -n zeroqwait \
  --from-literal=B2_ENDPOINT='https://s3.us-east-005.backblazeb2.com' \
  --from-literal=B2_BUCKET_NAME='<bucket>' \
  --from-literal=B2_KEY_ID='<key-id>' \
  --from-literal=B2_APP_KEY='<application-key>' \
  --from-literal=B2_REGION='us-east-005'
```

## Apply

```bash
kubectl apply -f k8s-manifests/backup/cronjob.yaml
kubectl get cronjob postgres-b2-backup -n zeroqwait
```

To run an immediate backup without waiting for the schedule:

```bash
kubectl create job --from=cronjob/postgres-b2-backup postgres-b2-backup-manual-$(date -u +%Y%m%d%H%M%S) -n zeroqwait
kubectl logs -n zeroqwait -l job-name=<job-name> --follow
```

## Manual Restore

Restores should be tested in staging first. A restore overwrites database objects in the target database.

1. Scale down application writers so the database is quiet:

```bash
kubectl scale deployment/backend -n zeroqwait --replicas=0
kubectl scale deployment/temporal-worker -n zeroqwait --replicas=0
```

2. Start a temporary restore pod:

```bash
kubectl run postgres-restore -n zeroqwait --rm -it --restart=Never \
  --image=alpine:3.20 \
  --env=DB_HOST=postgres.zeroqwait.svc.cluster.local \
  --env=DB_PORT=5432 \
  --env=DB_NAME=zeroqwait \
  --overrides='{
    "spec": {
      "containers": [{
        "name": "postgres-restore",
        "image": "alpine:3.20",
        "stdin": true,
        "tty": true,
        "env": [
          {"name": "DB_USER", "valueFrom": {"secretKeyRef": {"name": "backend-secret", "key": "DB_USER"}}},
          {"name": "PGPASSWORD", "valueFrom": {"secretKeyRef": {"name": "backend-secret", "key": "DB_PASSWORD"}}},
          {"name": "B2_ENDPOINT", "valueFrom": {"secretKeyRef": {"name": "zeroqwait-backup-secret", "key": "B2_ENDPOINT"}}},
          {"name": "B2_BUCKET_NAME", "valueFrom": {"secretKeyRef": {"name": "zeroqwait-backup-secret", "key": "B2_BUCKET_NAME"}}},
          {"name": "AWS_ACCESS_KEY_ID", "valueFrom": {"secretKeyRef": {"name": "zeroqwait-backup-secret", "key": "B2_KEY_ID"}}},
          {"name": "AWS_SECRET_ACCESS_KEY", "valueFrom": {"secretKeyRef": {"name": "zeroqwait-backup-secret", "key": "B2_APP_KEY"}}}
        ]
      }]
    }
  }' -- /bin/sh
```

3. Inside the pod, install tools and download the selected backup:

```sh
apk add --no-cache aws-cli gzip postgresql16-client
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-005}"
aws --endpoint-url "$B2_ENDPOINT" s3 ls "s3://$B2_BUCKET_NAME/postgres/daily/"
aws --endpoint-url "$B2_ENDPOINT" s3 cp "s3://$B2_BUCKET_NAME/postgres/daily/backup-YYYY-MM-DD-HH.sql.gz" /tmp/restore.sql.gz
gunzip /tmp/restore.sql.gz
```

4. Restore the dump:

```sh
psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" --dbname="$DB_NAME" --set=ON_ERROR_STOP=on --file=/tmp/restore.sql
```

5. Exit the pod and scale application writers back up:

```bash
kubectl scale deployment/backend -n zeroqwait --replicas=1
kubectl scale deployment/temporal-worker -n zeroqwait --replicas=1
```

6. Validate application health and inspect logs before considering the restore complete.