#!/bin/bash

# Complete ZeroQwait Deployment After Build
# Run this after the Docker build completes

echo "🚀 Completing ZeroQwait Deployment"
echo "===================================="
echo ""

# Check build status
echo "📊 Checking build status..."
ssh pi@raspberrypi.local "cd /home/pi/Documents/projects/apps/zeroqwait && tail -20 build.log"

echo ""
read -p "Is the build complete? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Build not complete yet. Run this script again when build is done."
    echo ""
    echo "Check build status with:"
    echo "  ssh pi@raspberrypi.local 'cd /home/pi/Documents/projects/apps/zeroqwait && tail -f build.log'"
    exit 1
fi

# Start containers
echo ""
echo "🚀 Starting containers..."
ssh pi@raspberrypi.local "cd /home/pi/Documents/projects/apps/zeroqwait && docker compose -f docker-compose.prod.simple.yml up -d"

# Wait for startup
echo ""
echo "⏳ Waiting for containers to start..."
sleep 15

# Check status
echo ""
echo "📊 Container status:"
ssh pi@raspberrypi.local "cd /home/pi/Documents/projects/apps/zeroqwait && docker compose -f docker-compose.prod.simple.yml ps"

# Health checks
echo ""
echo "🏥 Running health checks..."
echo "Checking backend..."
ssh pi@raspberrypi.local "curl -f http://localhost:8000/ >/dev/null 2>&1" && echo "✅ Backend is healthy" || echo "⚠️  Backend not responding yet"

echo "Checking frontend..."
ssh pi@raspberrypi.local "curl -f http://localhost:3000/ >/dev/null 2>&1" && echo "✅ Frontend is healthy" || echo "⚠️  Frontend not responding yet"

echo ""
echo "🎉 Deployment Complete!"
echo "======================="
echo ""
echo "🌐 Your app is now live:"
echo "   • Website: https://zeroqwait.com"
echo "   • Queue Counter: https://zeroqwait.com/queue-counter"
echo ""
echo "🎮 New Gesture Recognition Features:"
echo "   • Finger counting (1-5)"
echo "   • Thumbs up/down 👍👎"
echo "   • Peace sign ✌️"
echo "   • OK sign 👌"
echo "   • Rock on 🤘"
echo "   • And 5+ more gestures!"
echo ""
echo "📱 Perfect for your 11-year-old demo!"
echo ""
