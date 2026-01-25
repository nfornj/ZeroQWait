# 🎮 AI Queue Counter - Demo Feature

## Overview
The Queue Counter is an AI-powered demo feature that uses computer vision to detect and count people in real-time through your device's camera. It's a fun, interactive way to demonstrate AI capabilities, especially for educational purposes!

## Features
- ✅ Real-time person detection using TensorFlow.js
- ✅ Automatic people counting with bounding boxes
- ✅ Estimated wait time calculation
- ✅ Works on mobile devices and desktop
- ✅ No backend required - runs entirely in the browser
- ✅ Perfect for demos with toys (action figures, dolls) or real people

## How to Access
1. **From Homepage**: Click the "Launch AI Demo" button in the AI Demo section
2. **Direct URL**: Navigate to `/queue-counter` route

## How It Works
1. **Click "Start Detection"** - Activates your camera
2. **Point at people or toys** - AI detects human figures
3. **Watch the magic** - Red boxes appear around detected people
4. **See the count** - Real-time count and estimated wait time displayed

## Technology Stack
- **TensorFlow.js**: Machine learning in the browser
- **COCO-SSD Model**: Pre-trained object detection model
- **React Webcam**: Camera access
- **Material-UI**: Beautiful interface

## Performance Notes

### Will it work on Raspberry Pi 4 (4GB RAM)?
**YES!** The AI model runs in the user's browser (client-side), NOT on your server. 

Your Raspberry Pi 4 only serves the static React app. The actual AI processing happens on the device viewing the page (phone, tablet, laptop). This means:
- ✅ No server load for AI processing
- ✅ Pi 4 can easily handle serving the static files
- ✅ Works on any device with a modern web browser
- ✅ Performance depends on the user's device, not your Pi

### Browser Requirements
- Modern browser with WebGL support
- Camera permissions enabled
- Recommended: Chrome, Safari, Edge (latest versions)

## Demo Tips for 11-Year-Olds
1. **Start with toys**: Line up action figures or dolls
2. **Add/remove objects**: Watch the count change instantly
3. **Try different angles**: See how AI detects from various positions
4. **Use real people**: Get family members to join the queue
5. **Experiment with distance**: See how close/far the camera can detect

## Educational Value
- Shows how AI "sees" the world
- Demonstrates object detection in real-time
- Explains practical AI applications (queue management)
- Introduces computer vision concepts visually
- Makes machine learning tangible and fun

## Mobile Usage
The feature is fully mobile-responsive! Access it from your phone:
1. Open the app on your phone
2. Navigate to the Queue Counter page
3. Grant camera permissions
4. Point at people or toys
5. See instant AI detection!

## Troubleshooting

### Camera not working?
- Check browser permissions
- Try a different browser
- Ensure HTTPS or localhost (camera requires secure context)

### AI model loading slowly?
- First load downloads the model (~5-10 MB)
- Subsequent loads are faster (cached)
- Normal on slower connections

### Detection not accurate?
- Ensure good lighting
- Keep people/toys clearly visible
- Try moving camera closer/further
- Works best with full body visibility

## Future Enhancements
- Multiple camera support (front/back)
- Snapshot/photo capture
- Detection history/statistics
- Adjustable detection sensitivity
- Sound effects for detections
- Leaderboard for "most people detected"

## Development
```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm start

# Access at
http://localhost:3000/queue-counter
```

## Credits
Built with ❤️ using:
- [TensorFlow.js](https://www.tensorflow.org/js)
- [COCO-SSD Model](https://github.com/tensorflow/tfjs-models/tree/master/coco-ssd)
- [React Webcam](https://github.com/mozmorris/react-webcam)
- [Material-UI](https://mui.com/)
