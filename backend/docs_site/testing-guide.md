# Testing Guide

This guide contains all credentials, test scenarios, and instructions for evaluating the ZeroQwait platform.

> **Test environment:** [https://zeroqwait.com](https://zeroqwait.com) — live production environment with seeded test data.

---

## Test Accounts

### Shop Owner <span class="badge badge-owner">OWNER</span>

<div class="cred-card">

**Shop:** True Toronto Point Barber Shop  
**Shop URL:** https://true-toronto-point-barber-shop.zeroqwait.com  
**Dashboard:** https://zeroqwait.com/dashboard

**Email:** `owner_lisa_adams_166@example-zeroqwait.com`  
**Username:** `owner_lisa_adams_166`  
**Password:** `Owner!0166814`

</div>

**Login at:** [https://zeroqwait.com/login](https://zeroqwait.com/login)

**Access:** Analytics, Revenue Reports, Staff Management, AI Inbox, Settings, Queue Management

---

### Employee Accounts <span class="badge badge-emp">EMPLOYEE</span>

Login URL: [https://zeroqwait.com/login](https://zeroqwait.com/login)

| Name | Username | Password |
|---|---|---|
| Jeffrey Holmes | `emp_461_1_jeffrey_holmes` | `ZQTest2026!` |

**Access:** Employee Dashboard, Queue Management, Call Next Customer, Service Tracking

---

### Customer / Walk-in <span class="badge badge-cust">CUSTOMER</span>

**No login required.** Visit the shop URL directly:  
🔗 [https://true-toronto-point-barber-shop.zeroqwait.com](https://true-toronto-point-barber-shop.zeroqwait.com)

---

## Services Catalogue

| Service | Price | Duration |
|---|---|---|
| Beard Trim | $31.12 | 18 min |
| Hot Towel Shave | $31.65 | 31 min |
| Skin Fade | $41.97 | 38 min |
| Classic Haircut | $42.41 | 26 min |
| Hair + Beard Combo | $52.96 | 45 min |

---

## Scenario 1 — Customer Queue & Payment

**Goal:** Verify a customer can find a shop, join the queue, and pay for a service.

1. Go to [zeroqwait.com](https://zeroqwait.com) and locate the large **violet/purple floating orb** at the centre of the hero section
2. Click the orb to open the full-screen AI chat overlay
2. Type: `find a barber shop in Toronto`
3. The agent should return True Toronto Point Barber Shop in the results
4. Click the shop name or navigate to [https://true-toronto-point-barber-shop.zeroqwait.com](https://true-toronto-point-barber-shop.zeroqwait.com)
5. Click **"Join Queue"**
6. Enter any name and select a service (e.g., Classic Haircut)
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

1. Go to [https://zeroqwait.com/login](https://zeroqwait.com/login)
2. Log in with employee credentials: `emp_461_1_jeffrey_holmes` / `ZQTest2026!`
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

1. Go to [https://zeroqwait.com/login](https://zeroqwait.com/login)
2. Log in with owner credentials: `owner_lisa_adams_166` / `Owner!0166814`
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

1. Visit [https://true-toronto-point-barber-shop.zeroqwait.com](https://true-toronto-point-barber-shop.zeroqwait.com)
2. Locate the **"NOW CHATTING WITH"** chat box on the page
3. Type: `What services do you offer?` — verify the AI lists the service menu
4. Type: `How long is the wait?` — verify real wait time is returned
5. Type: `Join the queue for a Classic Haircut` — verify the AI guides through the queue join form
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
3. Click the orb and **speak**: *"Find a barber shop in Toronto"*
4. Verify the AI returns search results including True Toronto Point Barber Shop
5. Speak: *"What's the wait time at True Toronto Point Barber Shop?"*
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

## Scenario 7 — Admin Portal

> **Note:** The admin portal (`/admin`) is available but requires a super-admin account. No public test admin credentials are available in the seeded dataset. Contact the platform administrator to request admin access for testing.

If you have admin credentials:

1. Go to `https://zeroqwait.com/admin`
2. Log in with provided admin credentials
3. View the **Overview** tab — live shop counts and queue stats
4. Click the **Feedback** tab — review submitted feedback tickets
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
  -F "description=Queue join worked perfectly" \
  -F "name=Your Name" \
  -F "page_context=testing-guide"
```

Optional fields: `-F "screenshot=@/path/to/screenshot.png"`, `-F "email=you@example.com"`, `-F "session_id=sess_123"`

---

## Admin Review

Feedback tickets are reviewed in the **Admin Portal** at [zeroqwait.com/admin](https://zeroqwait.com/admin).

**Admin credentials:**

> Admin access requires a super-admin account. No public test admin credentials are exported from the seed data. Contact the platform administrator to request access.

**Workflow:**

1. Log in at `/admin`
2. Click the **Feedback** tab
3. Each ticket shows: ID, rating, message, timestamp
4. Click a ticket to open the detail dialog — includes screenshot (if attached) and admin notes field
5. Update the status: **open → reviewed → closed**
6. Save admin notes for internal tracking
