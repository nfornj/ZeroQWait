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
    Button,
    Chip,
    LinearProgress
} from '@mui/material';
import { useSpring, animated, config } from '@react-spring/web';
import MicIcon from '@mui/icons-material/Mic';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';
import axios from 'axios';
import { useVoiceInterface } from '../hooks/useVoiceInterface';

// --- Animations ---
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

type FlowState = 'idle' | 'listening' | 'asking_name' | 'asking_phone' | 'asking_service' | 'confirming' | 'processing' | 'success' | 'error';

const AIShopPublicPage: React.FC = () => {
    const { shopId } = useParams<{ shopId: string }>();
    const navigate = useNavigate();

    // Data States
    const [shop, setShop] = useState<any>(null);
    const [queues, setQueues] = useState<any[]>([]);
    const [services, setServices] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Flow Data
    const [customerName, setCustomerName] = useState('');
    const [customerPhone, setCustomerPhone] = useState('');
    const [selectedService, setSelectedService] = useState<any>(null);

    // UI State
    const [flowState, setFlowState] = useState<FlowState>('idle');
    const [feedbackMessage, setFeedbackMessage] = useState("Hi! Tap the mic to join.");
    const [transcriptHistory, setTranscriptHistory] = useState<string[]>([]);

    // Voice Interface
    const { isListening, transcript, startListening, stopListening, speak, isSupported } = useVoiceInterface({
        continuous: false,
        onResult: (text) => handleVoiceInput(text)
    });

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

    useEffect(() => {
        fetchShopData();
    }, [shopId]);

    useEffect(() => {
        if (isListening) {
            // Just UI update, state logic is handled in flow
        }
    }, [isListening]);

    const fetchShopData = async () => {
        try {
            // 1. Fetch Shop
            let response;
            const isSlug = isNaN(Number(shopId));
            if (isSlug) {
                response = await axios.get(`/shops/public/${shopId}`);
            } else {
                response = await axios.get(`/shops/${shopId}`);
                if (!response?.data) response = await axios.get(`/shops/${shopId}`); // Fallback
            }
            const shopData = response.data;
            setShop(shopData);

            // 2. Fetch Queues
            if (shopData.id) {
                const queueRes = await axios.get(`/queues/shop/${shopData.id}/active`);
                setQueues(queueRes.data.queue_items ? [queueRes.data] : (Array.isArray(queueRes.data) ? queueRes.data : []));

                // 3. Fetch Services (Public)
                try {
                    const servicesRes = await axios.get(`/api/shops/${shopData.id}/services`);
                    setServices(servicesRes.data.filter((s: any) => s.is_active));
                } catch (e) {
                    console.log("Services fetch failed or empty", e);
                }
            }
            setLoading(false);

            // Initial Greeting
            setTimeout(() => {
                speak(`Welcome to ${shopData.name}. Tap the microphone and say Join Queue to start.`);
            }, 1000);

        } catch (err) {
            console.error(err);
            setError('Could not load shop details');
            setLoading(false);
        }
    };

    const handleVoiceInput = (text: string) => {
        const lowerText = text.toLowerCase();
        console.log("Input:", text, "State:", flowState);
        setTranscriptHistory(prev => [...prev.slice(-2), text]); // Keep last 3

        switch (flowState) {
            case 'idle':
            case 'error':
                if (lowerText.includes('join') || lowerText.includes('queue') || lowerText.includes('add me')) {
                    setFlowState('asking_name');
                    const msg = "Sure! What is your name?";
                    setFeedbackMessage(msg);
                    speak(msg);
                    // Auto-listen after speaking? Web Speech API requires user interaction often, 
                    // but if we are already in a flow initiated by user, we might try to startListening again after delay.
                    // For now, let's rely on user tapping or manual re-activation if continuous is false.
                    // But ideally: 
                    setTimeout(startListening, 3000);
                } else if (lowerText.includes('wait') || lowerText.includes('time')) {
                    const time = shop.average_service_time || 15;
                    const msg = `Estimated wait time is about ${time} minutes.`;
                    setFeedbackMessage(msg);
                    speak(msg);
                    setFlowState('idle');
                } else {
                    speak("I didn't catch that. Say Join Queue to start.");
                }
                break;

            case 'asking_name':
                // Naive extraction: take the whole text as name if short, or look for patterns
                // User might say "My name is John"
                let name = text;
                if (lowerText.includes('my name is')) {
                    name = text.substring(lowerText.indexOf('is') + 3).trim();
                } else if (lowerText.includes('i am')) {
                    name = text.substring(lowerText.indexOf('am') + 3).trim();
                }
                // Clean up punctuation
                name = name.replace(/[.,!]/g, '');

                setCustomerName(name);
                setFlowState('asking_phone');
                const phoneMsg = `Hi ${name}. What's your phone number?`;
                setFeedbackMessage(phoneMsg);
                speak(phoneMsg);
                setTimeout(startListening, 4000);
                break;

            case 'asking_phone':
                // Extract digits
                const nums = text.replace(/[^0-9]/g, '');
                if (nums.length < 7) {
                    speak("That didn't sound like a phone number. Please say it again.");
                    setTimeout(startListening, 3000);
                    return;
                }
                setCustomerPhone(nums);

                if (services.length > 0) {
                    setFlowState('asking_service');
                    const serviceNames = services.map(s => s.name).join(', ');
                    const srvMsg = `Got it. Which service would you like? We have: ${serviceNames}`;
                    setFeedbackMessage(`Services: ${serviceNames}`);
                    speak(srvMsg);
                    setTimeout(startListening, 6000);
                } else {
                    // No services, skip to confirm
                    submitQueue(name, nums, null);
                }
                break;

            case 'asking_service':
                // Match service name
                const matchedService = services.find(s => lowerText.includes(s.name.toLowerCase()));
                if (matchedService) {
                    setSelectedService(matchedService);
                    submitQueue(customerName, customerPhone, matchedService);
                } else {
                    // If ambiguous, maybe default or ask again.
                    // Let's assume first one if unsure? No that's risky.
                    // Let's ask again.
                    speak("Sorry, I didn't recognize that service. Please choose from: " + services.map(s => s.name).join(', '));
                    setTimeout(startListening, 5000);
                }
                break;
        }
    };

    const submitQueue = async (name: string, phone: string, service: any) => {
        setFlowState('processing');
        setFeedbackMessage("Adding you to the queue...");
        speak("Adding you to the queue now.");

        try {
            await axios.post(`/queues/shop/${shop.id}/join`, {
                customer_name: name,
                customer_phone: phone,
                service_id: service?.id || null,
                notes: "Joined via AI Voice Agent"
            });

            setFlowState('success');
            const finalMsg = `You are added! ${service ? 'for ' + service.name : ''}. You will receive a text shortly.`;
            setFeedbackMessage("Joined Successfully!");
            speak(finalMsg);

            // Navigate after delay
            setTimeout(() => {
                navigate(`/queue/${shop.id}`);
            }, 5000);

        } catch (err) {
            console.error(err);
            setFlowState('error');
            setFeedbackMessage("Failed to join. Please try again or use manual join.");
            speak("Something went wrong joining the queue. Please try the manual button.");
        }
    };

    if (loading) return <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh"><CircularProgress /></Box>;
    if (error || !shop) return <Container maxWidth="sm" sx={{ mt: 10 }}><Alert severity="error">{error || "Shop not found"}</Alert></Container>;

    return (
        <animated.div style={{ ...bgSpring, minHeight: '100vh', width: '100%', overflow: 'hidden', position: 'relative' }}>

            {/* Background & Header (Same as before) */}
            <Container maxWidth="md" sx={{ pt: 8, pb: 4, position: 'relative', zIndex: 2 }}>
                <Stack spacing={2} alignItems="center" textAlign="center" mb={6}>
                    {shop.logo_url && <Avatar src={shop.logo_url} sx={{ width: 80, height: 80, border: '4px solid white', boxShadow: 3 }} />}
                    <Typography variant="h4" fontWeight="800">{shop.name}</Typography>
                </Stack>

                <animated.div style={fadeIn}>
                    <Paper
                        elevation={12}
                        sx={{
                            p: 6,
                            borderRadius: '32px',
                            background: 'rgba(255, 255, 255, 0.9)',
                            backdropFilter: 'blur(20px)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 3,
                            minHeight: 450,
                            border: flowState === 'listening' ? `2px solid ${shop.primary_color || '#1976d2'}` : 'none'
                        }}
                    >
                        {/* Status Area */}
                        <Box sx={{ minHeight: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
                            {flowState === 'idle' && <Typography variant="h5" color="text.secondary">Tap & Say "Join Queue"</Typography>}

                            {/* Dynamic prompt display */}
                            {(flowState === 'asking_name' || flowState === 'asking_phone' || flowState === 'asking_service') && (
                                <Typography variant="h5" fontWeight="bold" textAlign="center">{feedbackMessage}</Typography>
                            )}

                            {/* Transcript */}
                            {transcript && <Typography variant="body1" color="primary" sx={{ mt: 1, fontStyle: 'italic' }}>"{transcript}"</Typography>}
                        </Box>

                        {/* Visualizer & Mic */}
                        <Box sx={{ position: 'relative', mb: 2 }}>
                            {isListening && (
                                <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '100%', height: '100%', borderRadius: '50%', animation: `${pulseGlow} 2s infinite` }} />
                            )}
                            <IconButton
                                onClick={isListening ? stopListening : startListening}
                                disabled={flowState === 'processing' || flowState === 'success'}
                                sx={{
                                    width: 120,
                                    height: 120,
                                    bgcolor: isListening ? 'error.main' : 'primary.main',
                                    color: 'white',
                                    '&:hover': { bgcolor: isListening ? 'error.dark' : 'primary.dark', transform: 'scale(1.05)' },
                                    boxShadow: '0 10px 40px rgba(0,0,0,0.3)',
                                    transition: 'all 0.3s'
                                }}
                            >
                                {isListening ? <GraphicEqIcon sx={{ fontSize: 60 }} /> : <MicIcon sx={{ fontSize: 60 }} />}
                            </IconButton>
                        </Box>

                        {/* Progress Steps */}
                        {flowState !== 'idle' && flowState !== 'error' && flowState !== 'success' && (
                            <Box sx={{ width: '100%', mt: 2 }}>
                                <Stack direction="row" spacing={1} justifyContent="center" mb={1}>
                                    <Chip label="Name" color={['asking_name', 'asking_phone', 'asking_service', 'processing'].includes(flowState) || customerName ? "primary" : "default"} />
                                    <Chip label="Phone" color={['asking_phone', 'asking_service', 'processing'].includes(flowState) || customerPhone ? "primary" : "default"} />
                                    <Chip label="Service" color={['asking_service', 'processing'].includes(flowState) || selectedService ? "primary" : "default"} />
                                </Stack>
                                <LinearProgress variant={flowState === 'processing' ? "indeterminate" : "determinate"} value={
                                    flowState === 'asking_name' ? 33 :
                                        flowState === 'asking_phone' ? 66 :
                                            flowState === 'asking_service' ? 90 : 100
                                } />
                            </Box>
                        )}

                        {/* Filled Data Display */}
                        <Stack spacing={1} direction="row" flexWrap="wrap" justifyContent="center">
                            {customerName && <Chip label={customerName} avatar={<Avatar>{customerName[0]}</Avatar>} />}
                            {customerPhone && <Chip label={customerPhone} icon={<RecordVoiceOverIcon />} />}
                            {selectedService && <Chip label={selectedService.name} color="secondary" />}
                        </Stack>

                        {/* Manual Action Fallback */}
                        <Button variant="text" size="small" onClick={() => navigate(`/queue/${shop.id}`)} sx={{ mt: 'auto' }}>
                            Prefer to type? Switch to Manual Form
                        </Button>

                    </Paper>
                </animated.div>
            </Container>
        </animated.div>
    );
};

export default AIShopPublicPage;
