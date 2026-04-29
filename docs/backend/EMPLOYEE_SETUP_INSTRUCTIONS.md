# Employee Management Setup

This document reflects the current employee-management surface in ZeroQwait.

## Overview

Employee management is part of the active backend and does not require an external SQL-editor workflow.

Current employee-related behavior includes:

- shop owners adding and removing employees from a shop
- employees viewing assigned shops
- employee shift clock-in and clock-out
- employee profile photo updates
- owner and employee permission boundaries enforced through the backend permission layer

## Current Endpoints

### Owner-Only Employee Management

- `POST /api/shops/{shop_id}/employees`
- `GET /api/shops/{shop_id}/employees`
- `DELETE /api/shops/{shop_id}/employees/{employee_id}`
- `PUT /api/shops/{shop_id}/employees/{employee_id}/reactivate`

### Employee Dashboard And Shift Endpoints

- `GET /api/employees/my-shops`
- `GET /api/current-shift`
- `POST /api/clock-in/{shop_id}`
- `POST /api/clock-out`
- `POST /api/upload-profile-photo`

These routes are implemented in `backend/modules/employees/router.py`.

## Local Setup

1. Start the support services:

```bash
docker compose up -d db redis booking-mcp finance-mcp hr-mcp odoo
```

2. Start the backend:

```bash
cd backend
uv sync --dev
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

3. Open the API docs:

- `http://localhost:8000/docs`

## Manual Validation Flow

### 1. Create or use a shop-owner account

Authenticate through:

```text
POST /api/auth/token
```

### 2. Add an employee to a shop

```bash
curl -X POST "http://localhost:8000/api/shops/1/employees" \
  -H "Authorization: Bearer YOUR_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "employee1",
    "email": "employee1@test.com",
    "password": "employeepass123",
    "role": "employee"
  }'
```

### 3. List shop employees

```bash
curl -X GET "http://localhost:8000/api/shops/1/employees" \
  -H "Authorization: Bearer YOUR_OWNER_TOKEN"
```

### 4. Sign in as the employee

```bash
curl -X POST "http://localhost:8000/api/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=employee1&password=employeepass123"
```

### 5. Verify employee shop access

```bash
curl -X GET "http://localhost:8000/api/employees/my-shops" \
  -H "Authorization: Bearer EMPLOYEE_TOKEN"
```

### 6. Verify shift actions

```bash
curl -X POST "http://localhost:8000/api/clock-in/1" \
  -H "Authorization: Bearer EMPLOYEE_TOKEN"
```

```bash
curl -X POST "http://localhost:8000/api/clock-out" \
  -H "Authorization: Bearer EMPLOYEE_TOKEN"
```

## Permission Model

### Shop Owners

- can add, list, remove, and reactivate employees for their own shops
- can access owner-only operational and analytics surfaces

### Employees

- can access only assigned shops
- can use employee-facing shift and profile actions
- cannot perform owner-only shop administration

### Customers And Public Users

- cannot access employee management endpoints

## Agent Context

Employee and staffing workflows also appear in the owner-facing agent experience through the HR specialist. That path is complementary to the direct REST endpoints above.

## Troubleshooting

### Employee creation fails

- verify the owner token belongs to the target shop owner
- verify the username and email are not already taken
- check backend logs for service-level errors

### Employee cannot access a shop

- verify the employee is linked to that shop and marked active
- verify the employee is using the correct token

### Shift endpoints fail

- verify the user role is `employee`
- verify the employee is assigned to the shop before clock-in
