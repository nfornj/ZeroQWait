# Employee Management System - Setup Instructions

## ✅ What's Been Implemented

1. **Database Schema** - SQL script created
2. **Backend Schemas** - Employee role and schemas added
3. **Permissions System** - Role-based access control module
4. **Employee API Endpoints** - Full CRUD for employee management
5. **Router Integration** - Employees router added to main app

## 🔧 What You Need to Do

### Step 1: Create Database Table in Supabase

1. Go to your Supabase dashboard: https://supabase.com/dashboard
2. Select your project (`yuxfpspyzyhesfuspjns`)
3. Go to **SQL Editor** in the left sidebar
4. Copy and paste the SQL from `backend/sql/create_shop_employees_table.sql`:

```sql
CREATE TABLE IF NOT EXISTS shop_employees (
  id SERIAL PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_by INTEGER REFERENCES users(id),
  is_active BOOLEAN DEFAULT TRUE,
  UNIQUE(shop_id, user_id)
);

CREATE INDEX idx_shop_employees_shop_id ON shop_employees(shop_id);
CREATE INDEX idx_shop_employees_user_id ON shop_employees(user_id);
CREATE INDEX idx_shop_employees_is_active ON shop_employees(is_active);
```

5. Click **Run** to execute
6. Verify the table was created in the **Table Editor**

### Step 2: Rebuild and Restart Backend

```bash
cd /Users/neekrish/FastCuts
docker-compose down backend
docker-compose build --no-cache backend
docker-compose up -d backend
```

### Step 3: Test the New Endpoints

Visit http://localhost:8000/docs to see the new Employee endpoints:

#### New API Endpoints

**Employee Management** (Owner only):
- `POST /api/shops/{shop_id}/employees` - Add employee
- `GET /api/shops/{shop_id}/employees` - List employees
- `DELETE /api/shops/{shop_id}/employees/{employee_id}` - Remove employee
- `PUT /api/shops/{shop_id}/employees/{employee_id}/reactivate` - Reactivate employee

**Employee Dashboard**:
- `GET /api/employees/my-shops` - Get shops for current employee

## 📋 Testing Checklist

### Test 1: Create a Shop (if you don't have one)
```bash
curl -X POST "http://localhost:8000/api/shops/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Barber Shop",
    "description": "Test shop for employee management",
    "shop_type": "barbershop",
    "address": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "country": "United States",
    "phone": "555-1234"
  }'
```

### Test 2: Add an Employee
```bash
curl -X POST "http://localhost:8000/api/shops/1/employees" \
  -H "Authorization: Bearer YOUR_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "employee1",
    "email": "employee1@test.com",
    "password": "employeepass123"
  }'
```

### Test 3: List Employees
```bash
curl -X GET "http://localhost:8000/api/shops/1/employees" \
  -H "Authorization: Bearer YOUR_OWNER_TOKEN"
```

### Test 4: Employee Login
```bash
curl -X POST "http://localhost:8000/api/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=employee1&password=employeepass123"
```

### Test 5: Employee Access Their Shops
```bash
curl -X GET "http://localhost:8000/api/employees/my-shops" \
  -H "Authorization: Bearer EMPLOYEE_TOKEN"
```

## 🔐 Permission System

### Role Hierarchy

**Shop Owner**:
- ✅ Full access to their shops
- ✅ Can add/remove employees
- ✅ Can manage queues
- ✅ Can modify shop settings
- ✅ Can view analytics

**Employee**:
- ✅ Can view assigned shop details
- ✅ Can manage queue items (serve customers)
- ❌ Cannot add/remove employees
- ❌ Cannot modify shop settings
- ❌ Cannot view analytics
- ❌ Cannot access other shops

**Customer**:
- ✅ Can join queues
- ❌ Cannot manage queues
- ❌ Cannot access shop management

## 🚀 Next Steps (Queue Permissions Update)

The queue endpoints still need to be updated to use the new permission system. This is next on the todo list.

After that's done, employees will be able to:
1. Call the next customer in queue
2. Update queue item status (waiting → being_served → completed)
3. View all queue items

But employees will NOT be able to:
1. Create/delete queues
2. Modify shop settings
3. View analytics

## 📝 Frontend Integration (Coming Soon)

Once backend is tested, you'll need to:
1. Create EmployeeManagementPage for shop owners
2. Add employee list/add/remove UI
3. Create simplified employee dashboard
4. Add role-based navigation

## 🐛 Troubleshooting

### Table creation fails
- Check that shops and users tables exist first
- Verify you're using the service_role key, not anon key
- Check Supabase logs for errors

### Employee creation fails
- Check that shop_employees table was created
- Verify the shop owner is authenticated
- Check backend logs: `docker-compose logs backend`

### Permission errors
- Make sure the shop_employees link exists and is_active=true
- Verify the employee is using the correct shop_id
- Check that the user role is set to "employee"

## 📚 API Documentation

After restarting, visit:
- API Docs: http://localhost:8000/docs
- OpenAPI Schema: http://localhost:8000/openapi.json

The new Employee section will appear with all endpoints documented.
