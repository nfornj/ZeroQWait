# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

ZeroQwait (zeroqwait.com) is a universal queue management system for various service providers including barbershops, salons, clinics, and more. It's built with a modern full-stack architecture using FastAPI for the backend and React with TypeScript for the frontend. The platform enables businesses to create and manage queues while customers can check in online and view real-time wait times.

## Production Server Information

**IMPORTANT**: The application is now deployed on a new production server using Kubernetes (k3s).

### Server Access
- **SSH**: `ssh neekrishrichu@192.168.2.88`
- **Application Code Location**: `/home/neekrishrichu/apps/zeroqwait/`
- **Kubernetes Manifests Location**: `/home/neekrishrichu/k8s/apps/zeroqwait/`
- **Kubernetes Cluster**: k3s (lightweight Kubernetes)
- **Namespace**: `zeroqwait`

### Access Points
- **Frontend**: http://192.168.2.88:30001
- **Backend API**: http://192.168.2.88:30000
- **Backend API Docs**: http://192.168.2.88:30000/docs

### Important Notes
- The production server uses **Kubernetes**, NOT Docker Compose directly
- Kubernetes commands require: `export KUBECONFIG=/home/neekrishrichu/.kube/config` or may need `sudo` depending on permissions
- The application code is mounted from the host filesystem into pods using hostPath volumes
- Code changes on the server at `~/apps/zeroqwait/` require pod restarts to take effect

## Architecture

### High-Level Structure
- **Full-stack web application** with separate backend and frontend services
- **Kubernetes-based deployment** on k3s with three main components: PostgreSQL StatefulSet, Backend Deployment, and Frontend Deployment
- **RESTful API architecture** with clear separation between data models, API routes, and business logic
- **Authentication system** using JWT tokens with secure password hashing

### Backend (FastAPI)
- **Entry Point**: `backend/main.py` - FastAPI app initialization with CORS, router inclusion, and database setup
- **Database Layer**: SQLAlchemy ORM with PostgreSQL
  - `backend/database.py` - Database connection and session management
  - `backend/models.py` - SQLAlchemy models (User, HaircutService, user_favorites association table)
- **API Layer**: Modular router structure in `backend/routers/`
  - `auth.py` - Authentication endpoints (login, token management)
  - `users.py` - User management and profile endpoints
  - `haircuts.py` - Haircut service search, listing, and favorites management
- **Data Validation**: `backend/schemas.py` - Pydantic models for request/response validation
- **Authentication**: `backend/auth_utils.py` - JWT token handling and password utilities

### Frontend (React + TypeScript)
- **Entry Point**: `frontend/src/index.tsx` and `frontend/src/App.tsx`
- **Routing**: React Router with protected routes for authenticated features
- **UI Framework**: Material-UI (MUI) with custom theming
- **Component Architecture**:
  - `src/components/` - Reusable UI components (Navbar, HaircutCard, SearchForm, ProtectedRoute)
  - `src/pages/` - Route-specific page components (HomePage, LoginPage, RegisterPage, SearchPage, FavoritesPage)
  - `src/contexts/` - React context for state management (likely authentication context)
  - `src/services/` - API service layer for backend communication

### Database Schema
- **Users table**: Authentication and profile data
- **HaircutServices table**: Business listings with location data (lat/lng), ratings, hours, contact info
- **Many-to-many relationship**: Users can favorite multiple haircut services via `user_favorites` association table

## Development Commands

### Local Development (Docker Compose)
```bash
# Start all services (database, backend, frontend) locally
docker-compose up

# Start in detached mode
docker-compose up -d

# Stop all services
docker-compose down

# Rebuild containers after code changes
docker-compose up --build
```

### Production Deployment (Kubernetes on Server)

**Access the production server first:**
```bash
ssh neekrishrichu@192.168.2.88
```

**View deployment status:**
```bash
# Set kubeconfig
export KUBECONFIG=/home/neekrishrichu/.kube/config

# Check pod status
kubectl get pods -n zeroqwait

# Check services
kubectl get services -n zeroqwait

# View logs
kubectl logs -n zeroqwait -l app=backend
kubectl logs -n zeroqwait -l app=frontend
kubectl logs -n zeroqwait -l app=postgres
```

**Deploy or update application:**
```bash
# Navigate to manifests directory
cd ~/k8s/apps/zeroqwait/

# Apply all manifests (initial deployment)
kubectl apply -f postgres-pvc.yaml
kubectl apply -f postgres-secret.yaml
kubectl apply -f postgres-statefulset.yaml
kubectl apply -f backend-configmap.yaml
kubectl apply -f backend-secret.yaml
kubectl apply -f backend-deployment.yaml
kubectl apply -f frontend-deployment.yaml

# Or use the deployment script
bash deploy-with-ingress.sh
```

**Update application code:**
```bash
# 1. Update code in ~/apps/zeroqwait/backend/ or ~/apps/zeroqwait/frontend/
# 2. Restart the deployment to pick up changes
kubectl rollout restart deployment/backend -n zeroqwait
kubectl rollout restart deployment/frontend -n zeroqwait
```

### Backend Development (FastAPI)
```bash
cd backend

# Install PDM (Python Dependency Manager) if not already installed
pip install pdm

# Install dependencies
pdm install

# Run development server with auto-reload
pdm run start

# Run tests
pdm run test

# Run linting and formatting
pdm run lint
```

### Frontend Development (React)
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

### Individual Service Testing
```bash
# Test backend API directly
curl http://localhost:8000/docs  # API documentation
curl http://localhost:8000/      # Health check

# Test frontend
curl http://localhost:3000       # Frontend application
```

## Key Development Patterns

### Backend Patterns
- **Router-based modularization**: Each feature area (auth, users, haircuts) has its own router
- **Dependency injection**: FastAPI's dependency system used for database sessions and authentication
- **Schema validation**: Pydantic models separate from SQLAlchemy models for clean API contracts
- **Authentication middleware**: JWT-based authentication with protected routes

### Frontend Patterns
- **Component composition**: Reusable components with clear separation of concerns
- **Protected routing**: Authentication-aware route protection
- **Service layer pattern**: Separate API communication logic from UI components
- **Material-UI integration**: Consistent design system with custom theming

### Database Patterns
- **SQLAlchemy ORM**: Declarative model definitions with relationships
- **Migration-ready**: Database table creation through SQLAlchemy metadata
- **Relational design**: Proper foreign keys and many-to-many relationships

## Environment Configuration

### Local Development Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (handled by Docker Compose)
- `SECRET_KEY`: JWT token signing key (set in docker-compose.yml)

### Production Kubernetes Environment Variables

Managed via ConfigMap and Secrets:

**ConfigMap** (`backend-configmap.yaml`):
- `DB_HOST`: postgres.zeroqwait.svc.cluster.local
- `DB_PORT`: 5432
- `DB_NAME`: fastcuts_db
- `FRONTEND_URL`: http://192.168.2.88:30001
- `PYTHONUNBUFFERED`: 1
- `USE_SUPABASE`: false

**Secrets** (`backend-secret.yaml`):
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `SECRET_KEY`: JWT token signing key

**Note**: Secret values are defined in the K8s manifests on the server at `~/k8s/apps/zeroqwait/`

### Port Configuration

**Local Development:**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database**: localhost:5432

**Production (Kubernetes NodePort):**
- **Frontend**: http://192.168.2.88:30001
- **Backend API**: http://192.168.2.88:30000
- **Backend API Docs**: http://192.168.2.88:30000/docs
- **Database**: Internal to cluster (postgres.zeroqwait.svc.cluster.local:5432)

## Technology Stack Details

### Backend Dependencies
- **FastAPI**: Modern Python web framework with automatic API documentation
- **SQLAlchemy**: ORM with PostgreSQL support
- **Pydantic**: Data validation and settings management
- **Python-JOSE**: JWT token handling
- **Passlib**: Password hashing with bcrypt
- **Uvicorn**: ASGI server for FastAPI

### Frontend Dependencies  
- **React 18**: Latest React with hooks and modern patterns
- **TypeScript**: Type-safe JavaScript development
- **Material-UI**: Comprehensive React UI framework
- **React Router**: Client-side routing
- **Axios**: HTTP client for API communication

### Development Tools
- **PDM**: Python dependency management (backend)
- **Docker Compose**: Multi-container local development environment
- **Kubernetes (k3s)**: Production deployment orchestration
- **PostgreSQL**: Production-grade relational database

## Kubernetes Deployment Details

### Architecture

**PostgreSQL (StatefulSet):**
- Image: `postgres:16-alpine`
- Storage: 10Gi PersistentVolumeClaim
- Service: ClusterIP (internal only)
- Credentials managed via `postgres-secret.yaml`

**Backend (Deployment):**
- Base Image: `python:3.11-slim`
- Code mounted from: `/home/neekrishrichu/apps/zeroqwait/backend`
- Init containers: Wait for postgres, then run database initialization
- Service: NodePort 30000
- Environment: Configured via ConfigMap + Secret

**Frontend (Deployment):**
- Base Image: `node:18-alpine`
- Code mounted from: `/home/neekrishrichu/apps/zeroqwait/frontend`
- Builds on first start, then uses cached build
- Service: NodePort 30001
- API URL: Configured at build time to point to backend

### Troubleshooting Production Issues

**Check pod status:**
```bash
ssh neekrishrichu@192.168.2.88
export KUBECONFIG=/home/neekrishrichu/.kube/config
kubectl get pods -n zeroqwait
```

**View pod logs:**
```bash
# Backend logs
kubectl logs -n zeroqwait -l app=backend --tail=100

# Frontend logs
kubectl logs -n zeroqwait -l app=frontend --tail=100

# PostgreSQL logs
kubectl logs -n zeroqwait postgres-0
```

**Describe pod (for debugging startup issues):**
```bash
kubectl describe pod -n zeroqwait <pod-name>
```

**Access pod shell:**
```bash
# Backend
kubectl exec -it -n zeroqwait deployment/backend -- bash

# Frontend
kubectl exec -it -n zeroqwait deployment/frontend -- sh

# PostgreSQL
kubectl exec -it -n zeroqwait postgres-0 -- psql -U fastcuts_user -d fastcuts_db
```

**Common Issues:**

1. **Backend CrashLoopBackOff with database authentication error:**
   - Check if postgres and backend secrets match
   - Verify: `kubectl get secret -n zeroqwait postgres-secret -o yaml`
   - Verify: `kubectl get secret -n zeroqwait backend-secret -o yaml`
   - Passwords must match between `POSTGRES_PASSWORD` and `DB_PASSWORD`

2. **Frontend not redirecting after login:**
   - Check AuthContext is fetching user data correctly
   - Verify backend `/api/users/me` endpoint is accessible
   - Check browser console for API errors
   - Ensure `REACT_APP_API_URL` matches backend URL during build

3. **Code changes not reflecting:**
   - Code is mounted from host, so changes sync automatically
   - But pods need restart: `kubectl rollout restart deployment/<name> -n zeroqwait`
   - Frontend requires rebuild: Delete pod to trigger fresh npm build

### Deployment Workflow

1. **Make code changes locally** in your development environment
2. **Test locally** using Docker Compose
3. **Push to Git** (if using version control)
4. **SSH to production server**: `ssh neekrishrichu@192.168.2.88`
5. **Update code on server**: `cd ~/apps/zeroqwait && git pull` (or manually copy files)
6. **Restart pods**: `kubectl rollout restart deployment/backend -n zeroqwait`
7. **Verify**: Check logs and access the application
