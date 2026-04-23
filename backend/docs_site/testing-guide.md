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
| Shop 41 Employee #1 | `test_bulk_emp_0_0_8410` | `password123` |
| Shop 41 Employee #2 | `test_bulk_emp_0_1_3676` | `password123` |

For the current local E2E seed on shop 41, use the `test_bulk_emp_*` accounts above. The older `emp_samuel_james_421_0` demo credential is stale for the active local dataset.

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

1. Go to [zeroqwait.com](https://zeroqwait.com) and locate the large **violet/purple floating orb** at the centre of the hero section
2. Click the orb to open the full-screen AI chat overlay
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
2. Log in with employee credentials: `test_bulk_emp_0_0_8410`
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

## Scenario 6 — In-Chat Feedback

**Goal:** Verify the `/feedback` command opens an inline feedback form and generates a ticket.

1. Go to [zeroqwait.com](https://zeroqwait.com) and click the violet orb to open the chat
2. Type: `/feedback`
3. The AI should respond with a voice intro and render an **inline feedback form** below its message bubble
4. Fill in a test issue description (e.g., *"Button colour looks off on mobile"*)
5. Optionally attach a screenshot (take a browser screenshot and drag it in)
6. Click **Submit feedback**
7. Verify a green **Ticket ID** card appears (format: `ZQ-YYYYMMDD-NNNN`)

**Alternative trigger phrases — verify all open the form:**

| Phrase | Expected |
|---|---|
| `/feedback` | ✓ Form opens |
| `report a bug` | ✓ Form opens |
| `I have feedback` | ✓ Form opens |
| `submit my feedback` | ✓ Form opens |
| `found a bug` | ✓ Form opens |

**Expected results:**
- ✓ Inline form renders inside the chat (no new page)
- ✓ Screenshot thumbnail preview shown before submit
- ✓ Unique ticket ID returned on success (e.g., `ZQ-20260419-0001`)
- ✓ Ticket visible in admin portal at [zeroqwait.com/admin](https://zeroqwait.com/admin)

---

## Scenario 7 — Admin Feedback Portal

**Goal:** Verify the admin portal shows submitted feedback with full detail.

1. Go to `https://zeroqwait.com/admin` (or `http://localhost:3000/admin` on local)
2. Log in with:
   - **Username:** `zeroqwait_admin`
   - **Password:** `Admin@ZQ2026!`
3. The **Overview** tab shows live shop counts and queue stats
4. Click the **Feedback** tab
5. Verify the feedback ticket submitted in Scenario 6 appears in the table
6. Click the ticket row to open the **detail dialog**
7. Verify the full description and screenshot (if attached) are visible
8. Change the **Status** dropdown from *open* → *reviewed*
9. Add an admin note and click **Save**
10. Verify the row in the table now shows the *reviewed* chip

**Expected results:**
- ✓ All feedback submissions visible with ticket IDs
- ✓ Screenshot displayed in detail dialog
- ✓ Status can be updated (open / reviewed / closed)
- ✓ Admin notes saved and persisted

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
| /feedback command (in-chat) | ✓ Inline form opens, ticket ID returned (ZQ-YYYYMMDD-NNNN) |
| Admin feedback portal | ✓ Tickets listed, detail dialog opens, status updatable |

---

## Submit Feedback

Feedback can be submitted in two ways: **directly inside the AI chat** (recommended) or via the **REST API**.

### In-Chat Feedback (Recommended)

While chatting with ZeroQ on [zeroqwait.com](https://zeroqwait.com), type any of the following:

| Trigger phrase | What it does |
|---|---|
| `/feedback` | Opens the inline feedback form immediately |
| `report a bug` | Opens the inline feedback form |
| `I have feedback` | Opens the inline feedback form |
| `something isn't working` | Opens the inline feedback form |

The inline form will appear **inside the chat window** and lets you:
- Select a rating (1–5 stars)
- Write a message describing the issue or suggestion
- Optionally attach a screenshot

On submit, ZeroQ replies with a **ticket ID** (format: `ZQ-YYYYMMDD-NNNN`) for reference.

### REST API

For automated or headless testing:

```bash
curl -X POST https://zeroqwait.com/api/chat-feedback/submit \
  -F "tester_name=Your Name" \
  -F "message=Queue join worked perfectly" \
  -F "rating=5"
```

Optional field: `-F "screenshot=@/path/to/screenshot.png"`

**Rating scale:** 1 (broken) → 5 (perfect)

---

## Admin Review

Feedback tickets are reviewed in the **Admin Portal** at [zeroqwait.com/admin](https://zeroqwait.com/admin).

**Admin credentials:**

| Field | Value |
|---|---|
| Username | `zeroqwait_admin` |
| Password | `Admin@ZQ2026!` |

**Workflow:**

1. Log in at `/admin`
2. Click the **Feedback** tab
3. Each ticket shows: ID, rating, message, timestamp
4. Click a ticket to open the detail dialog — includes screenshot (if attached) and admin notes field
5. Update the status: **open → reviewed → closed**
6. Save admin notes for internal tracking
