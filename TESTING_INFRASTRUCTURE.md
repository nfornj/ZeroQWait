# ZeroQwait Testing Infrastructure — Complete Deployment & Testing Guide

**Last Updated:** April 19, 2026  
**Status:** ✅ Production Ready | Documentation Complete | Feedback System Active

---

## 📋 Overview

This guide provides complete instructions for:
1. **Accessing the Testing Documentation** — Step-by-step guide for QA testers
2. **Testing Feedback System** — Collecting QA feedback with database persistence
3. **Production Deployment** — Deploying the testing infrastructure to production
4. **Credentials Management** — All test accounts with access levels

---

## 🎯 Quick Access

### For Testers
- **Documentation URL (Local):** http://localhost:3000/docs/testing-guide.html
- **Documentation URL (Production):** https://urban-trim-oshawa.zeroqwait.com/docs/testing-guide.html
- **Shop URL:** https://urban-trim-oshawa.zeroqwait.com
- **Admin Dashboard:** https://urban-trim-oshawa.zeroqwait.com/dashboard

### For Developers
- **Feedback API Endpoint:** `POST /api/feedback/submit`
- **Feedback Stats Endpoint:** `GET /api/feedback/stats`
- **All Feedback Endpoint:** `GET /api/feedback/all`

---

## 📚 Testing Documentation

### Location & Access
The interactive testing documentation is served from:
- **File Path:** `/frontend/public/docs/testing-guide.html`
- **Local URL:** `http://localhost:3000/docs/testing-guide.html`
- **Production:** Accessible at the root domain under `/docs/testing-guide.html`

### What's Included

The testing documentation includes:
1. **Quick Start Guide** — System overview, key features
2. **Credentials Section** — All test accounts (owner, employees)
3. **Testing Scenarios** (5 scenarios):
   - Scenario 1: Customer Queue Join & Payment
   - Scenario 2: Employee Dashboard Access
   - Scenario 3: Owner Dashboard & Analytics
   - Scenario 4: AI Chat Interaction
   - Scenario 5: Voice Mode Testing
4. **Expected Results Checklist** — What should happen for each feature
5. **Interactive Feedback Form** — Built into the page

---

## 🔐 Test Accounts

### Shop Owner Account

| Field | Value |
|-------|-------|
| Email | donna_sanchez_421@zeroqwait.com |
| Username | donna_sanchez_421 |
| Password | TempPassword!0fed01f36 |
| Role | Shop Owner (Full Access) |
| Dashboard | https://urban-trim-oshawa.zeroqwait.com/dashboard |

**Capabilities:**
- View live queue (#32 in system)
- Analytics and revenue reports
- Employee management
- AI Inbox (ask AI about business)
- Settings and shop configuration

### Employee Test Accounts

| Name | Username | Password | Access |
|------|----------|----------|--------|
| Samuel James | emp_samuel_james_421_0 | EmpPassword!9e969c7a7b | Employee Dashboard |
| Alexander Ruiz | emp_alexander_ruiz_421_1 | EmpPassword!463fa91ddc | Employee Dashboard |
| Robert Castillo | emp_robert_castillo_421_2 | EmpPassword!ee79a90807 | Employee Dashboard |
| William Long | emp_william_long_421_3 | EmpPassword!81f62de4f4 | Employee Dashboard |

**Capabilities:**
- View queue dashboard
- Call next customer
- Service tracking
- Check shifts

### Sample Services

| Service | Price | Duration |
|---------|-------|----------|
| Haircut | $25.00 | 30 min |
| Scalp Treatment | $25.48 | 30 min |
| Hair Styling | $30.00 | 45 min |
| Color Treatment | $45.00 | 60 min |

---

## 📊 Feedback System

### Backend Implementation

#### Database Table: `testing_feedback`

```sql
CREATE TABLE testing_feedback (
    id SERIAL PRIMARY KEY,
    tester_name VARCHAR(255) NOT NULL,
    tester_email VARCHAR(255) NOT NULL,
    test_scenario VARCHAR(50) NOT NULL,
    overall_rating INTEGER NOT NULL,
    feedback_text TEXT NOT NULL,
    issues_found TEXT,
    suggestions TEXT,
    allow_follow_up BOOLEAN DEFAULT FALSE,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookup
CREATE INDEX idx_testing_feedback_email ON testing_feedback(tester_email);
CREATE INDEX idx_testing_feedback_scenario ON testing_feedback(test_scenario);
```

#### API Endpoints

**1. Submit Feedback**
```
POST /api/feedback/submit
Content-Type: application/json

{
    "tester_name": "John Doe",
    "tester_email": "john@example.com",
    "test_scenario": "customer_queue",
    "overall_rating": 5,
    "feedback_text": "Everything works great!",
    "issues_found": "Minor typo on homepage",
    "suggestions": "Add dark mode",
    "allow_follow_up": true
}

Response: 201 Created
{
    "id": 1,
    "tester_name": "John Doe",
    "tester_email": "john@example.com",
    "test_scenario": "customer_queue",
    "overall_rating": 5,
    "feedback_text": "Everything works great!",
    "issues_found": "Minor typo on homepage",
    "suggestions": "Add dark mode",
    "allow_follow_up": true,
    "submitted_at": "2026-04-19T17:30:06Z",
    "created_at": "2026-04-19T17:30:06Z"
}
```

**2. Get Feedback Statistics**
```
GET /api/feedback/stats

Response: 200 OK
{
    "total_feedback": 5,
    "average_rating": 4.6,
    "by_scenario": [
        {"scenario": "customer_queue", "count": 2},
        {"scenario": "owner_dashboard", "count": 2},
        {"scenario": "voice_mode", "count": 1}
    ],
    "rating_distribution": [
        {"rating": 5, "count": 3},
        {"rating": 4, "count": 2}
    ],
    "follow_up_count": 4
}
```

**3. Get All Feedback (Admin)**
```
GET /api/feedback/all

Response: 200 OK
[
    {feedback_entry_1},
    {feedback_entry_2},
    ...
]
```

### Frontend Form Implementation

The feedback form is embedded directly in the testing documentation HTML:

```javascript
// Form collects:
- Tester name (required)
- Email address (required, validated)
- Test scenario (dropdown selection)
- Overall rating (1-5 scale)
- Detailed feedback (text area, required)
- Issues found (optional)
- Suggestions (optional)
- Follow-up checkbox (optional)

// Data is sent to POST /api/feedback/submit
// Success: "Thank you! Your feedback has been recorded."
// Error: "Error submitting feedback. Please try again."
```

---

## 🚀 Production Deployment

### Prerequisites

- Backend API running and healthy
- PostgreSQL database accessible
- Frontend served via Nginx or similar
- SSL/TLS certificates configured

### Deployment Checklist

- [x] Testing documentation HTML created at `/frontend/public/docs/testing-guide.html`
- [x] Feedback API endpoints implemented in `backend/modules/testing/routes.py`
- [x] Database table `testing_feedback` created
- [x] API tested and working locally
- [x] Frontend form functionality verified
- [x] Credentials verified in documentation

### To Deploy to Production (https://zeroqwait.com)

1. **Commit and Push Changes**
   ```bash
   cd /home/neekrishrichu/projects/FastCuts
   git add -A
   git commit -m "Add testing documentation and feedback system - v1.0"
   git push origin prod  # Deploy to production
   ```

2. **Verify Production Deployment**
   ```bash
   # Check if documentation is accessible
   curl -I https://zeroqwait.com/docs/testing-guide.html
   
   # Test feedback API on production
   curl -X POST https://zeroqwait.com/api/feedback/submit \
     -H 'Content-Type: application/json' \
     -d '{"tester_name":"Test","tester_email":"test@example.com",...}'
   ```

3. **Share with Testers**
   ```
   Testing Documentation: https://zeroqwait.com/docs/testing-guide.html
   Shop URL: https://urban-trim-oshawa.zeroqwait.com
   Owner Email: donna_sanchez_421@zeroqwait.com
   ```

### Post-Deployment Monitoring

After production deployment:

1. **Monitor Feedback Stats**
   ```bash
   curl -s https://zeroqwait.com/api/feedback/stats | jq .
   ```

2. **Review Feedback**
   ```bash
   curl -s https://zeroqwait.com/api/feedback/all | jq 'sort_by(.submitted_at) | reverse'
   ```

3. **Check Database**
   ```bash
   psql -U postgres -d zeroqwait -c "SELECT COUNT(*) as total_feedback FROM testing_feedback;"
   ```

---

## 🧪 Testing Workflow for QA

### Step-by-Step for Testers

1. **Access Documentation**
   - Open: https://urban-trim-oshawa.zeroqwait.com/docs/testing-guide.html
   - Read Quick Start guide
   - Note down credentials

2. **Run Test Scenarios**
   - Follow each scenario in order (1-5)
   - Check results against checklist
   - Note any issues encountered

3. **Submit Feedback**
   - Scroll to "Testing Feedback Form" section
   - Fill in all required fields
   - Optional: Add details about issues found
   - Click "Submit Feedback"
   - Confirm "Thank you" message appears

4. **Expected Time**
   - ~30-45 minutes per scenario
   - 10 minutes for feedback submission

### Success Criteria

✅ All 5 test scenarios complete  
✅ Expected results match actual behavior  
✅ Feedback form submits successfully  
✅ No critical bugs encountered  
✅ All three core customer features work:
- Register a Shop
- Search for Shops (AI-powered queue)
- Ask about Products

---

## 📈 Feedback Analysis

### Dashboard Metrics (Available via API)

**Example Stats after 10 testers:**
```
{
    "total_feedback": 10,
    "average_rating": 4.7,
    "by_scenario": {
        "customer_queue": 2,
        "owner_dashboard": 3,
        "ai_chat": 2,
        "employee_dashboard": 2,
        "voice_mode": 1
    },
    "rating_distribution": {
        "5": 7,
        "4": 2,
        "3": 1
    },
    "follow_up_count": 8
}
```

### Common Feedback Categories to Track

- **Usability Issues:** Hard to find features, confusing UI
- **Performance:** Slow loading, lag, delays
- **Bugs:** Errors, crashes, incorrect behavior
- **Feature Requests:** Missing capabilities, improvements
- **Voice Quality:** Audio clarity, TTS speed, ASR accuracy

---

## 🔗 Integration Points

### Backend Routes

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/feedback/submit` | POST | Submit feedback | None (public) |
| `/api/feedback/stats` | GET | View statistics | None (stats are public) |
| `/api/feedback/all` | GET | Get all feedback | TODO: Add auth |

### Frontend Integration

- Testing guide HTML: `/frontend/public/docs/testing-guide.html`
- Nginx serves as static file from `public/` directory
- Form uses vanilla JavaScript (no dependencies)
- CORS enabled for API calls

### Database Integration

- Table: `testing_feedback` in `zeroqwait` database
- Indices: `tester_email`, `test_scenario` for fast queries
- Retention: Keep all feedback indefinitely (backup before deletion)

---

## 🛠️ Troubleshooting

### Issue: "404 Not Found" for testing documentation

**Solution:**
```bash
# Verify file exists at frontend
ls -la /home/neekrishrichu/projects/FastCuts/frontend/public/docs/testing-guide.html

# Verify Nginx is serving public directory
docker exec zeroqwait-frontend-1 nginx -T | grep "alias"

# Clear browser cache and reload
```

### Issue: Feedback form submits but nothing happens

**Solution:**
```bash
# Check backend logs for errors
docker logs zeroqwait-backend-1 | grep -i feedback

# Verify database table exists
docker exec zeroqwait-db-1 psql -U postgres -d zeroqwait \
  -c "\dt testing_feedback"

# Check CORS headers
curl -i http://localhost:8000/api/feedback/submit \
  -H 'Origin: http://localhost:3000'
```

### Issue: No records in feedback table

**Solution:**
```bash
# Check database table
docker exec zeroqwait-db-1 psql -U postgres -d zeroqwait \
  -c "SELECT COUNT(*) FROM testing_feedback;"

# Manually insert test data
docker exec zeroqwait-db-1 psql -U postgres -d zeroqwait \
  -c "INSERT INTO testing_feedback (tester_name, tester_email, test_scenario, overall_rating, feedback_text) 
      VALUES ('Test', 'test@example.com', 'customer_queue', 5, 'Test feedback');"
```

---

## 📝 Files Modified/Created

### New Files
- ✅ `frontend/public/docs/testing-guide.html` — Interactive testing documentation
- ✅ `backend/modules/testing/__init__.py` — Module initialization
- ✅ `backend/modules/testing/models.py` — TestingFeedback SQLAlchemy model
- ✅ `backend/modules/testing/schemas.py` — Pydantic schemas for validation
- ✅ `backend/modules/testing/routes.py` — FastAPI feedback endpoints

### Modified Files
- ✅ `backend/models.py` — Added TestingFeedback import
- ✅ `backend/main.py` — Registered testing router

---

## 🎓 Learning Resources

### For Understanding the System

1. **Queue Management** — See `/backend/modules/queues/`
2. **Payment Integration** — See `/backend/routers/payments.py`
3. **AI Agent** — See `/backend/agent_logic.py`
4. **Voice Pipeline** — See `/backend/routers/voice.py`

### API Documentation

All endpoints are documented in **FastAPI Swagger UI**:
```
http://localhost:8000/docs
```

---

## 🎯 Next Steps

After initial testing deployment, consider:

1. **Analytics Dashboard** — Visualize feedback stats (Grafana/Chart.js)
2. **Email Notifications** — Alert team when critical feedback arrives
3. **Tester Management** — Track which testers have followed up
4. **Automated Testing** — Run key scenarios via Selenium/Playwright
5. **A/B Testing** — Compare different UI variations

---

## 👥 Support Contacts

- **Technical Issues:** support@zeroqwait.com
- **Feedback Questions:** qa@zeroqwait.com
- **Deployment Help:** devops@zeroqwait.com

---

## ✅ Sign-Off Checklist

- [x] Testing documentation created and functional
- [x] Feedback API endpoints implemented and tested
- [x] Database table created with proper schema
- [x] Frontend HTML form working correctly
- [x] All test credentials verified in database
- [x] Credentials documented with access levels
- [x] Production deployment instructions provided
- [x] Monitoring and troubleshooting guide included
- [x] File changes documented
- [x] Test data verified (at least 1 feedback record)

**Status:** 🟢 READY FOR PRODUCTION DEPLOYMENT

---

**Created by:** AI Assistant  
**Date:** April 19, 2026  
**Version:** 1.0 (Initial Release)
