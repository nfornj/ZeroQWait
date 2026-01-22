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
    Fade,
    Button,
    Chip,
    LinearProgress,
    TextField,
    InputAdornment
} from '@mui/material';
import { useSpring, animated, config } from '@react-spring/web';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import CloseIcon from '@mui/icons-material/Close';
import axios from 'axios';
import { useVoiceInterface } from '../hooks/useVoiceInterface';
import { useAudioVisualizer } from '../hooks/useAudioVisualizer';
import CanvasOrb from '../components/agent/CanvasOrb';

const AIShopPublicPage: React.FC = () => {
    const { shopId } = useParams<{ shopId: string }>();
    const navigate = useNavigate();
    const theme = { palette: { primary: { main: '#1976d2' } } }; // Fallback

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

    // Audio & Voice hooks
    const { isListening, transcript, startListening, stopListening, speak } = useVoiceInterface({
        continuous: false,
        onResult: (text) => handleAgenticChat(text)
    });

    const { volume } = useAudioVisualizer(isListening);

    // Animation springs
    const fadeIn = useSpring({
        from: { opacity: 0, scale: 0.9 },
        to: { opacity: 1, scale: 1 },
        config: config.gentle,
    });

    useEffect(() => {
        fetchShopData();
    }, [shopId]);

    const fetchShopData = async () => {
        try {
            const isSlug = isNaN(Number(shopId));
            const endpoint = isSlug ? `/shops/s/${shopId}` : `/shops/${shopId}`;
            const response = await axios.get(endpoint);
            setShop(response.data);
            setLoading(false);

            setTimeout(() => {
                const agentName = response.data.ai_agent_name || response.data.name;
                speak(`Welcome to ${response.data.name}. I'm ${agentName}, your AI assistant. How can I help you join the queue?`);
            }, 1000);
        } catch (err) {
            setError('Could not load shop details');
            setLoading(false);
        }
    };

    const handleAgenticChat = async (userText: string) => {
        if (!userText.trim()) return;

        setChatHistory(prev => [...prev, { role: 'user', text: userText }]);
        setIsProcessing(true);
        setFeedbackMessage("Thinking...");

        try {
            const response = await axios.post(`/agent/chat/${shop.id}`, {
                message: userText,
                history: chatHistory.map(h => ({
                    role: h.role === 'ai' ? 'assistant' : 'user',
                    content: h.text
                }))
            });

            const { response: agentText, actions } = response.data;

            setChatHistory(prev => [...prev, { role: 'ai', text: agentText }]);
            setFeedbackMessage(agentText);
            setIsProcessing(false);
            speak(agentText);

            const enrollment = actions.find((a: any) => a.tool === 'enroll_customer' && a.result.success);
            if (enrollment) {
                setTimeout(() => navigate(`/queue/${shop.id}`), 4000);
            }

        } catch (err) {
            setIsProcessing(false);
            setFeedbackMessage("I'm sorry, I'm having trouble thinking. Please try again or use the manual button.");
            speak("I encountered an error. Please try again.");
        }
    };

    const handleClose = () => {
        if (window.confirm("Do you want to exit the AI assistant?")) {
            navigate(-1);
        }
    };

    if (loading) return <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh"><CircularProgress /></Box>;
    if (error || !shop) return <Container maxWidth="sm" sx={{ mt: 10 }}><Alert severity="error">{error || "Shop not found"}</Alert></Container>;

    const primaryColor = shop.primary_color || '#1976d2';

    return (
        <Box
            sx={{
                minHeight: '100vh',
                width: '100%',
                background: `linear-gradient(135deg, ${primaryColor}15, #ffffff)`,
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                overflow: 'hidden'
            }}
        >
            {/* Top Control Bar */}
            <Box sx={{ p: 2, display: 'flex', justifyContent: 'flex-end', zIndex: 10 }}>
                <IconButton
                    onClick={handleClose}
                    onPointerDown={(e) => e.currentTarget.style.transform = 'scale(0.9)'}
                    onPointerUp={(e) => e.currentTarget.style.transform = 'scale(1)'}
                    sx={{ bgcolor: 'white', '&:hover': { bgcolor: 'grey.100' }, boxShadow: 2 }}
                >
                    <CloseIcon />
                </IconButton>
            </Box>

            <Container maxWidth="md" sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pb: 8 }}>

                <animated.div style={fadeIn}>
                    <Stack spacing={2} alignItems="center" textAlign="center" mb={4}>
                        <Avatar src={shop.logo_url} sx={{ width: 80, height: 80, border: '4px solid white', boxShadow: 3 }} />
                        <Typography variant="h3" fontWeight="900" sx={{ letterSpacing: '-2px', color: 'text.primary' }}>
                            {shop.name}
                        </Typography>
                        <Chip icon={<SmartToyIcon fontSize="small" />} label="Intelligent Concierge" color="primary" variant="outlined" />
                    </Stack>

                    <Paper
                        elevation={0}
                        sx={{
                            p: 4,
                            borderRadius: '50px',
                            background: 'rgba(255, 255, 255, 0.7)',
                            backdropFilter: 'blur(40px)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            minHeight: 550,
                            width: { xs: '100%', sm: 500 },
                            position: 'relative',
                        }}
                    >
                        {isProcessing && <LinearProgress sx={{ position: 'absolute', top: 0, left: '10%', right: '10%', borderRadius: 10, mt: 2 }} />}

                        {/* Speech Feedback Area */}
                        <Box sx={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>

                            <Fade in={true} key={feedbackMessage}>
                                <Typography
                                    variant="h5"
                                    textAlign="center"
                                    sx={{
                                        fontWeight: 600,
                                        lineHeight: 1.4,
                                        color: isProcessing ? 'text.disabled' : 'text.primary',
                                        px: 2,
                                        minHeight: '3em',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center'
                                    }}
                                >
                                    {feedbackMessage}
                                </Typography>
                            </Fade>

                            {/* Voice Support Warning (for HTTP environments) */}
                            {!isListening && !isProcessing && (
                                <Box sx={{ width: '100%', mt: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                                    {transcript ? (
                                        <Typography
                                            variant="h6"
                                            color="primary"
                                            sx={{
                                                fontStyle: 'italic',
                                                backgroundColor: `${primaryColor}10`,
                                                px: 3,
                                                py: 1,
                                                borderRadius: 10
                                            }}
                                        >
                                            "{transcript}"
                                        </Typography>
                                    ) : (
                                        <Box
                                            component="form"
                                            onSubmit={(e: any) => {
                                                e.preventDefault();
                                                const val = e.target.elements.chatInput.value;
                                                if (val) {
                                                    handleAgenticChat(val);
                                                    e.target.elements.chatInput.value = '';
                                                }
                                            }}
                                            sx={{ width: '100%', maxWidth: 400 }}
                                        >
                                            <TextField
                                                name="chatInput"
                                                fullWidth
                                                placeholder="Ask me anything..."
                                                variant="outlined"
                                                size="small"
                                                sx={{
                                                    '& .MuiOutlinedInput-root': {
                                                        borderRadius: 10,
                                                        backgroundColor: 'rgba(255,255,255,0.8)'
                                                    }
                                                }}
                                            />
                                        </Box>
                                    )}
                                </Box>
                            )}

                            {/* The Animated Canvas Orb */}
                            <Box
                                sx={{
                                    position: 'relative',
                                    cursor: 'pointer',
                                    transition: 'transform 0.2s',
                                    '&:active': { transform: 'scale(0.95)' },
                                    opacity: isProcessing ? 0.6 : 1
                                }}
                                onPointerDown={(e) => {
                                    if (!isProcessing) isListening ? stopListening() : startListening();
                                }}
                            >
                                <CanvasOrb
                                    volume={volume}
                                    isListening={isListening}
                                    primaryColor={primaryColor}
                                />
                            </Box>

                            {isListening && (
                                <Typography variant="body1" color="primary" sx={{ fontStyle: 'italic', animation: 'pulse 1.5s infinite' }}>
                                    {transcript ? `"${transcript}"` : "Listening..."}
                                </Typography>
                            )}
                        </Box>

                        {/* Recent History */}
                        <Stack direction="row" spacing={1} sx={{ mt: 2, mb: 4 }}>
                            {chatHistory.slice(-2).map((msg, i) => (
                                <Chip
                                    key={i}
                                    label={msg.text}
                                    size="small"
                                    sx={{ maxWidth: 150, fontSize: '0.75rem' }}
                                />
                            ))}
                        </Stack>

                        <Button
                            variant="outlined"
                            onClick={() => navigate(`/queue/${shop.id}`)}
                            sx={{ borderRadius: 10, px: 4 }}
                        >
                            Switch to Manual Form
                        </Button>
                    </Paper>
                </animated.div>
            </Container>
        </Box>
    );
};

export default AIShopPublicPage;
