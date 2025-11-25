# Supabase Migration Guide

## Migration Complete! ✅

Your FastAPI backend has been successfully migrated from SQLAlchemy + PostgreSQL to Supabase.

## What Changed

### Removed
- ❌ PostgreSQL Docker container
- ❌ `backend/database.py` (SQLAlchemy engine)
- ❌ `backend/models.py` (SQLAlchemy ORM models)
- ❌ SQLAlchemy and psycopg2-binary dependencies

### Added
- ✅ `backend/supabase_client.py` - Supabase client with helper functions
- ✅ `supabase_schema.sql` - Database schema for Supabase
- ✅ `supabase-py` dependency
- ✅ Supabase Storage integration for shop logos

### Modified
- 🔄 All routers (auth, users, shops, queues, haircuts, subscriptions, analytics, uploads)
- 🔄 `auth_utils.py` - Uses Supabase queries
- 🔄 `schemas.py` - Updated to Pydantic v2 (`from_attributes=True`)
- 🔄 `main.py` - Removed SQLAlchemy table creation
- 🔄 `docker-compose.yml` - Removed PostgreSQL service
- 🔄 `requirements.txt` & `pyproject.toml` - Updated dependencies

## Setup Instructions

### 1. Set Up Supabase Database

1. Go to your Supabase project: https://supabase.com/dashboard/project/yuxfpspyzyhesfuspjns
2. Navigate to **SQL Editor**
3. Copy the entire contents of `supabase_schema.sql`
4. Paste and run it in the SQL Editor
5. Verify tables were created in **Database** → **Tables**

### 2. Create Storage Bucket for Shop Logos

1. Navigate to **Storage** in Supabase dashboard
2. Create a new bucket:
   - Name: `shop-logos`
   - Public: ✅ Yes (for public logo access)
3. Click **Create bucket**

### 3. Get Your Supabase Service Role Key

1. Go to **Settings** → **API**
2. Find **service_role** key (NOT the anon key!)
3. Copy it (it starts with `eyJ...`)
4. Update `.env` file:
   ```bash
   SUPABASE_KEY=your_actual_service_role_key_here
   ```

### 4. Install Dependencies

```bash
cd /Users/neekrish/FastCuts/backend
pip install supabase==2.3.0
# or if using PDM:
pdm install
```

### 5. Test the Backend

#### Option A: Run without Docker
```bash
cd /Users/neekrish/FastCuts/backend
export SUPABASE_URL="https://yuxfpspyzyhesfuspjns.supabase.co"
export SUPABASE_KEY="your_service_role_key"
export SECRET_KEY="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Option B: Run with Docker
```bash
cd /Users/neekrish/FastCuts
# Make sure SUPABASE_KEY is set in your .env file
docker-compose up backend
```

## Testing API Endpoints

### 1. Check Health
```bash
curl http://localhost:8000/
```
Expected: `{"message":"Welcome to Universal Queue System API"}`

### 2. View API Documentation
Open: http://localhost:8000/docs

### 3. Create a Test User
```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpass123",
    "role": "customer"
  }'
```

### 4. Login
```bash
curl -X POST http://localhost:8000/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass123"
```

Save the `access_token` from response.

### 5. Get Current User
```bash
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 6. Get Haircut Services
```bash
curl http://localhost:8000/api/haircuts
```

### 7. Get All Shops
```bash
curl http://localhost:8000/api/shops/
```

### 8. Create a Shop (as shop owner)
First create a shop owner account, then:
```bash
curl -X POST http://localhost:8000/api/shops/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Barbershop",
    "shop_type": "barber",
    "address": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "country": "United States",
    "phone": "555-123-4567"
  }'
```

## Verification Checklist

- [ ] Database schema created in Supabase
- [ ] Storage bucket `shop-logos` created
- [ ] `.env` file updated with SUPABASE_KEY
- [ ] Dependencies installed
- [ ] Backend starts without errors
- [ ] Can create users
- [ ] Can login and get JWT token
- [ ] Can access protected endpoints
- [ ] Can create shops (as shop owner)
- [ ] Can join queues
- [ ] All API endpoints return expected responses

## Common Issues & Solutions

### Issue: "SUPABASE_KEY environment variable is required"
**Solution**: Make sure SUPABASE_KEY is set in `.env` file or environment variables

### Issue: "Failed to connect to Supabase"
**Solution**: 
- Check internet connection
- Verify SUPABASE_URL is correct
- Ensure service role key (not anon key) is being used

### Issue: Import errors for `models` or `database`
**Solution**: 
- Make sure all routers import from `supabase_client` not `database`
- Check that no files are importing from the removed `models.py`

### Issue: "Table does not exist"
**Solution**: Run the `supabase_schema.sql` script in Supabase SQL Editor

### Issue: RLS (Row Level Security) blocking queries
**Solution**: Using service role key bypasses RLS. If issues persist, check RLS policies in Supabase dashboard

## Performance Notes

- Supabase auto-commits all changes (no manual commit needed)
- Consider adding indexes for frequently queried columns
- Use `.select()` with specific columns instead of `*` for better performance
- Batch operations when possible

## Next Steps

1. **Test all features thoroughly** - Try every user flow
2. **Monitor Supabase Dashboard** - Check for query performance
3. **Set up backup strategy** - Enable Supabase automated backups
4. **Configure RLS properly** - Fine-tune Row Level Security policies
5. **Add error logging** - Integrate Sentry or similar for production

## Rollback Plan

If you need to rollback to SQLAlchemy:
1. The old files are backed up as `*_old.py`
2. Restore from git: `git checkout HEAD -- backend/`
3. Restart PostgreSQL container

## Support

- Supabase Docs: https://supabase.com/docs
- Supabase Python Client: https://supabase.com/docs/reference/python/introduction
- Project Dashboard: https://supabase.com/dashboard/project/yuxfpspyzyhesfuspjns
