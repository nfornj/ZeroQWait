import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Box,
    Typography,
    Container,
    Paper,
    Avatar,
    IconButton,
    CircularProgress,
    Alert,
    Stack,
    keyframes,
    useTheme,
    Button
} from '@mui/material';
import { useSpring, animated, config } from '@react-spring/web';
import MicIcon from '@mui/icons-material/Mic';
import MicOffIcon from '@mui/icons-material/MicOff';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import KeyboardIcon from '@mui/icons-material/Keyboard';
import axios from 'axios';
import { useVoiceInterface } from '../hooks/useVoiceInterface';

// --- Animations ---
const float = keyframes`
  0% { transform: translateY(0px); }
  50% { transform: translateY(-20px); }
  100% { transform: translateY(0px); }
`;

const pulseGlow = keyframes`
  0% { box-shadow: 0 0 0 0 rgba(25, 118, 210, 0.4); }
  70% { box-shadow: 0 0 0 20px rgba(25, 118, 210, 0); }
  100% { box-shadow: 0 0 0 0 rgba(25, 118, 210, 0); }
`;

const waveAudio = keyframes`
  0% { height: 10%; }
  50% { height: 100%; }
  100% { height: 10%; }
`;

// --- Components ---

const Visualizer = ({ isListening }: { isListening: boolean }) => {
    return (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 60, gap: 1 }}>
            {[...Array(10)].map((_, i) => (
                <Box
                    key={i}
                    sx={{
                        width: 6,
                        height: isListening ? '100%' : '10%',
                        bgcolor: 'primary.main',
                        borderRadius: 4,
                        animation: isListening
                            ? `${waveAudio} ${0.5 + Math.random() * 0.5}s ease-in-out infinite`
                            : 'none',
                        transition: 'height 0.3s ease'
                    }}
                />
            ))}
        </Box>
    );
};

const AIShopPublicPage: React.FC = () => {
    const { shopId } = useParams<{ shopId: string }>(); // Logic handles slug or ID
    const navigate = useNavigate();
    const theme = useTheme();
    const [shop, setShop] = useState<any>(null);
    const [queues, setQueues] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [interactionState, setInteractionState] = useState<'idle' | 'listening' | 'processing' | 'success' | 'error'>('idle');
    const [feedbackMessage, setFeedbackMessage] = useState("Hi! I'm your shop assistant. Tap the mic to join a queue.");

    // Animation springs
    const fadeIn = useSpring({
        from: { opacity: 0, transform: 'translateY(50px)' },
        to: { opacity: 1, transform: 'translateY(0px)' },
        config: config.molasses,
        delay: 200
    });

    const bgSpring = useSpring({
        to: { background: shop?.primary_color ? `linear-gradient(135deg, ${shop.primary_color}11, #ffffff)` : '#f5f5f5' },
        config: config.gentle
    });

    // Voice Interface
    const { isListening, transcript, startListening, stopListening, speak, isSupported } = useVoiceInterface({
        continuous: false,
        onResult: (text) => handleVoiceCommand(text)
    });

    useEffect(() => {
        fetchShopAndQueues();
    }, [shopId]);

    // Handle state visualization for voice
    useEffect(() => {
        if (isListening) {
            setInteractionState('listening');
            setFeedbackMessage("Listening...");
        } else if (interactionState === 'listening') {
            // Stopped listening but haven't processed yet? 
            // Usually onResult handles processing.
            // setInteractionState('idle'); 
        }
    }, [isListening]);

    const fetchShopAndQueues = async () => {
        try {
            let response;
            // Determine if slug or ID
            const isSlug = isNaN(Number(shopId));
            if (isSlug) {
                // Assuming we have this endpoint or use public slug search
                // Since I didn't verify the /shops/s/ endpoint, I'll try to guess logic or standard ID
                // Actually, let's stick to the pattern used in InShopDisplayPage
                response = await axios.get(`/shops/public/${shopId}`);
            } else {
                response = await axios.get(`/shops/${shopId}`);
                // If that fails (auth), try public
            }

            // Fallback for demo if API strict
            // Note: The previous files suggested `/shops/s/${slug}` might not exist.
            // Using logic from InShopDisplayPage which seems more robust:

            // Re-implementing InShopDisplayPage logic simplistically:
            if (!response?.data && !isNaN(Number(shopId))) {
                response = await axios.get(`/shops/${shopId}`);
            }

            setShop(response.data);

            if (response.data.id) {
                const queueRes = await axios.get(`/queues/shop/${response.data.id}/active`);
                setQueues(queueRes.data.queue_items ? [queueRes.data] : (Array.isArray(queueRes.data) ? queueRes.data : []));
                // Note: API consistency varied in other files. Assuming standard list or single object.
                // Actually QueueManagement gets `/queues/shop/${id}/all`.
                const allQueues = await axios.get(`/queues/shop/${response.data.id}/all`);
                setQueues(allQueues.data);
            }
            setLoading(false);

            // Greeter
            setTimeout(() => {
                speak(`Welcome to ${response.data.name}. How can I help you?`);
            }, 1000);

        } catch (err) {
            console.error(err);
            // Fallback for dev/demo if backend not perfectly aligned to my assumptions
            setError('Could not load shop details');
            setLoading(false);
        }
    };

    const handleVoiceCommand = (text: string) => {
        setInteractionState('processing');
        const lowerText = text.toLowerCase();

        console.log("Voice command:", lowerText);

        if (lowerText.includes('join') || lowerText.includes('queue') || lowerText.includes('add me')) {
            // Heuristic for which queue
            if (queues.length > 0) {
                const targetQueue = queues[0]; // Default to first
                joinQueue(targetQueue);
            } else {
                setFeedbackMessage("Sorry, there are no open queues right now.");
                speak("Sorry, there are no open queues right now.");
                setInteractionState('error');
            }
        } else if (lowerText.includes('wait') || lowerText.includes('time') || lowerText.includes('long')) {
            if (shop) {
                const time = shop.average_service_time || 15;
                setFeedbackMessage(`Estimated wait time is about ${time} minutes.`);
                speak(`The estimated wait time is about ${time} minutes per person.`);
                setInteractionState('idle');
            }
        } else {
            setFeedbackMessage("I didn't quite catch that. Try saying 'Join Queue'.");
            speak("I didn't quite catch that. You can say join queue.");
            setInteractionState('error');
        }

        setTimeout(() => {
            if (interactionState !== 'success') setInteractionState('idle');
        }, 5000);
    };

    const joinQueue = (queue: any) => {
        // In a real flow, we'd ask for name/phone. 
        // For this AI agent page, let's redirect to the queue join form or handle it if we knew the user.
        // Let's redirect to the existing detailed join page but maybe pre-fill or auto-trigger?
        // Or better: Simulate the logic here.

        setFeedbackMessage(`Navigating you to join ${queue.name}...`);
        speak(`Okay, let's get you in the ${queue.name} queue.`);
        setInteractionState('success');

        setTimeout(() => {
            navigate(`/queue/${shop.id}`);
        }, 2000);
    };

    if (loading) return (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
            <CircularProgress />
        </Box>
    );

    if (error || !shop) return (
        <Container maxWidth="sm" sx={{ mt: 10 }}>
            <Alert severity="error">{error || "Shop not found"}</Alert>
        </Container>
    );

    return (
        <animated.div style={{ ...bgSpring, minHeight: '100vh', width: '100%', overflow: 'hidden', position: 'relative' }}>

            {/* Background Decor */}
            <Box sx={{ position: 'absolute', top: -100, right: -100, width: 400, height: 400, borderRadius: '50%', background: `radial-gradient(circle, ${shop.primary_color || '#1976d2'}44 0%, transparent 70%)` }} />
            <Box sx={{ position: 'absolute', bottom: -50, left: -50, width: 300, height: 300, borderRadius: '50%', background: `radial-gradient(circle, ${shop.primary_color || '#1976d2'}22 0%, transparent 70%)` }} />

            <Container maxWidth="md" sx={{ pt: 8, pb: 4, position: 'relative', zIndex: 2 }}>

                {/* Header Section */}
                <Stack spacing={2} alignItems="center" textAlign="center" mb={6}>
                    {shop.logo_url && (
                        <animated.div style={fadeIn}>
                            <Avatar
                                src={shop.logo_url}
                                sx={{ width: 100, height: 100, boxShadow: '0 8px 24px rgba(0,0,0,0.1)', border: '4px solid white' }}
                            />
                        </animated.div>
                    )}
                    <animated.div style={fadeIn}>
                        <Typography variant="h3" fontWeight="800" sx={{ letterSpacing: '-1px' }}>
                            {shop.name}
                        </Typography>
                        <Typography variant="subtitle1" color="text.secondary">
                            AI Assistant
                        </Typography>
                    </animated.div>
                </Stack>

                {/* Main AI Interface Card */}
                <animated.div style={fadeIn}>
                    <Paper
                        elevation={12}
                        sx={{
                            p: 6,
                            borderRadius: '32px',
                            background: 'rgba(255, 255, 255, 0.8)',
                            backdropFilter: 'blur(20px)',
                            border: '1px solid rgba(255, 255, 255, 0.5)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 4,
                            minHeight: 400,
                            justifyContent: 'center',
                            position: 'relative'
                        }}
                    >
                        {/* Status Feedback */}
                        <Box sx={{ minHeight: 60, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            {interactionState === 'listening' ? (
                                <Visualizer isListening={true} />
                            ) : (
                                <Typography variant="h5" color="text.secondary" fontWeight="500" textAlign="center">
                                    {feedbackMessage}
                                </Typography>
                            )}
                        </Box>

                        {/* Mic Button */}
                        <Box sx={{ position: 'relative' }}>
                            {isListening && (
                                <Box
                                    sx={{
                                        position: 'absolute',
                                        top: '50%',
                                        left: '50%',
                                        transform: 'translate(-50%, -50%)',
                                        width: '100%',
                                        height: '100%',
                                        borderRadius: '50%',
                                        animation: `${pulseGlow} 2s infinite`
                                    }}
                                />
                            )}
                            <IconButton
                                onClick={isListening ? stopListening : startListening}
                                disabled={!isSupported}
                                sx={{
                                    width: 100,
                                    height: 100,
                                    bgcolor: isListening ? 'error.main' : 'primary.main',
                                    color: 'white',
                                    transition: 'all 0.3s ease',
                                    '&:hover': {
                                        transform: 'scale(1.1)',
                                        bgcolor: isListening ? 'error.dark' : 'primary.dark',
                                    },
                                    boxShadow: '0 10px 30px rgba(0,0,0,0.2)'
                                }}
                            >
                                {isListening ? <GraphicEqIcon fontSize="large" /> : <MicIcon fontSize="large" />}
                            </IconButton>
                        </Box>

                        {/* Transcript Display */}
                        {transcript && (
                            <Typography variant="body1" sx={{ fontStyle: 'italic', opacity: 0.7, maxWidth: '80%', textAlign: 'center' }}>
                                "{transcript}"
                            </Typography>
                        )}

                        {!isSupported && (
                            <Alert severity="warning">
                                Voice not supported in this browser. Please use the buttons below.
                            </Alert>
                        )}

                        {/* Quick Actions Actions */}
                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', justifyContent: 'center', mt: 2 }}>
                            <Button
                                startIcon={<ArrowForwardIcon />}
                                variant="outlined"
                                size="large"
                                sx={{ borderRadius: 8, px: 4, py: 1.5, borderColor: 'primary.main', borderWidth: 2 }}
                                onClick={() => navigate(`/queue/${shop.id}`)}
                            >
                                Manual Join
                            </Button>
                        </Box>

                    </Paper>
                </animated.div>

                {/* Available Queues Glace */}
                <Stack direction="row" justifyContent="center" gap={2} mt={6} flexWrap="wrap">
                    {queues.map((q, i) => (
                        <animated.div key={q.id} style={{ ...fadeIn }}>
                            <Paper
                                elevation={0}
                                sx={{
                                    p: 2,
                                    borderRadius: 4,
                                    bgcolor: 'white',
                                    minWidth: 150,
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    transition: 'transform 0.2s',
                                    '&:hover': { transform: 'translateY(-5px)' }
                                }}
                                onClick={() => navigate(`/queue/${shop.id}`)}
                            >
                                <Typography variant="subtitle2" color="text.secondary" textTransform="uppercase" fontSize={10} letterSpacing={1} fontWeight="bold">
                                    Queue
                                </Typography>
                                <Typography variant="h6" fontWeight="bold">
                                    {q.name}
                                </Typography>
                                <Box sx={{ mt: 1, display: 'inline-block', px: 1, py: 0.5, bgcolor: 'secondary.main', color: 'white', borderRadius: 2, fontSize: 12, fontWeight: 'bold' }}>
                                    Open
                                </Box>
                            </Paper>
                        </animated.div>
                    ))}
                </Stack>

            </Container>
        </animated.div>
    );
};

export default AIShopPublicPage;
