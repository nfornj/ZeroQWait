# 🔧 Supabase Setup Guide

## ⚠️ Current Issue

The Supabase URL in your `.env` file (`yuxfpspyzyhesfuspjns.supabase.co`) **does not exist**. 
This project was likely deleted or the URL is incorrect.

## ✅ What's Working

- ✓ **Email Configuration**: SMTP is fully configured and working
- ✓ **Backend API**: Running successfully on port 8000
- ✓ **Frontend**: Running on port 3000
- ✓ **Docker Setup**: All containers are working

## 🚀 Fix Steps

### Option 1: Create a New Supabase Project (Recommended)

1. **Go to Supabase**: https://supabase.com/dashboard

2. **Create a new project**:
   - Click "New Project"
   - Choose organization
   - Enter project name: "FastCuts" or "ZeroQwait"
   - Enter a strong database password (save it!)
   - Choose a region close to you
   - Wait for project to finish setting up (~2 minutes)

3. **Get your credentials**:
   - Go to Project Settings > API
   - Copy the following:
     - **Project URL**: `https://xxxxx.supabase.co`
     - **Service Role Key**: `eyJhbG...` (the long one under "service_role")
     - **Anon Key**: `eyJhbG...` (under "anon" key)

4. **Update your `.env` file** (`backend/.env`):
   ```bash
   # Replace these lines with your new values
   SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
   SUPABASE_KEY=your_service_role_key_here
   SUPABASE_ANON_KEY=your_anon_key_here
   
   # Also update DATABASE_URL
   DATABASE_URL=postgresql://postgres:YOUR_DB_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
   ```

5. **Create the database tables**:
   ```bash
   cd /Users/neekrish/FastCuts
   docker-compose restart backend
   
   # Wait 5 seconds for backend to start
   sleep 5
   
   # Run the table creation script
   docker exec fastcuts-backend-1 python create_supabase_tables.py
   ```

6. **Restart services**:
   ```bash
   docker-compose restart
   ```

7. **Run the comprehensive test**:
   ```bash
   cd /Users/neekrish/FastCuts/backend
   python3 comprehensive_test.py
   ```

### Option 2: Use Local PostgreSQL (Alternative)

If you prefer not to use Supabase, you can set up a local PostgreSQL database:

1. **Add PostgreSQL to docker-compose.yml**:
   ```yaml
   db:
     image: postgres:15
     environment:
       POSTGRES_USER: postgres
       POSTGRES_PASSWORD: postgres
       POSTGRES_DB: fastcuts
     ports:
       - "5432:5432"
     volumes:
       - postgres_data:/var/lib/postgresql/data
   
   volumes:
     postgres_data:
   ```

2. **Update `.env`**:
   ```bash
   DATABASE_URL=postgresql://postgres:postgres@db:5432/fastcuts
   ```

3. **Modify code** to use SQLAlchemy instead of Supabase client (more work required)

## 📊 Current Configuration Status

### ✅ Working
- Email: `nfornj@gmail.com`
- SMTP: Configured and tested
- Backend API: Running on http://localhost:8000
- Frontend: Running on http://localhost:3000

### ❌ Not Working
- Supabase: Invalid project URL
- Database: Cannot connect

## 🧪 Test Email Functionality

Even though Supabase is not working, you can test email:

```bash
cd /Users/neekrish/FastCuts/backend
python3 test_smtp.py
```

## 📞 Next Steps

1. Create a new Supabase project (takes 5 minutes)
2. Update the `.env` file with new credentials
3. Create database tables
4. Run comprehensive test
5. Start using the application!

## 📝 Useful Commands

```bash
# Check if services are running
docker-compose ps

# View backend logs
docker-compose logs -f backend

# Restart services
docker-compose restart

# Stop services
docker-compose down

# Start services
docker-compose up -d

# Access backend shell
docker exec -it fastcuts-backend-1 bash

# Test API
curl http://localhost:8000/

# View API docs
open http://localhost:8000/docs
```

## 🔐 Security Note

Your `.env` file contains actual credentials. Make sure:
- Never commit `.env` to git (it's in `.gitignore`)
- Keep your service role key secret
- Use environment variables in production
