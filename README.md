# ZeroQwait

A universal queue management system for service providers including barbershops, salons, clinics, and more. Customers can check in online and view real-time wait times.

**Live at: https://zeroqwait.com**

## Features

- Service providers can register and create their queue systems
- Real-time queue management dashboard for shops
- Customer check-in and live queue viewing
- Estimated wait time calculations
- Multi-tenant architecture supporting various service types
- User authentication

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React (TypeScript)
- **Database**: PostgreSQL
- **Containerization**: Docker & Docker Compose

## Getting Started

### Prerequisites

- Docker and Docker Compose installed on your machine

### Running the Application

1. Clone this repository
2. Run the following command in the project root:

```bash
docker-compose up
```

3. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Project Structure

```
ZeroQwait/
├── backend/            # FastAPI application
├── frontend/           # React application
├── docker-compose.yml  # Docker Compose configuration
└── README.md           # Project documentation
```
