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
    LinearProgress,
    Fade
} from '@mui/material';
import { useSpring, animated, config } from '@react-spring/web';
import MicIcon from '@mui/icons-material/Mic';
import GraphicEqIcon from '@mui/icons-material/GraphicEq';
import SmartToyIcon from '@mui/icons-material/SmartToy';
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

// --- UI Components ---

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
    const { shopId } = useParams<{ shopId: string }>();
    const navigate = useNavigate();

    // Data States
    const [shop, setShop] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // UI State
    const [isProcessing, setIsProcessing] = useState(false);
    const [feedbackMessage, setFeedbackMessage] = useState("Hi! Tap the mic to join.");
    const [chatHistory, setChatHistory] = useState<Array<{ role: 'ai' | 'user', text: string }>>([
        { role: 'ai', text: "Hi! I'm the intelligent front desk. How can I help you today?" }
    ]);

    // Voice Interface
    const { isListening, transcript, startListening, stopListening, speak, isSupported } = useVoiceInterface({
        continuous: false,
        onResult: (text) => handleAgenticChat(text)
    });

    // Animation springs
    const fadeIn = useSpring({
        from: { opacity: 0, transform: 'translateY(50px)' },
        to: { opacity: 1, transform: 'translateY(0px)' },
        config: config.molasses,
    });

    const bgSpring = useSpring({
        to: { background: shop?.primary_color ? `linear-gradient(135deg, ${shop.primary_color}11, #ffffff)` : '#f5f5f5' },
        config: config.gentle
    });

    useEffect(() => {
        fetchShopData();
    }, [shopId]);

    const fetchShopData = async () => {
        try {
            const isSlug = isNaN(Number(shopId));
            const endpoint = isSlug ? `/shops/public/${shopId}` : `/shops/${shopId}`;
            const response = await axios.get(endpoint);
            setShop(response.data);
            setLoading(false);

            // Initial Warm Greeting
            setTimeout(() => {
                speak(`Welcome to ${response.data.name}. How can I assist you?`);
            }, 1000);
        } catch (err) {
            setError('Could not load shop details');
            setLoading(false);
        }
    };

    const handleAgenticChat = async (userText: string) => {
        if (!userText.trim()) return;

        // Add to history
        setChatHistory(prev => [...prev, { role: 'user', text: userText }]);
        setIsProcessing(true);
        setFeedbackMessage("Thinking...");

        try {
            // Call the NEW backend agent endpoint
            const response = await axios.post(`/api/agent/${shop.id}/chat`, {
                message: userText,
                history: chatHistory.map(h => ({ role: h.role === 'ai' ? 'assistant' : 'user', content: h.text }))
            });

            const { response: agentText, actions } = response.data;

            // Add AI response to history
            setChatHistory(prev => [...prev, { role: 'ai', text: agentText }]);
            setFeedbackMessage(agentText);
            setIsProcessing(false);

            // Speak response
            speak(agentText);

            // Handle Agentic Actions (e.g., successful enrollment)
            const enrollment = actions.find((a: any) => a.tool === 'enroll_customer' && a.result.success);
            if (enrollment) {
                setTimeout(() => {
                    navigate(`/queue/${shop.id}`);
                }, 4000);
            }

        } catch (err) {
            console.error("Agent Error:", err);
            setIsProcessing(false);
            setFeedbackMessage("I'm sorry, I'm having trouble thinking right now. Please try again.");
            speak("I'm sorry, I encountered an error.");
        }
    };

    if (loading) return <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh"><CircularProgress /></Box>;
    if (error || !shop) return <Container maxWidth="sm" sx={{ mt: 10 }}><Alert severity="error">{error || "Shop not found"}</Alert></Container>;

    return (
        <animated.div style={{ ...bgSpring, minHeight: '100vh', width: '100%', overflow: 'hidden', position: 'relative' }}>

            <Container maxWidth="md" sx={{ pt: 8, pb: 4, position: 'relative', zIndex: 2 }}>
                <Stack spacing={2} alignItems="center" textAlign="center" mb={6}>
                    {shop.logo_url && <Avatar src={shop.logo_url} sx={{ width: 80, height: 80, border: '4px solid white', boxShadow: 3 }} />}
                    <Typography variant="h3" fontWeight="900" sx={{ letterSpacing: '-2px' }}>{shop.name}</Typography>
                    <Chip icon={<SmartToyIcon fontSize="small" />} label="Intelligent Front Desk" color="primary" variant="outlined" />
                </Stack>

                <animated.div style={fadeIn}>
                    <Paper
                        elevation={12}
                        sx={{
                            p: 4,
                            borderRadius: '40px',
                            background: 'rgba(255, 255, 255, 0.95)',
                            backdropFilter: 'blur(30px)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 3,
                            minHeight: 500,
                            position: 'relative',
                            overflow: 'hidden'
                        }}
                    >
                        {isProcessing && <LinearProgress sx={{ position: 'absolute', top: 0, left: 0, right: 0, height: 6 }} />}

                        {/* Interaction Hub */}
                        <Box sx={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>

                            {/* Large Message Display */}
                            <Fade in={true} key={feedbackMessage}>
                                <Typography
                                    variant="h4"
                                    textAlign="center"
                                    sx={{
                                        fontWeight: 600,
                                        lineHeight: 1.2,
                                        maxWidth: '85%',
                                        color: isProcessing ? 'text.disabled' : 'text.primary'
                                    }}
                                >
                                    {feedbackMessage}
                                </Typography>
                            </Fade>

                            {/* Voice Visuals */}
                            <Box sx={{ position: 'relative' }}>
                                {isListening && (
                                    <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: '180%', height: '180%', borderRadius: '50%', animation: `${pulseGlow} 2s infinite` }} />
                                )}
                                <IconButton
                                    onClick={isListening ? stopListening : startListening}
                                    disabled={isProcessing}
                                    sx={{
                                        width: 140,
                                        height: 140,
                                        bgcolor: isListening ? 'error.main' : 'primary.main',
                                        color: 'white',
                                        transition: 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                                        '&:hover': { transform: 'scale(1.1)', bgcolor: isListening ? 'error.dark' : 'primary.dark' },
                                        boxShadow: isListening ? '0 0 40px rgba(244, 67, 54, 0.5)' : '0 20px 50px rgba(25, 118, 210, 0.3)'
                                    }}
                                >
                                    {isListening ? <GraphicEqIcon sx={{ fontSize: 70 }} /> : <MicIcon sx={{ fontSize: 70 }} />}
                                </IconButton>
                            </Box>

                            {transcript && (
                                <Typography variant="h6" color="primary" sx={{ fontStyle: 'italic', opacity: 0.8 }}>
                                    "{transcript}"
                                </Typography>
                            )}
                        </Box>

                        {/* Recent History (Minimalist) */}
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'center' }}>
                            {chatHistory.slice(-2).map((msg, i) => (
                                <Chip
                                    key={i}
                                    label={msg.text}
                                    size="small"
                                    variant="filled"
                                    sx={{ maxWidth: 200, bgcolor: msg.role === 'ai' ? 'grey.100' : 'primary.50' }}
                                />
                            ))}
                        </Box>

                        <Button
                            variant="text"
                            color="inherit"
                            size="small"
                            onClick={() => navigate(`/queue/${shop.id}`)}
                            sx={{ opacity: 0.5, '&:hover': { opacity: 1 } }}
                        >
                            Switch to Manual Entry
                        </Button>
                    </Paper>
                </animated.div>
            </Container>
        </animated.div>
    );
};

export default AIShopPublicPage;
