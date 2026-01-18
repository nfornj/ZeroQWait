#!/bin/bash

# Comprehensive API Testing Script for FastCuts
# Tests all major endpoints to ensure everything works with PostgreSQL

API_URL="http://192.168.2.88:30000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

echo "=================================="
echo "FastCuts API Testing Suite"
echo "API URL: $API_URL"
echo "=================================="
echo ""

# Test function
test_endpoint() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    local auth_token="$6"
    
    echo -n "Testing: $test_name ... "
    
    if [ -n "$auth_token" ]; then
        if [ "$method" = "POST" ]; then
            response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL$endpoint" \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -H "Authorization: Bearer $auth_token" \
                -d "$data" 2>/dev/null)
        else
            response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $auth_token" "$API_URL$endpoint" 2>/dev/null)
        fi
    else
        if [ "$method" = "POST" ]; then
            response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL$endpoint" \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -d "$data" 2>/dev/null)
        else
            response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint" 2>/dev/null)
        fi
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (HTTP $http_code)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC} (Expected $expected_status, got $http_code)"
        ((FAILED++))
        return 1
    fi
}

# Store token globally
TOKEN=""

echo "1. HEALTH & INFO TESTS"
echo "----------------------"
test_endpoint "API Root" "GET" "/" "" "200"
test_endpoint "API Docs" "GET" "/docs" "" "200"
test_endpoint "OpenAPI Spec" "GET" "/openapi.json" "" "200"
echo ""

echo "2. AUTHENTICATION TESTS"
echo "-----------------------"
# Test login and capture token
echo -n "Testing: Login with shop owner ... "
login_response=$(curl -s -X POST "$API_URL/api/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=testowner&password=password123" 2>/dev/null)

if echo "$login_response" | grep -q "access_token"; then
    TOKEN=$(echo "$login_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    echo -e "${GREEN}✓ PASSED${NC} (Token received)"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

test_endpoint "Login with invalid password" "POST" "/api/auth/token" "username=testowner&password=wrong" "401"
test_endpoint "Login with customer" "POST" "/api/auth/token" "username=testcustomer&password=password123" "200"
test_endpoint "Login with employee" "POST" "/api/auth/token" "username=testemployee&password=password123" "200"
echo ""

echo "3. USER MANAGEMENT TESTS"
echo "------------------------"
if [ -n "$TOKEN" ]; then
    test_endpoint "Get current user profile" "GET" "/api/users/me" "" "200" "$TOKEN"
else
    echo -e "${YELLOW}⚠ Skipped (no token)${NC}"
fi
test_endpoint "Check username availability (taken)" "GET" "/api/users/check-username/testowner" "" "200"
test_endpoint "Check username availability (available)" "GET" "/api/users/check-username/nonexistent" "" "200"
test_endpoint "Check email availability (taken)" "GET" "/api/users/check-email/owner@test.com" "" "200"
test_endpoint "Check email availability (available)" "GET" "/api/users/check-email/new@test.com" "" "200"
echo ""

echo "4. SHOP MANAGEMENT TESTS"
echo "------------------------"
test_endpoint "Get all shops" "GET" "/api/shops/" "" "200"
test_endpoint "Get shops by country" "GET" "/api/shops/?country=United%20States" "" "200"
test_endpoint "Get countries list" "GET" "/api/shops/countries" "" "200"
test_endpoint "Get shop by ID" "GET" "/api/shops/1" "" "200"
test_endpoint "Get shop by slug" "GET" "/api/shops/s/downtown-barbershop" "" "200"
test_endpoint "Get non-existent shop" "GET" "/api/shops/9999" "" "404"

if [ -n "$TOKEN" ]; then
    test_endpoint "Get my shops (authenticated)" "GET" "/api/shops/my-shops" "" "200" "$TOKEN"
else
    echo -e "${YELLOW}⚠ Skipped my-shops test (no token)${NC}"
fi
echo ""

echo "5. QUEUE TESTS"
echo "--------------"
# Verify queue data in shop response
echo -n "Testing: Shop includes queue data ... "
shop_response=$(curl -s "$API_URL/api/shops/1" 2>/dev/null)
if echo "$shop_response" | grep -q "queues"; then
    if echo "$shop_response" | grep -q "queue_items"; then
        echo -e "${GREEN}✓ PASSED${NC} (Queues with items found)"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠ PARTIAL${NC} (Queues found but no items)"
        ((PASSED++))
    fi
else
    echo -e "${RED}✗ FAILED${NC} (No queue data)"
    ((FAILED++))
fi
echo ""

echo "6. DATA VALIDATION TESTS"
echo "------------------------"
# Verify shop data structure
echo -n "Testing: Shop data structure ... "
shop_data=$(curl -s "$API_URL/api/shops/1" 2>/dev/null)
required_fields=("name" "address" "city" "state" "country" "phone" "shop_type" "slug")
missing_fields=()

for field in "${required_fields[@]}"; do
    if ! echo "$shop_data" | grep -q "\"$field\""; then
        missing_fields+=("$field")
    fi
done

if [ ${#missing_fields[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC} (All required fields present)"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC} (Missing: ${missing_fields[*]})"
    ((FAILED++))
fi

# Verify user data structure
echo -n "Testing: User data structure ... "
if [ -n "$TOKEN" ]; then
    user_data=$(curl -s -H "Authorization: Bearer $TOKEN" "$API_URL/api/users/me" 2>/dev/null)
    user_fields=("username" "email" "role" "is_active")
    missing_user_fields=()
    
    for field in "${user_fields[@]}"; do
        if ! echo "$user_data" | grep -q "\"$field\""; then
            missing_user_fields+=("$field")
        fi
    done
    
    if [ ${#missing_user_fields[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED${NC} (All required fields present)"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC} (Missing: ${missing_user_fields[*]})"
        ((FAILED++))
    fi
else
    echo -e "${YELLOW}⚠ Skipped (no token)${NC}"
fi
echo ""

echo "7. DATABASE INTEGRATION TESTS"
echo "-----------------------------"
# Verify data matches what was inserted
echo -n "Testing: Sample shop data integrity ... "
shops=$(curl -s "$API_URL/api/shops/" 2>/dev/null)
if echo "$shops" | grep -q "Downtown Barbershop" && echo "$shops" | grep -q "Elite Hair Salon"; then
    echo -e "${GREEN}✓ PASSED${NC} (Sample shops found)"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC} (Sample shops not found)"
    ((FAILED++))
fi

echo -n "Testing: Sample queue items exist ... "
shop_detail=$(curl -s "$API_URL/api/shops/1" 2>/dev/null)
if echo "$shop_detail" | grep -q "John Doe" || echo "$shop_detail" | grep -q "Jane Smith"; then
    echo -e "${GREEN}✓ PASSED${NC} (Queue items found)"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC} (Queue items not found)"
    ((FAILED++))
fi
echo ""

echo "=================================="
echo "TEST SUMMARY"
echo "=================================="
echo -e "Total Tests: $((PASSED + FAILED))"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo "The API is fully functional with PostgreSQL."
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo "Please check the failed tests above."
    exit 1
fi
