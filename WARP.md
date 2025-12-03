# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

ZeroQwait (zeroqwait.com) is a universal queue management system for various service providers including barbershops, salons, clinics, and more. It's built with a modern full-stack architecture using FastAPI for the backend and React with TypeScript for the frontend. The platform enables businesses to create and manage queues while customers can check in online and view real-time wait times.

## Architecture

### High-Level Structure
- **Full-stack web application** with separate backend and frontend services
- **Containerized deployment** using Docker Compose with three services: database, backend, and frontend
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

### Full Application (Recommended for Development)
```bash
# Start all services (database, backend, frontend)
docker-compose up

# Start in detached mode
docker-compose up -d

# Stop all services
docker-compose down

# Rebuild containers after code changes
docker-compose up --build
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

### Required Environment Variables
- `DATABASE_URL`: PostgreSQL connection string (handled by Docker Compose)
- `SECRET_KEY`: JWT token signing key (set in docker-compose.yml)

### Default Ports
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database**: localhost:5432

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
- **Docker Compose**: Multi-container development environment
- **PostgreSQL**: Production-grade relational database