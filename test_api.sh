#!/bin/bash

# FastCuts API Testing Script
# This script tests all major API endpoints after Supabase migration

BASE_URL="http://localhost:8000"
API_URL="${BASE_URL}/api"

echo "🚀 FastCuts API Testing Script"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to test an endpoint
test_endpoint() {
    local name="$1"
    local method="$2"
    local url="$3"
    local data="$4"
    local headers="$5"
    local expected_status="$6"
    
    echo -n "Testing: $name... "
    
    if [ "$method" = "POST" ]; then
        if [ -z "$headers" ]; then
            response=$(curl -s -w "\n%{http_code}" -X POST "$url" -H "Content-Type: application/json" -d "$data")
        else
            response=$(curl -s -w "\n%{http_code}" -X POST "$url" -H "Content-Type: application/json" -H "$headers" -d "$data")
        fi
    else
        if [ -z "$headers" ]; then
            response=$(curl -s -w "\n%{http_code}" "$url")
        else
            response=$(curl -s -w "\n%{http_code}" "$url" -H "$headers")
        fi
    fi
    
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (HTTP $http_code)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (Expected $expected_status, got $http_code)"
        echo "  Response: $body"
        ((FAILED++))
        return 1
    fi
}

echo "1️⃣  Health Check"
test_endpoint "Root endpoint" "GET" "$BASE_URL/" "" "" "200"
echo ""

echo "2️⃣  User Management"
# Generate random username to avoid conflicts
RANDOM_NUM=$RANDOM
TEST_USER="testuser_${RANDOM_NUM}"
TEST_EMAIL="test_${RANDOM_NUM}@example.com"

test_endpoint "Create user" "POST" "$API_URL/users" \
    "{\"email\":\"$TEST_EMAIL\",\"username\":\"$TEST_USER\",\"password\":\"testpass123\",\"role\":\"customer\"}" \
    "" "200"

# Login to get token
echo -n "Logging in... "
login_response=$(curl -s -X POST "$API_URL/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$TEST_USER&password=testpass123")

ACCESS_TOKEN=$(echo $login_response | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -n "$ACCESS_TOKEN" ]; then
    echo -e "${GREEN}✓ Login successful${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Login failed${NC}"
    echo "  Response: $login_response"
    ((FAILED++))
fi

test_endpoint "Get current user" "GET" "$API_URL/users/me" "" \
    "Authorization: Bearer $ACCESS_TOKEN" "200"
echo ""

echo "3️⃣  Haircut Services"
test_endpoint "Get haircut services" "GET" "$API_URL/haircuts" "" "" "200"

test_endpoint "Search haircuts" "POST" "$API_URL/haircuts/search" \
    "{\"latitude\":37.7749,\"longitude\":-122.4194,\"radius\":10}" "" "200"
echo ""

echo "4️⃣  Shops"
test_endpoint "Get all shops" "GET" "$API_URL/shops/" "" "" "200"

# Create shop owner for shop tests
SHOP_OWNER="shopowner_${RANDOM_NUM}"
SHOP_EMAIL="shop_${RANDOM_NUM}@example.com"

test_endpoint "Create shop owner" "POST" "$API_URL/users" \
    "{\"email\":\"$SHOP_EMAIL\",\"username\":\"$SHOP_OWNER\",\"password\":\"testpass123\",\"role\":\"shop_owner\"}" \
    "" "200"

# Login as shop owner
shop_login=$(curl -s -X POST "$API_URL/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$SHOP_OWNER&password=testpass123")

SHOP_TOKEN=$(echo $shop_login | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -n "$SHOP_TOKEN" ]; then
    test_endpoint "Create shop" "POST" "$API_URL/shops/" \
        "{\"name\":\"Test Barbershop\",\"shop_type\":\"barber\",\"address\":\"123 Main St\",\"city\":\"San Francisco\",\"state\":\"CA\",\"zip_code\":\"94102\",\"country\":\"United States\",\"phone\":\"555-123-4567\"}" \
        "Authorization: Bearer $SHOP_TOKEN" "200"
        
    # Get shop ID from my-shops
    my_shops=$(curl -s "$API_URL/shops/my-shops" -H "Authorization: Bearer $SHOP_TOKEN")
    SHOP_ID=$(echo $my_shops | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
    
    if [ -n "$SHOP_ID" ]; then
        test_endpoint "Get shop by ID" "GET" "$API_URL/shops/${SHOP_ID}" "" "" "200"
    fi
fi
echo ""

echo "5️⃣  Queue Management"
if [ -n "$SHOP_ID" ]; then
    test_endpoint "Get active queue" "GET" "$API_URL/queues/shop/${SHOP_ID}/active" "" "" "200"
    
    test_endpoint "Join queue (guest)" "POST" "$API_URL/queues/shop/${SHOP_ID}/join" \
        "{\"customer_name\":\"John Doe\",\"customer_phone\":\"555-9999\",\"customer_email\":\"john@example.com\"}" \
        "" "200"
fi
echo ""

echo "📊 Test Summary"
echo "================================"
echo -e "Total tests: $((PASSED + FAILED))"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Check the output above.${NC}"
    exit 1
fi
