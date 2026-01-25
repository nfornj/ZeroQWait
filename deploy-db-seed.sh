#!/bin/bash
set -e

echo "🌱 Seeding Production Database..."

# Get the backend pod name
POD=$(sudo kubectl get pod -n zeroqwait -l app=backend -o jsonpath="{.items[0].metadata.name}")

if [ -z "$POD" ]; then
    echo "❌ CRM Backend Pod not found!"
    exit 1
fi

echo "found pod: $POD"

# Check if auto shop script exists, if not copy it (though it should be there via hostPath)
# Since hostPath is used, the file 'add_auto_shop.py' I created locally should be available inside if I commit it.
# BUT I created it on the *user's* machine. The `deploy-local.sh` does a `git pull`. 
# So I must ensure `add_auto_shop.py` is committed to the repo first!

# Run the script
sudo kubectl exec -n zeroqwait $POD -- python add_auto_shop.py

echo "✅ Database Seeded Successfully!"
