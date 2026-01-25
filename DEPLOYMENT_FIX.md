# Production Deployment Fix (Kubernetes)

As we are using Kubernetes for the production environment on your Raspberry Pi, please follow these steps to deploy the latest code and seed the new search data.

### 1. Update Code & Deploy
Run the enhanced deployment script. This will pull the latest code and restart both the frontend and backend services.
```bash
./deploy-local.sh
```

### 2. Seed Search Data (Important)
To make "Search Auto Repair" work in production, run the new seeding script to inject "Mike's Auto Repair" into the Postgres database inside your cluster:
```bash
chmod +x deploy-db-seed.sh
./deploy-db-seed.sh
```

### 3. Verify
1. Go to `https://zeroqwait.com`.
2. Open the AI Assistant.
3. Search for **"auto repair"**.
4. You should see "Mike's Auto Repair" appear on the left side of the split-screen.

---
**What I Fixed in this Release:**
*   **Search Engine**: Now matches query keywords (auto, repair) against name, type, and description.
*   **Thinking Animation**: Removed the overlapping spinner; the Sphere now spins faster and pulses when "Thinking".
*   **Alignment**: Fixed vertical centering for both the sphere and the content card.
*   **Close Button**: Fixed z-index conflict to ensure it's always clickable.
