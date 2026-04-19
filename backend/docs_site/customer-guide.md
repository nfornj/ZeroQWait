# Finding a Shop & Joining the Queue

This guide walks you through the complete customer experience — from landing on [zeroqwait.com](https://zeroqwait.com) to getting your queue position at a local shop.

---

## Step 1 — Open the AI Chat Agent

<div class="step">
  <div class="step-num">1</div>
  <div class="step-body">
    <strong>Go to <a href="https://zeroqwait.com">zeroqwait.com</a></strong><br>
    You'll see the ZeroQwait landing page. In the <strong>bottom-right corner</strong> of the screen you'll find
    a glowing orb — this is the <strong>AI Chat Agent</strong>. Click it to open the chat panel.
  </div>
</div>

<div class="tip">

**Don't see the orb?** Scroll down slightly — the orb may be partially below the fold on smaller screens. It has a subtle animation and a microphone icon.

</div>

---

## Step 2 — Ask the Agent to Find a Shop

<div class="step">
  <div class="step-num">2</div>
  <div class="step-body">
    <strong>Type your request in plain English.</strong><br>
    You don't need to use any special commands. Just describe what you're looking for.
  </div>
</div>

### Useful phrases to try

The agent understands many ways of asking. Any of these will work:

<span class="chip">find a barber near me</span>  
<span class="chip">show me salons in Oshawa</span>  
<span class="chip">I need a haircut today</span>  
<span class="chip">search for barber shops near Oshawa</span>  
<span class="chip">find nail salons in Toronto</span>  
<span class="chip">any auto shops accepting walk-ins?</span>  
<span class="chip">look up clinics near me</span>

<div class="tip">

**Tip:** The more specific you are, the better the results. Include the city or neighbourhood if you can — for example *"barbers in Oshawa"* returns faster results than just *"haircut"*.

</div>

### What happens next

The agent processes your request and returns a list of matching shops. For each shop you'll see:

- Shop name and category (e.g., Barber, Salon, Clinic)
- Current queue status (Open / Closed)
- Estimated wait time
- Location / city

---

## Step 3 — Choose a Shop

<div class="step">
  <div class="step-num">3</div>
  <div class="step-body">
    <strong>Click on a shop name in the chat results</strong>, or ask the agent:
    <br><br>
    <span class="chip">tell me more about Urban Trim Oshawa</span><br>
    <span class="chip">open the first shop</span><br>
    <span class="chip">go to Urban Trim</span>
  </div>
</div>

The agent will give you a direct link to the shop's public page, or you can type the shop's slug URL directly:

```
https://<shop-slug>.zeroqwait.com
```

For example, the test demo shop is at:  
🔗 **[https://urban-trim-oshawa.zeroqwait.com](https://urban-trim-oshawa.zeroqwait.com)**

---

## Joining the Queue

Once you're on a shop's page, joining is simple — no account required.

<div class="step">
  <div class="step-num">1</div>
  <div class="step-body">
    <strong>Click "Join Queue"</strong> — the large button on the shop page.
  </div>
</div>

<div class="step">
  <div class="step-num">2</div>
  <div class="step-body">
    <strong>Enter your name.</strong> This is how staff will call you when it's your turn.
  </div>
</div>

<div class="step">
  <div class="step-num">3</div>
  <div class="step-body">
    <strong>Select a service</strong> from the list (e.g., Haircut, Hair Styling, Color Treatment).
    Each service shows its price and estimated duration.
  </div>
</div>

<div class="step">
  <div class="step-num">4</div>
  <div class="step-body">
    <strong>Confirm.</strong> You'll immediately see your queue position — for example <em>"You are #3 in queue"</em>
    — along with an estimated wait time.
  </div>
</div>

<div class="tip">

**You can also join via the AI chat on the shop page.** Type: *"I'd like to join the queue for a haircut"* and the agent will guide you through the form.

</div>

---

## Tracking Your Position

After joining the queue:

- Your **position number** updates in real time as customers ahead of you are called.
- The **estimated wait time** (in minutes) recalculates automatically.
- When it's almost your turn you'll see your position drop to **#1**.
- The employee on duty will call your name when it's time.

<div class="warn">

**Don't close the page** if you want to see live updates. Real-time sync uses WebSocket — refreshing the page will reload your current position but live updates require an active connection.

</div>

---

## Asking the Shop's AI Agent

Every shop has its own AI Receptionist that can answer questions about the shop directly:

<span class="chip">What services do you offer?</span>  
<span class="chip">How long is the wait right now?</span>  
<span class="chip">What are your hours?</span>  
<span class="chip">How much does a haircut cost?</span>  
<span class="chip">Is the queue open today?</span>

The shop agent has access to real-time queue data, service prices, and availability.

---

## Voice Mode

Prefer to speak instead of type? ZeroQwait supports full voice interaction.

<div class="step">
  <div class="step-num">1</div>
  <div class="step-body">
    In the top-right area of the chat interface, click the <strong>"Voice"</strong> toggle button to switch to Voice Mode.
  </div>
</div>

<div class="step">
  <div class="step-num">2</div>
  <div class="step-body">
    The orb grows larger and becomes the recording button. <strong>Click the orb and speak</strong> your request.
  </div>
</div>

<div class="step">
  <div class="step-num">3</div>
  <div class="step-body">
    The AI will respond both in text <em>and</em> with a natural-sounding voice (powered by Qwen3-TTS, voice: <em>Vivian</em>).
  </div>
</div>

**Voice mode examples:**
<span class="chip">Find a barber near Oshawa</span>  
<span class="chip">Join the queue for a haircut</span>  
<span class="chip">What's my wait time?</span>

Switch back to **Chat mode** at any time using the same toggle button.

---

## Frequently Asked Questions

**Do I need to create an account?**  
No. Customers can find shops and join queues with no account required. Just enter your name when joining.

**Can I join multiple queues?**  
You can join queues at different shops, but you should only occupy one position per shop at a time.

**Can I leave the queue?**  
Yes — on the shop page, find your queue entry and use the leave/cancel option.

**What if the queue is closed?**  
The shop page will show "Queue Closed". You can ask the AI agent when the shop reopens: *"When does Urban Trim Oshawa open tomorrow?"*

**Is there a mobile app?**  
No app needed — ZeroQwait works fully in any modern mobile browser.
