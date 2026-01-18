#!/bin/bash

# Test script for queue serve functionality
BASE_URL="http://localhost:8000/api"

echo "🧪 Testing Queue Serve Functionality"
echo "======================================"
echo ""

# Create test employee account
EMPLOYEE_USER="testemployee_$(date +%s)"
EMPLOYEE_EMAIL="emp_$(date +%s)@test.com"

echo "1️⃣  Creating test employee account..."
curl -s -X POST "$BASE_URL/users" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMPLOYEE_EMAIL\",\"username\":\"$EMPLOYEE_USER\",\"password\":\"test123\",\"role\":\"employee\"}" > /dev/null

# Login as employee
echo "2️⃣  Logging in as employee..."
login_response=$(curl -s -X POST "$BASE_URL/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$EMPLOYEE_USER&password=test123")

TOKEN=$(echo $login_response | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to login"
    exit 1
fi
echo "✅ Login successful"
echo ""

# Get shop 1 queue
echo "3️⃣  Getting current queue state..."
queue_before=$(curl -s "$BASE_URL/queues/shop/1/active")
echo "$queue_before" | python3 -m json.tool
echo ""

# Add test customers
echo "4️⃣  Adding test customers to queue..."
customer1=$(curl -s -X POST "$BASE_URL/queues/shop/1/join" \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Test Serve 1","customer_phone":"5551111111"}')
CUSTOMER1_ID=$(echo $customer1 | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "   Added customer 1 (ID: $CUSTOMER1_ID)"

customer2=$(curl -s -X POST "$BASE_URL/queues/shop/1/join" \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Test Serve 2","customer_phone":"5552222222"}')
CUSTOMER2_ID=$(echo $customer2 | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "   Added customer 2 (ID: $CUSTOMER2_ID)"

customer3=$(curl -s -X POST "$BASE_URL/queues/shop/1/join" \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Test Serve 3","customer_phone":"5553333333"}')
CUSTOMER3_ID=$(echo $customer3 | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "   Added customer 3 (ID: $CUSTOMER3_ID)"
echo ""

# Test Scenario 1: Serve a specific customer (skip queue)
echo "5️⃣  SCENARIO 1: Serving customer 2 (skip queue)..."
serve_response=$(curl -s -X POST "$BASE_URL/queues/items/$CUSTOMER2_ID/serve" \
  -H "Authorization: Bearer $TOKEN")
echo "   Response:"
echo "$serve_response" | python3 -m json.tool
echo ""

echo "   Checking queue state after serving customer 2..."
queue_after_serve=$(curl -s "$BASE_URL/queues/shop/1/active")
serving_count=$(echo "$queue_after_serve" | grep -o '"status": "being_served"' | wc -l)
served_customer=$(echo "$queue_after_serve" | grep -B5 '"status": "being_served"' | grep '"customer_name"' | head -1 | cut -d'"' -f4)

echo "   Currently being served: $served_customer"
echo "   Number of customers being served: $serving_count"

if [ "$serving_count" -eq 1 ] && [ "$served_customer" = "Test Serve 2" ]; then
    echo "   ✅ PASSED: Customer 2 is now being served (1 customer only)"
else
    echo "   ❌ FAILED: Expected 1 customer (Test Serve 2) being served, got $serving_count"
fi
echo ""

# Test Scenario 2: Call next customer
echo "6️⃣  SCENARIO 2: Calling next customer in line..."
queue_response=$(curl -s "$BASE_URL/queues/shop/1/active")
QUEUE_ID=$(echo $queue_response | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

call_next_response=$(curl -s -X POST "$BASE_URL/queues/$QUEUE_ID/call-next" \
  -H "Authorization: Bearer $TOKEN")
echo "   Response:"
echo "$call_next_response" | python3 -m json.tool
echo ""

echo "   Checking queue state after calling next..."
queue_after_next=$(curl -s "$BASE_URL/queues/shop/1/active")
serving_count2=$(echo "$queue_after_next" | grep -o '"status": "being_served"' | wc -l)
serving_names=$(echo "$queue_after_next" | grep -B5 '"status": "being_served"' | grep '"customer_name"' | cut -d'"' -f4)

echo "   Currently being served: $serving_names"
echo "   Number of customers being served: $serving_count2"

if [ "$serving_count2" -eq 1 ]; then
    echo "   ✅ PASSED: Only 1 customer being served after call-next"
else
    echo "   ❌ FAILED: Expected 1 customer being served, got $serving_count2"
fi
echo ""

# Final queue state
echo "7️⃣  Final queue state:"
curl -s "$BASE_URL/queues/shop/1/active" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"\\n{'='*60}\")
print(f\"Queue: {data['name']}\")
print(f\"{'='*60}\")
for item in data['queue_items']:
    if item['status'] in ['waiting', 'being_served']:
        status_icon = '🟢' if item['status'] == 'being_served' else '⏳'
        print(f\"{status_icon} #{item['position']:2d} | {item['customer_name']:20s} | Status: {item['status']}\")
print(f\"{'='*60}\\n\")
"

echo "✅ Testing complete!"
