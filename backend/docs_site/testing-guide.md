# Testing Guide

This guide contains all credentials, test scenarios, and instructions for evaluating the ZeroQwait platform.

> **Test environment:** [https://zeroqwait.com](https://zeroqwait.com) — live production environment with seeded test data.

---

## Test Accounts

### Shop Owner <span class="badge badge-owner">OWNER</span>

<div class="cred-card">

**Shop:** Urban Trim Oshawa  
**Shop URL:** https://urban-trim-oshawa.zeroqwait.com  
**Dashboard:** https://urban-trim-oshawa.zeroqwait.com/dashboard

**Email:** `donna_sanchez_421@zeroqwait.com`  
**Username:** `donna_sanchez_421`  
**Password:** `TempPassword!0fed01f36`

</div>

**Access:** Analytics, Revenue Reports, Staff Management, AI Inbox, Settings, Queue Management

---

### Employee Accounts <span class="badge badge-emp">EMPLOYEE</span>

Login URL: `https://urban-trim-oshawa.zeroqwait.com/login`

| Name | Username | Password |
|---|---|---|
| Samuel James | `emp_samuel_james_421_0` | `EmpPassword!9e969c7a7b` |
| Alexander Ruiz | `emp_alexander_ruiz_421_1` | `EmpPassword!463fa91ddc` |
| Robert Castillo | `emp_robert_castillo_421_2` | `EmpPassword!ee79a90807` |
| William Long | `emp_william_long_421_3` | `EmpPassword!81f62de4f4` |

**Access:** Employee Dashboard, Queue Management, Call Next Customer, Service Tracking

---

### Customer / Walk-in <span class="badge badge-cust">CUSTOMER</span>

**No login required.** Visit the shop URL directly:  
🔗 [https://urban-trim-oshawa.zeroqwait.com](https://urban-trim-oshawa.zeroqwait.com)

---

## Services Catalogue

| Service | Price | Duration |
|---|---|---|
| Haircut | $25.00 | 30 min |
| Scalp Treatment | $25.48 | 30 min |
| Hair Styling | $30.00 | 45 min |
| Color Treatment | $45.00 | 60 min |

---

## Scenario 1 — Customer Queue & Payment

**Goal:** Verify a customer can find a shop, join the queue, and pay for a service.

1. Go to [zeroqwait.com](https://zeroqwait.com) and open the AI chat agent (bottom-right orb)
2. Type: `find a barber shop in Oshawa`
3. The agent should return Urban Trim Oshawa in the results
4. Click the shop name or navigate to [https://urban-trim-oshawa.zeroqwait.com](https://urban-trim-oshawa.zeroqwait.com)
5. Click **"Join Queue"**
6. Enter any name and select a service (e.g., Haircut)
7. Verify queue position is displayed (e.g., "You are #X in queue")
8. Click **"Pay for Service"**
9. Use Stripe test card: `4242 4242 4242 4242` / expiry `12/26` / CVC `123`
10. Verify payment success notification

**Expected results:**
- ✓ Position displays immediately after joining
- ✓ Estimated wait time shown
- ✓ Payment confirmation received

---

## Scenario 2 — Employee Dashboard

**Goal:** Verify employee can view and manage the active queue.

1. Go to [https://urban-trim-oshawa.zeroqwait.com/login](https://urban-trim-oshawa.zeroqwait.com/login)
2. Log in with employee credentials: `emp_samuel_james_421_0`
3. View the active queue in the employee dashboard
4. Click **"Call Next Customer"** to serve the next person
5. Verify the queue advances and the customer count updates
6. Check employee shift status in the sidebar

**Expected results:**
- ✓ Active queue loads instantly
- ✓ "Call Next" updates queue in real time
- ✓ Shift info visible on dashboard

---

## Scenario 3 — Owner Dashboard & Analytics

**Goal:** Verify owner can access full analytics and AI inbox.

1. Go to [https://urban-trim-oshawa.zeroqwait.com/dashboard](https://urban-trim-oshawa.zeroqwait.com/dashboard)
2. Log in with owner credentials: `donna_sanchez_421@zeroqwait.com`
3. View live queue status from the dashboard
4. Navigate to **Analytics** — verify revenue charts and customer metrics load
5. Navigate to **Employees** — verify staff list is visible
6. Open **AI Inbox** and type: `What was yesterday's revenue?`
7. Verify the AI agent responds with financial data

**Expected results:**
- ✓ Analytics graphs with 3 years of seed data
- ✓ AI Inbox responds with accurate revenue info
- ✓ Employee shifts visible

---

## Scenario 4 — AI Chat Interaction

**Goal:** Verify the AI chat agent responds correctly on the public shop page.

1. Visit [https://urban-trim-oshawa.zeroqwait.com](https://urban-trim-oshawa.zeroqwait.com)
2. Locate the **"NOW CHATTING WITH"** chat box on the page
3. Type: `What services do you offer?` — verify the AI lists the service menu
4. Type: `How long is the wait?` — verify real wait time is returned
5. Type: `Join the queue for a haircut` — verify the AI guides through the queue join form
6. Type: `What are your hours?` — verify the AI returns shop hours

**Expected results:**
- ✓ AI returns real-time queue and service data
- ✓ Queue join can be initiated via natural language
- ✓ Responses are coherent and accurate

---

## Scenario 5 — Voice Mode

**Goal:** Verify voice input and TTS output work end-to-end.

1. On [zeroqwait.com](https://zeroqwait.com), click the **"Voice"** toggle in the top-right controls
2. The orb enlarges to indicate recording mode
3. Click the orb and **speak**: *"Find a barber near Oshawa"*
4. Verify the AI returns search results
5. Speak: *"What's the wait time at Urban Trim?"*
6. Verify you **hear** the response (TTS audio plays automatically)
7. Switch back to **Chat** mode using the same toggle — verify no audio plays

**Expected results:**
- ✓ Speech recognized accurately (Whisper ASR)
- ✓ AI voice response plays (Qwen3-TTS, voice: Vivian)
- ✓ Voice / Chat toggle works correctly
- ✓ Switching to Chat mode stops audio

---

## Expected Results Checklist

| Feature | Expected |
|---|---|
| Queue Join | ✓ Position displays immediately |
| Wait Time | ✓ Shows current estimate |
| Payment (Stripe) | ✓ Test card accepted, confirmation shown |
| Employee "Call Next" | ✓ Queue advances in real time |
| Owner Analytics | ✓ Charts load with seed data |
| AI Chat (public) | ✓ Shop-specific responses |
| AI Inbox (owner) | ✓ Finance/queue questions answered |
| Voice ASR | ✓ Speech recognized via Whisper |
| Voice TTS | ✓ Audio plays with Vivian voice |

---

## Submit Feedback

After testing, please submit your findings through the feedback form:

**API endpoint:**

```bash
curl -X POST https://zeroqwait.com/api/feedback/submit \
  -H "Content-Type: application/json" \
  -d '{
    "tester_name": "Your Name",
    "scenario": "Customer Queue Join",
    "rating": 5,
    "feedback": "Worked perfectly — queue joined instantly.",
    "issues": ""
  }'
```

**Rating scale:** 1 (broken) → 5 (perfect)

**View submitted feedback:**

```bash
curl https://zeroqwait.com/api/feedback/stats
```
