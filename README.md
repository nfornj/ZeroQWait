# FastCuts

A web application for finding and saving nearby haircut services, similar to Great Clips.

## Features

- Search for nearby haircut services
- View details about each service (location, hours, ratings, etc.)
- Save favorite haircut services to a personal list
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
FastCuts/
├── backend/            # FastAPI application
├── frontend/           # React application
├── docker-compose.yml  # Docker Compose configuration
└── README.md           # Project documentation
```
