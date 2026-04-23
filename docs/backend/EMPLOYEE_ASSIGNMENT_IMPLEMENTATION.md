# Employee Assignment Implementation Summary

## Overview
This note documents the employee-assignment feature in the service workflow. The feature lets shop staff or owners associate an in-progress customer with a specific employee, or fall back to an automatic assignment strategy.

## Files Created

### 1. Database Migration
**`backend/sql/add_employee_assignment.sql`**
- Adds `assigned_employee_id` column to `queue_items` table
- Creates index for performance
- Foreign key reference to `users` table

### 2. Frontend Component
**`frontend/src/components/EmployeeSelector.tsx`**
- Dialog component for selecting employees
- Options for random assignment or specific employee selection
- Shows clocked-in employees with avatars and online status
- Displays time since clock-in for each employee

## Files Modified

### Backend Changes

#### 1. Schemas (`backend/schemas.py`)
- Updated `QueueItem` schema to include:
  - `assigned_employee_id: Optional[int]`
  - `assigned_employee: Optional[dict]` (for nested employee details)

#### 2. Employee Endpoints (`backend/routers/employees.py`)
- **New Endpoint**: `GET /api/employees/shops/{shop_id}/clocked-in`
  - Returns list of employees currently on shift
  - Available to shop owners and employees
  - Includes user details (username, email, profile photo, clock-in time)

#### 3. Queue Endpoints (`backend/routers/queues.py`)
- **Added Helper Function**: `populate_employee_details()`
  - Efficiently fetches employee details for queue items
  - Batch retrieves employee information to minimize database queries

- **Modified**: `get_active_queue()`
  - Now includes employee details in queue items

- **Modified**: `get_all_shop_queues()`
  - Now includes employee details in all queue items

- **Modified**: `call_next_customer()`
  - Accepts optional `employee_id` parameter
  - **Random Assignment Logic**:
    - If `employee_id` is None: randomly selects from clocked-in employees
    - If no employees clocked in: assigns to shop owner
  - Updates queue item with assigned employee
  - Returns employee details with the queue item

- **Modified**: `serve_specific_customer()`
  - Accepts optional `employee_id` parameter
  - Assigns employee when serving out-of-order customer
  - Defaults to current user if no employee specified

### Frontend Changes

#### 1. Shop Dashboard (`frontend/src/pages/ShopDashboardPage.tsx`)
- **Added State Variables**:
  - `employees`: List of clocked-in employees
  - `employeeSelectorOpen`: Dialog open/close state
  - `loadingEmployees`: Loading state for employee fetch

- **Added Interfaces**:
  - `Employee`: Type for clocked-in employee data
  - Updated `QueueItem` to include employee assignment fields

- **New Function**: `fetchClockedInEmployees()`
  - Fetches list of currently clocked-in employees
  - Refreshes every 5 seconds along with queue data

- **Modified**: `handleCallNext()`
  - Now opens employee selector dialog instead of immediately calling next

- **New Function**: `handleEmployeeSelected()`
  - Calls backend with selected employee ID
  - Sends null for random assignment
  - Passes employee_id as query parameter

- **Updated "Being Served" Display**:
  - Shows employee avatar and name
  - Displays "Served by [employee name]" for each customer
  - Visual indicator with PersonIcon

- **Added Component**: `<EmployeeSelector />` dialog
  - Shown when "Call Next" is clicked
  - Allows selection of specific employee or random assignment

#### 2. In-Shop Display (`frontend/src/pages/InShopDisplayPage.tsx`)
- **Updated `QueueItem` Interface**:
  - Added `assigned_employee` field with employee details

- **Updated "Now Serving" Section**:
  - Shows employee avatar (60x60px)
  - Displays "Served by [employee name]"
  - Only shown when employee is assigned
  - Aligned with customer information

## Features Implemented

### 1. Employee Assignment on Call Next
- Business owner clicks "Call Next"
- Dialog opens showing clocked-in employees
- Two options:
  - **Random Assignment** (default): Randomly selects from available employees
  - **Select Specific Employee**: Choose a particular employee
- If no employees clocked in: assigns to shop owner automatically

### 2. Visual Employee Display
- **Dashboard "Being Served" Section**:
  - Employee avatar next to customer
  - "Served by [name]" text
  - Clear visual association

- **In-Shop Display**:
  - Large employee avatar (60x60px)
  - "Served by" label
  - Employee name in bold
  - Positioned below customer information

### 3. Random Assignment Logic
When no employee is specified:
1. Queries for employees currently clocked in at the shop
2. If employees found: randomly selects one
3. If no employees: assigns to shop owner
4. Ensures someone is always assigned to serve

### 4. Real-time Employee Status
- List refreshes every 5 seconds
- Shows online status with green chip
- Displays "Clocked in Xm ago" or "Xh ago"
- Only shows actively clocked-in employees

## Database Schema Addition

```sql
ALTER TABLE queue_items 
ADD COLUMN assigned_employee_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX idx_queue_items_assigned_employee ON queue_items(assigned_employee_id);
```

## API Changes

### New Endpoint
```
GET /api/employees/shops/{shop_id}/clocked-in
```
**Response:**
```json
[
  {
    "shift_id": 1,
    "user_id": 5,
    "username": "john_barber",
    "email": "john@example.com",
    "profile_photo_url": "https://...",
    "clock_in": "2025-11-25T10:00:00Z"
  }
]
```

### Modified Endpoint
```
POST /api/queues/{queue_id}/call-next?employee_id={employee_id}
```
**Parameters:**
- `employee_id` (optional): ID of employee to assign
- If omitted or null: random assignment

**Response:**
```json
{
  "id": 123,
  "customer_name": "John Doe",
  "position": 1,
  "status": "being_served",
  "assigned_employee_id": 5,
  "assigned_employee": {
    "id": 5,
    "username": "john_barber",
    "email": "john@example.com",
    "profile_photo_url": "https://..."
  }
}
```

## Setup Instructions

### 1. Run The Database Migration

Apply the migration against the active PostgreSQL database used by the backend.

```bash
psql "$DATABASE_URL" -f backend/sql/add_employee_assignment.sql
```

### 2. Restart The Backend
```bash
# If using the non-prod Compose stack
docker compose restart backend

# If running locally from source
cd backend
uv sync --dev
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend is Ready
No additional setup needed. Changes are in the code.

## Testing Checklist

- [ ] Clock in employees at a shop
- [ ] Verify clocked-in employees appear in selector
- [ ] Test random assignment (don't select employee)
- [ ] Test specific employee assignment
- [ ] Verify employee name shows in "Being Served" section
- [ ] Check in-shop display shows employee name
- [ ] Test with no employees clocked in (should assign to owner)
- [ ] Verify employee details refresh automatically
- [ ] Test completing service (employee assignment persists in history)

## Benefits

### For Business Owners
- **Fair Distribution**: Random assignment ensures even workload
- **Flexibility**: Can assign specific employees when needed
- **Visibility**: See who is serving each customer
- **Accountability**: Track which employee served which customer

### For Employees
- **Clarity**: Know which customers are assigned to them
- **Organization**: Better workflow management
- **Recognition**: Customers see who is serving them

### For Customers
- **Personal Connection**: Know who is serving them
- **Trust**: See employee accountability
- **Communication**: Can refer to employee by name

## Future Enhancements

1. **Employee Preferences**: Allow customers to request specific employees
2. **Performance Tracking**: Analytics on employee service times
3. **Multiple Assignments**: Support multiple employees per customer (e.g., assistant)
4. **Employee Skills**: Match customers to employees based on service type
5. **Shift Management**: Automatic clock-in/out with geofencing
6. **Commission Tracking**: Track services completed by each employee
7. **Customer Notes**: Add notes about preferred employees
8. **Notifications**: Alert employees when assigned to new customer

## Known Limitations

1. Random assignment uses simple random selection (no load balancing)
2. Employee photos must be manually uploaded
3. Clock-in/out must be done manually through the system
4. No way to reassign customer to different employee after initial assignment
5. Assignment history not yet tracked in analytics

## Troubleshooting

### Employees Not Showing in Selector
- Verify employees are clocked in (check employee_shifts table)
- Ensure employee has active status in shop_employees table
- Check API endpoint returns data: `GET /api/employees/shops/{shop_id}/clocked-in`

### Assignment Not Saving
- Verify migration ran successfully
- Check `assigned_employee_id` column exists in queue_items table
- Review backend logs for errors

### Random Assignment Always Assigns Owner
- Check if any employees are actually clocked in
- Verify clock-out time is NULL in employee_shifts table
- Test employee clock-in endpoint

## API Documentation Update Needed

Update your API documentation (if any) to reflect:
1. New employee_id parameter for call-next endpoint
2. New clocked-in employees endpoint
3. Employee details in queue item responses
