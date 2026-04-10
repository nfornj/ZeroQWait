# FastCuts Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the FastCuts application.

## Architecture

- **PostgreSQL**: StatefulSet with persistent storage (10Gi)
- **Backend**: FastAPI application exposed on NodePort 30000
- **Frontend**: React application exposed on NodePort 30001

## Scheduling and Node Pool Strategy

See `NODE_POOL_BALANCING.md` for the production node pool balance plan, labels/taints, and rollout sequence.

## Directory Structure

```
~/k8s/apps/fastcuts/          # Kubernetes manifests
~/apps/fastcuts/              # Application source code
  ├── backend/                # FastAPI backend
  └── frontend/               # React frontend
```

## Deployment

### Option 1: Using the deployment script (Recommended)
```bash
cd ~/k8s/apps/fastcuts
sudo bash deploy-fastcuts.sh
```

### Option 2: Manual deployment
```bash
# Create namespace
sudo kubectl create namespace fastcuts

# Deploy PostgreSQL
sudo kubectl apply -f postgres-pvc.yaml
sudo kubectl apply -f postgres-secret.yaml
sudo kubectl apply -f postgres-statefulset.yaml

# Wait for PostgreSQL
sudo kubectl wait --for=condition=ready pod -l app=postgres -n fastcuts --timeout=120s

# Deploy Backend
sudo kubectl apply -f backend-secret.yaml
sudo kubectl apply -f backend-configmap.yaml
sudo kubectl apply -f backend-deployment.yaml

# Deploy Frontend
sudo kubectl apply -f frontend-deployment.yaml
```

## Access Points

- **Backend API**: http://192.168.2.88:30000
- **Backend API Docs**: http://192.168.2.88:30000/docs
- **Frontend**: http://192.168.2.88:30001

## Monitoring

```bash
# Check pod status
sudo kubectl get pods -n fastcuts

# Check services
sudo kubectl get services -n fastcuts

# Check logs
sudo kubectl logs -n fastcuts -l app=backend
sudo kubectl logs -n fastcuts -l app=frontend
sudo kubectl logs -n fastcuts -l app=postgres

# Describe resources
sudo kubectl describe pod -n fastcuts <pod-name>
```

## Database Access

The PostgreSQL database is accessible within the cluster at:
- **Host**: `postgres.fastcuts.svc.cluster.local`
- **Port**: `5432`
- **Database**: `zeroqwait`
- **User**: `zeroqwait`
- **Password**: Set in `postgres-secret.yaml`

## Updating the Application

### Backend updates
```bash
# Edit code in ~/apps/fastcuts/backend/
# Restart the deployment
sudo kubectl rollout restart deployment/backend -n fastcuts
```

### Frontend updates
```bash
# Edit code in ~/apps/fastcuts/frontend/
# Restart the deployment
sudo kubectl rollout restart deployment/frontend -n fastcuts
```

## Persistent Data

PostgreSQL data is stored in a PersistentVolume managed by k3s's local-path provisioner.
Data persists across pod restarts and redeployments.

## Configuration

### Backend Environment Variables
Managed via ConfigMap (`backend-configmap.yaml`) and Secret (`backend-secret.yaml`):
- `DB_HOST`: PostgreSQL service DNS
- `DB_PORT`: PostgreSQL port
- `DB_NAME`: Database name
- `DB_USER`: Database user (secret)
- `DB_PASSWORD`: Database password (secret)
- `SECRET_KEY`: JWT secret key (secret)
- `FRONTEND_URL`: Frontend URL for CORS

### Frontend Environment Variables
- `REACT_APP_API_URL`: Backend API URL (set during build)

## Troubleshooting

### Pods not starting
```bash
sudo kubectl describe pod -n fastcuts <pod-name>
sudo kubectl logs -n fastcuts <pod-name>
```

### Database connection issues
```bash
# Check PostgreSQL pod
sudo kubectl exec -it -n zeroqwait postgres-0 -- psql -U zeroqwait -d zeroqwait

# Test connectivity from backend
sudo kubectl exec -it -n fastcuts <backend-pod-name> -- bash
# Inside pod:
apt-get update && apt-get install -y postgresql-client
psql -h postgres.zeroqwait.svc.cluster.local -U zeroqwait -d zeroqwait
```

### Port conflicts
If ports 30000 or 30001 are already in use, edit the Service manifests and change the `nodePort` values.

## Cleanup

```bash
# Delete all resources
sudo kubectl delete namespace fastcuts

# This will remove all pods, services, and deployments
# The PersistentVolume data will be retained unless manually deleted
```

## Security Notes

**IMPORTANT**: Change the following before production:
1. PostgreSQL password in `postgres-secret.yaml`
2. Backend database password in `backend-secret.yaml`
3. JWT secret key in `backend-secret.yaml`
4. Consider using proper secrets management (e.g., sealed-secrets, external-secrets)
