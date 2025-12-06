# ZeroQwait

A universal queue management system for service providers including barbershops, salons, clinics, and more. Customers can check in online and view real-time wait times.

**Live at: https://zeroqwait.com** (Self-hosted on Raspberry Pi)

## Features

- Service providers can register and create their queue systems
- Real-time queue management dashboard for shops
- Customer check-in and live queue viewing
- Estimated wait time calculations
- Multi-tenant architecture supporting various service types
- User authentication and authorization
- Email notifications
- Analytics and reporting

## Tech Stack

- **Backend**: FastAPI (Python) with Uvicorn
- **Frontend**: React (TypeScript) with Material-UI
- **Database**: Supabase (PostgreSQL)
- **Containerization**: Docker & Docker Compose
- **Reverse Proxy**: Nginx with SSL/TLS
- **Deployment**: Self-hosted on Raspberry Pi

## Getting Started

### Prerequisites

- Docker and Docker Compose installed on your machine
- Node.js 16+ (for local development)
- Python 3.9+ (for local development)

### Local Development

1. Clone this repository:
```bash
git clone <your-repo-url>
cd FastCuts
```

2. Set up backend environment:
```bash
cd backend
cp .env.example .env  # Edit with your configuration
pdm install  # Or: pip install -r requirements.txt
```

3. Set up frontend environment:
```bash
cd frontend
npm install
```

4. Run with Docker Compose:
```bash
docker-compose up
```

5. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Production Deployment (Raspberry Pi)

For deploying to Raspberry Pi, see **[RASPBERRY_PI_DEPLOYMENT.md](RASPBERRY_PI_DEPLOYMENT.md)** for comprehensive instructions.

Quick deployment:
```bash
# From your local machine
./deploy-pi.sh
```

## Project Structure

```
ZeroQwait/
├── backend/                      # FastAPI application
│   ├── routers/                  # API route handlers
│   ├── models.py                 # Database models
│   ├── schemas.py                # Pydantic schemas
│   ├── auth_utils.py             # Authentication utilities
│   ├── main.py                   # Application entry point
│   └── Dockerfile                # Backend container config
├── frontend/                     # React application
│   ├── src/
│   │   ├── components/           # Reusable UI components
│   │   ├── pages/                # Page components
│   │   ├── services/             # API services
│   │   └── App.tsx               # Main app component
│   ├── nginx.conf                # Nginx configuration
│   └── Dockerfile                # Frontend container config
├── docker-compose.yml            # Development environment
├── docker-compose.prod.yml       # Production environment
├── deploy-pi.sh                  # Deployment script
├── RASPBERRY_PI_DEPLOYMENT.md    # Deployment guide
└── README.md                     # This file
```

## Documentation

- **[RASPBERRY_PI_DEPLOYMENT.md](RASPBERRY_PI_DEPLOYMENT.md)** - Complete Raspberry Pi deployment guide
- **[WARP.md](WARP.md)** - Development guidelines for AI assistants

## Development Workflow

### Backend Development

```bash
cd backend
pdm run start  # Start with auto-reload
pdm run test   # Run tests
pdm run lint   # Run linter
```

### Frontend Development

```bash
cd frontend
npm start      # Start development server
npm test       # Run tests
npm run build  # Build for production
```

## API Endpoints

- `GET /api/` - Health check
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/shops` - List all shops
- `POST /api/shops` - Create new shop
- `GET /api/queues/{shop_id}` - Get shop queue
- `POST /api/queues/{shop_id}/join` - Join queue

Full API documentation: https://zeroqwait.com/docs

## Environment Variables

### Backend (.env)

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SECRET_KEY=your_secret_key_for_jwt
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email
EMAIL_PASSWORD=your_app_password
FRONTEND_URL=https://zeroqwait.com
```

### Frontend (.env.production)

```env
REACT_APP_API_URL=/api
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Support

For issues or questions, please open an issue on GitHub.
