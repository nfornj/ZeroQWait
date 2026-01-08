#!/bin/bash
# Deploy FastCuts to Raspberry Pi and run comprehensive tests

PI_USER="pi"
PI_HOST="192.168.2.85"
PI_PATH="/home/pi/FastCuts"

echo "🚀 Deploying FastCuts to Raspberry Pi"
echo "   Target: $PI_USER@$PI_HOST:$PI_PATH"
echo ""

# Check if we can connect to Pi
echo "1️⃣  Testing SSH connection..."
if ssh -o ConnectTimeout=5 "$PI_USER@$PI_HOST" "echo '✓ Connection successful'" 2>/dev/null; then
    echo ""
else
    echo "❌ Cannot connect to Pi at $PI_HOST"
    echo "   Please check:"
    echo "   - Is the Pi powered on?"
    echo "   - Is it on the network at 192.168.2.85?"
    echo "   - Can you ping it: ping 192.168.2.85"
    exit 1
fi

# Sync files to Pi (excluding node_modules, .git, etc.)
echo "2️⃣  Syncing files to Pi..."
rsync -avz --progress \
    --exclude 'node_modules' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'venv' \
    --exclude '.venv' \
    ./ "$PI_USER@$PI_HOST:$PI_PATH/"

if [ $? -eq 0 ]; then
    echo "✓ Files synced successfully"
else
    echo "❌ File sync failed"
    exit 1
fi

# Copy .env file separately (it's excluded from rsync)
echo ""
echo "3️⃣  Copying .env file..."
scp backend/.env "$PI_USER@$PI_HOST:$PI_PATH/backend/.env"

# SSH into Pi and run setup
echo ""
echo "4️⃣  Setting up on Pi..."
ssh "$PI_USER@$PI_HOST" << 'ENDSSH'
cd /home/pi/FastCuts

echo "📦 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed on Pi"
    echo "   Install with: curl -sSL https://get.docker.com | sh"
    exit 1
fi

echo "✓ Docker is installed"
echo ""

echo "🛑 Stopping existing containers..."
docker-compose down

echo ""
echo "🚀 Starting services..."
docker-compose up -d --build

echo ""
echo "⏳ Waiting for services to start (15 seconds)..."
sleep 15

echo ""
echo "🧪 Running comprehensive tests..."
docker exec fastcuts-backend-1 python comprehensive_test.py

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📱 Access your application:"
echo "   Frontend: http://192.168.2.85:3000"
echo "   Backend API: http://192.168.2.85:8000"
echo "   API Docs: http://192.168.2.85:8000/docs"
echo ""
echo "📊 Check logs:"
echo "   docker-compose logs -f backend"
echo "   docker-compose logs -f frontend"

ENDSSH

echo ""
echo "🎉 Deployment to Pi complete!"
echo ""
echo "Test from your local machine:"
echo "  curl http://192.168.2.85:8000/"
echo ""
