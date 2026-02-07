import React, { useRef, useState, useEffect } from 'react';
import Webcam from 'react-webcam';
import * as cocoSsd from '@tensorflow-models/coco-ssd';
import '@tensorflow/tfjs';
import { Hands, Results } from '@mediapipe/hands';
import {
  Box,
  Container,
  Typography,
  Button,
  Paper,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  CameraAlt,
  People,
  Timer,
  PanTool,
} from '@mui/icons-material';
import { recognizeGesture, GestureResult } from '../../../utils/gestureRecognition';



type DetectionMode = 'people' | 'gestures' | 'both';

const QueueCounterPage: React.FC = () => {
  const webcamRef = useRef<Webcam>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [model, setModel] = useState<cocoSsd.ObjectDetection | null>(null);
  const [hands, setHands] = useState<Hands | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [peopleCount, setPeopleCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detectionMode, setDetectionMode] = useState<DetectionMode>('gestures');
  const [currentGesture, setCurrentGesture] = useState<GestureResult | null>(null);
  const [gestureHistory, setGestureHistory] = useState<GestureResult[]>([]);

  // Average service time per person in minutes
  const AVG_SERVICE_TIME = 5;

  // Load the COCO-SSD model and MediaPipe Hands
  useEffect(() => {
    const loadModels = async () => {
      try {
        setLoading(true);

        // Load COCO-SSD for person detection
        const loadedModel = await cocoSsd.load();
        setModel(loadedModel);

        // Load MediaPipe Hands for gesture detection
        const handsInstance = new Hands({
          locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
          },
        });

        handsInstance.setOptions({
          maxNumHands: 2,
          modelComplexity: 1,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });

        handsInstance.onResults(onHandsResults);
        setHands(handsInstance);

        setLoading(false);
      } catch (err) {
        setError('Failed to load AI models. Please refresh the page.');
        setLoading(false);
      }
    };

    loadModels();
  }, []);

  // Handle hand detection results
  const onHandsResults = (results: Results) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Only clear and draw hands if in gesture mode
    if (detectionMode === 'gestures' || detectionMode === 'both') {
      if (detectionMode === 'gestures') {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }

      if (results.multiHandLandmarks && results.multiHandedness) {
        results.multiHandLandmarks.forEach((landmarks, index) => {
          const handLabel = results.multiHandedness[index].label;

          // Recognize gesture
          const gesture = recognizeGesture(landmarks, handLabel);
          setCurrentGesture(gesture);

          // Add to history (keep last 5)
          setGestureHistory(prev => {
            const newHistory = [gesture, ...prev.slice(0, 4)];
            return newHistory;
          });

          // Draw hand landmarks
          drawHandLandmarks(ctx, landmarks, canvas.width, canvas.height);

          // Draw gesture label
          const wrist = landmarks[0];
          ctx.fillStyle = '#00A699';
          ctx.font = 'bold 24px Arial';
          const text = `${gesture.emoji} ${gesture.gesture}`;
          const x = wrist.x * canvas.width;
          const y = wrist.y * canvas.height - 30;

          // Background for text
          const textWidth = ctx.measureText(text).width;
          ctx.fillRect(x - 5, y - 25, textWidth + 10, 35);

          // Text
          ctx.fillStyle = '#FFFFFF';
          ctx.fillText(text, x, y);
        });
      } else {
        setCurrentGesture(null);
      }
    }
  };

  // Draw hand landmarks
  const drawHandLandmarks = (
    ctx: CanvasRenderingContext2D,
    landmarks: any[],
    width: number,
    height: number
  ) => {
    // Draw connections
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4], // Thumb
      [0, 5], [5, 6], [6, 7], [7, 8], // Index
      [0, 9], [9, 10], [10, 11], [11, 12], // Middle
      [0, 13], [13, 14], [14, 15], [15, 16], // Ring
      [0, 17], [17, 18], [18, 19], [19, 20], // Pinky
      [5, 9], [9, 13], [13, 17], // Palm
    ];

    ctx.strokeStyle = '#00A699';
    ctx.lineWidth = 3;

    connections.forEach(([start, end]) => {
      const startPoint = landmarks[start];
      const endPoint = landmarks[end];

      ctx.beginPath();
      ctx.moveTo(startPoint.x * width, startPoint.y * height);
      ctx.lineTo(endPoint.x * width, endPoint.y * height);
      ctx.stroke();
    });

    // Draw landmarks
    landmarks.forEach((landmark, index) => {
      ctx.beginPath();
      ctx.arc(
        landmark.x * width,
        landmark.y * height,
        index === 0 || index === 4 || index === 8 || index === 12 || index === 16 || index === 20 ? 8 : 5,
        0,
        2 * Math.PI
      );
      ctx.fillStyle = index === 0 ? '#FF5A5F' : '#00A699';
      ctx.fill();
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  };

  // Detection loop
  useEffect(() => {
    let animationId: number;

    const detect = async () => {
      if (
        !isDetecting ||
        !webcamRef.current ||
        !canvasRef.current ||
        webcamRef.current.video?.readyState !== 4
      ) {
        if (isDetecting) {
          animationId = requestAnimationFrame(detect);
        }
        return;
      }

      const video = webcamRef.current.video!;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');

      if (!ctx) return;

      // Set canvas dimensions to match video
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      // Run person detection if in people or both mode
      if ((detectionMode === 'people' || detectionMode === 'both') && model) {
        try {
          const predictions = await model.detect(video);

          // Clear canvas only if not in both mode (hands will handle clearing)
          if (detectionMode === 'people') {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
          }

          // Filter for people only
          const people = predictions.filter(
            (prediction) => prediction.class === 'person' && prediction.score > 0.5
          );

          setPeopleCount(people.length);

          // Draw boxes around detected people
          people.forEach((prediction) => {
            const [x, y, width, height] = prediction.bbox;

            // Draw bounding box
            ctx.strokeStyle = '#FF5A5F';
            ctx.lineWidth = 3;
            ctx.strokeRect(x, y, width, height);

            // Draw label background
            ctx.fillStyle = '#FF5A5F';
            const text = `Person ${Math.round(prediction.score * 100)}%`;
            ctx.font = '18px Arial';
            const textWidth = ctx.measureText(text).width;
            ctx.fillRect(x, y - 30, textWidth + 10, 30);

            // Draw label text
            ctx.fillStyle = '#FFFFFF';
            ctx.fillText(text, x + 5, y - 10);
          });
        } catch (err) {
          // Silently continue detection
        }
      }

      // Run hand detection if in gestures or both mode
      if ((detectionMode === 'gestures' || detectionMode === 'both') && hands) {
        try {
          await hands.send({ image: video });
        } catch (err) {
          // Silently continue detection
        }
      }

      animationId = requestAnimationFrame(detect);
    };

    if (isDetecting) {
      detect();
    }

    return () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
  }, [isDetecting, model, hands, detectionMode]);

  const handleStartStop = () => {
    setIsDetecting(!isDetecting);
    if (!isDetecting) {
      setPeopleCount(0);
      setCurrentGesture(null);
      setGestureHistory([]);
    }
  };

  const handleModeChange = (
    event: React.MouseEvent<HTMLElement>,
    newMode: DetectionMode | null
  ) => {
    if (newMode !== null) {
      setDetectionMode(newMode);
      setPeopleCount(0);
      setCurrentGesture(null);
    }
  };

  const estimatedWaitTime = peopleCount * AVG_SERVICE_TIME;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          🎮 AI Queue Counter & Gesture Game
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
          Detect people, count fingers, and recognize hand gestures with AI!
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Chip
            icon={<CameraAlt />}
            label="People Detection"
            color="primary"
            sx={{ fontSize: '1rem', py: 2 }}
          />
          <Chip
            icon={<PanTool />}
            label="Gesture Recognition"
            color="secondary"
            sx={{ fontSize: '1rem', py: 2 }}
          />
        </Box>
      </Box>

      {error && (
        <Paper
          elevation={0}
          sx={{
            p: 3,
            mb: 3,
            bgcolor: 'error.light',
            color: 'error.contrastText',
          }}
        >
          <Typography>{error}</Typography>
        </Paper>
      )}

      <Box display="flex" flexWrap="wrap" gap={3}>
        {/* Camera View */}
        <Box sx={{ flex: 1, minWidth: '250px' }}>
          <Paper
            elevation={3}
            sx={{
              p: 2,
              position: 'relative',
              bgcolor: '#000',
              overflow: 'hidden',
            }}
          >
            {loading ? (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: 400,
                  color: 'white',
                }}
              >
                <CircularProgress size={60} sx={{ mb: 2 }} />
                <Typography variant="h6">Loading AI Model...</Typography>
                <Typography variant="body2" color="grey.400">
                  This may take a few seconds
                </Typography>
              </Box>
            ) : (
              <Box sx={{ position: 'relative' }}>
                <Webcam
                  ref={webcamRef}
                  audio={false}
                  screenshotFormat="image/jpeg"
                  videoConstraints={{
                    facingMode: 'user',
                  }}
                  style={{
                    width: '100%',
                    height: 'auto',
                    borderRadius: '8px',
                  }}
                />
                <canvas
                  ref={canvasRef}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                  }}
                />
              </Box>
            )}

            {!loading && (
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                <Button
                  variant="contained"
                  size="large"
                  onClick={handleStartStop}
                  startIcon={isDetecting ? <Stop /> : <PlayArrow />}
                  sx={{
                    px: 4,
                    py: 1.5,
                    fontSize: '1.2rem',
                    bgcolor: isDetecting ? 'error.main' : 'primary.main',
                    '&:hover': {
                      bgcolor: isDetecting ? 'error.dark' : 'primary.dark',
                    },
                  }}
                >
                  {isDetecting ? 'Stop Detection' : 'Start Detection'}
                </Button>
              </Box>
            )}
          </Paper>
        </Box>

        {/* Stats Panel */}
        <Box sx={{ flex: 1, minWidth: '250px' }}>
          <Card
            elevation={3}
            sx={{
              bgcolor: 'primary.main',
              color: 'white',
              mb: 2,
            }}
          >
            <CardContent sx={{ textAlign: 'center', py: 4 }}>
              <People sx={{ fontSize: 60, mb: 1 }} />
              <Typography variant="h2" component="div" sx={{ fontWeight: 700 }}>
                {peopleCount}
              </Typography>
              <Typography variant="h6">People Detected</Typography>
            </CardContent>
          </Card>

          <Card elevation={3} sx={{ mb: 2 }}>
            <CardContent sx={{ textAlign: 'center', py: 3 }}>
              <Timer sx={{ fontSize: 50, color: 'secondary.main', mb: 1 }} />
              <Typography variant="h3" component="div" color="primary">
                {estimatedWaitTime}
              </Typography>
              <Typography variant="h6" color="text.secondary">
                Minutes Wait Time
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                ({AVG_SERVICE_TIME} min per person)
              </Typography>
            </CardContent>
          </Card>

          {/* Detection Mode Selector */}
          <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              Mode
            </Typography>
            <ToggleButtonGroup
              value={detectionMode}
              exclusive
              onChange={handleModeChange}
              size="small"
              color="primary"
            >
              <ToggleButton value="people">People</ToggleButton>
              <ToggleButton value="gestures">Gestures</ToggleButton>
              <ToggleButton value="both">Both</ToggleButton>
            </ToggleButtonGroup>
          </Paper>

          {/* Current Gesture Panel */}
          <Card elevation={3} sx={{ mb: 2 }}>
            <CardContent sx={{ py: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <PanTool sx={{ fontSize: 40, color: 'secondary.main' }} />
                <Box>
                  <Typography variant="h5" sx={{ mb: 0.5 }}>
                    {currentGesture ? `${currentGesture.emoji} ${currentGesture.gesture}` : 'No Gesture Detected'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {currentGesture ? `Fingers: ${currentGesture.fingerCount} • Confidence: ${(currentGesture.confidence * 100).toFixed(0)}%` : 'Show your hand to the camera'}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Gesture History */}
          <Paper elevation={1} sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 1 }}>
              Recent Gestures
            </Typography>
            {gestureHistory.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Perform a gesture to see it here.
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {gestureHistory.map((g, i) => (
                  <Chip key={i} label={`${g.emoji} ${g.gesture}`} />
                ))}
              </Box>
            )}
          </Paper>

          {/* How it works */}
          <Paper elevation={1} sx={{ p: 3, mt: 2 }}>
            <Typography variant="h6" gutterBottom>
              💡 How It Works
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              • People mode: AI detects people and estimates wait time
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              • Gestures mode: Recognizes finger counting, thumbs up/down, peace, OK, rock on, fist, open hand
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              • Both mode: Shows both people and gesture overlays together
            </Typography>
          </Paper>
        </Box>
      </Box>

      {/* Gesture Guide */}
      <Paper
        elevation={2}
        sx={{
          mt: 4,
          p: 3,
          background: 'linear-gradient(135deg, #00A699 0%, #4DB6AC 100%)',
          color: 'white',
        }}
      >
        <Typography variant="h5" gutterBottom sx={{ fontWeight: 600 }}>
          👋 Gestures You Can Try:
        </Typography>
        <Box display="flex" flexWrap="wrap" gap={3} sx={{ mt: 1 }}>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>1️⃣-5️⃣</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Number Counting</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Show 1-5 fingers</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>👍</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Thumbs Up</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Point thumb up</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>👎</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Thumbs Down</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Point thumb down</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>✌️</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Peace Sign</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Two fingers up</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>👌</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>OK Sign</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Circle with thumb & index</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>🤘</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Rock On</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Index & pinky up</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>🤟</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>I Love You</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Thumb, index & pinky</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>✋</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Open Hand</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>All fingers extended</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>✊</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Fist</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>Closed hand</Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h3" sx={{ mb: 1 }}>☝️</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>Pointing</Typography>
              <Typography variant="body2" sx={{ opacity: 0.9 }}>One finger up</Typography>
            </Box>
          </Box>
        </Box>
      </Paper>

      {/* Fun Instructions */}
      <Paper
        elevation={2}
        sx={{
          mt: 4,
          p: 3,
          bgcolor: 'primary.light',
          color: 'white',
        }}
      >
        <Typography variant="h5" gutterBottom sx={{ fontWeight: 600 }}>
          🎯 Try These Fun Experiments:
        </Typography>
        <Box display="flex" flexWrap="wrap" gap={2} sx={{ mt: 1 }}>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                1. Count with fingers
              </Typography>
              <Typography variant="body2">
                Hold up 1, 2, 3, 4, or 5 fingers
              </Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                2. Give feedback
              </Typography>
              <Typography variant="body2">
                Thumbs up for yes, thumbs down for no
              </Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                3. Try all gestures
              </Typography>
              <Typography variant="body2">
                See how many the AI can recognize!
              </Typography>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minWidth: '250px' }}>
            <Box>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                4. Both hands
              </Typography>
              <Typography variant="body2">
                Use two hands at once
              </Typography>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Container>
  );
};

export default QueueCounterPage;
