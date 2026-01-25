import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Typography,
    IconButton,
    Fade,
    Stack,
    CircularProgress,
    Card,
    CardContent,
    Button,
    Avatar,
    TextField,
    Chip
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import MicIcon from '@mui/icons-material/Mic';
import MicOffIcon from '@mui/icons-material/MicOff';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import axios from 'axios';
import { useVoiceInterface } from '../../hooks/useVoiceInterface';
import { useAudioVisualizer } from '../../hooks/useAudioVisualizer';
import ParticleSphere from '../../components/agent/ParticleSphere';
import { useNavigate } from 'react-router-dom';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';

import Pricing from './Pricing';
import Features from './Features';
import FAQ from './FAQ';

const MasterAIAgent: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isDarkMode, setIsDarkMode] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);

    // Updated State Type for Dynamic Layout
    const [chatHistory, setChatHistory] = useState<Array<{
        role: 'ai' | 'user',
        text: string,
        shops?: any[],
        relatedViewer?: 'shops' | 'pricing' | 'features' | 'faq' | null
    }>>([
        { role: 'ai', text: "Welcome to ZeroQwait! I'm ZeroQ. How can I help you today?" }
    ]);

    const scrollRef = useRef<HTMLDivElement>(null);
    const latestAIResponse = chatHistory[chatHistory.length - 1]?.role === 'ai' ? chatHistory[chatHistory.length - 1] : null;
    const navigate = useNavigate();

    const { isListening, transcript, startListening, stopListening, speak } = useVoiceInterface({
        onResult: (text) => {
            console.log('[DEBUG] Voice transcript result:', text);
            handleChat(text);
        },
        onError: (err) => console.error('[DEBUG] Voice interface error:', err)
    });

    const { volume } = useAudioVisualizer(isListening);

    // Theme & Visibility Configuration
    const theme = {
        bg: isDarkMode
            ? 'radial-gradient(ellipse 80% 50% at 50% -20%, hsl(270, 50%, 15%), #05050A)' // Deep violet dark mode
            : 'radial-gradient(ellipse 80% 50% at 50% -20%, hsl(270, 80%, 90%), #FFFFFF)', // Bright violet light mode - Matches Hero
        glass: isDarkMode ? 'blur(20px)' : 'blur(40px)', // Reduced blur for crisper bg visibility
        text: isDarkMode ? '#ffffff' : '#0f172a',
        textSecondary: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(15, 23, 42, 0.7)',
        accent: isDarkMode ? '#E879F9' : '#C026D3', // Fuchsia 400 (Dark) / Fuchsia 600 (Light) - Vibrant & Neon
        cardBg: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.6)',
        cardBorder: isDarkMode ? 'rgba(232, 121, 249, 0.2)' : 'rgba(192, 38, 211, 0.15)',
        inputBg: isDarkMode ? 'rgba(255, 255, 255, 0.07)' : 'rgba(255, 255, 255, 0.8)',
        iconColor: isDarkMode ? '#ffffff' : '#0f172a'
    };

    // Visibility & Global Triggers
    useEffect(() => {
        const handleToggle = () => {
            console.log('[DEBUG] AI Assistant trigger received');
            setIsOpen(prev => !prev);
        };
        window.addEventListener('trigger-zeroq-assistant', handleToggle);

        return () => {
            window.removeEventListener('trigger-zeroq-assistant', handleToggle);
        };
    }, []);

    // Handle initial speech when opening
    useEffect(() => {
        if (isOpen && chatHistory.length === 1) {
            speak(chatHistory[0].text);
        }
    }, [isOpen]);

    const handleChat = async (userText: string) => {
        if (!userText.trim()) return;

        setChatHistory(prev => [...prev, { role: 'user', text: userText }]);
        setIsProcessing(true);

        try {
            // MOCK INTENT DETECTION FOR DEMO PURPOSES
            // In a real app, the backend would return 'relatedViewer' or 'action'
            const lowerText = userText.toLowerCase();
            let relatedViewer: 'shops' | 'pricing' | 'features' | 'faq' | null = null;

            if (lowerText.includes('pricing') || lowerText.includes('cost') || lowerText.includes('plan')) {
                relatedViewer = 'pricing';
            } else if (lowerText.includes('feature') || lowerText.includes('what can you do')) {
                relatedViewer = 'features';
            } else if (lowerText.includes('help') || lowerText.includes('faq') || lowerText.includes('question')) {
                relatedViewer = 'faq';
            }

            const response = await axios.post('/agent/master/chat', {
                message: userText,
                history: chatHistory.map(h => ({
                    role: h.role === 'ai' ? 'assistant' : 'user',
                    content: h.text
                }))
            });

            const { response: agentText, actions } = response.data;
            let shopResults: any[] = [];

            actions.forEach((action: any) => {
                if (action.tool === 'navigate_to_page_section') {
                    // We might handle scroll here, OR if we have relatedViewer, we stay in overlay
                    if (!relatedViewer) {
                        const sectionId = action.result.target;
                        const element = document.getElementById(sectionId);
                        if (element) {
                            element.scrollIntoView({ behavior: 'smooth' });
                            setTimeout(() => setIsOpen(false), 2000);
                        }
                    }
                } else if (action.tool === 'search_shops') {
                    shopResults = action.result;
                    if (shopResults.length > 0) relatedViewer = 'shops';
                }
            });

            setChatHistory(prev => [...prev, { role: 'ai', text: agentText, shops: shopResults, relatedViewer }]);
            setIsProcessing(false);
            speak(agentText);
        } catch (err) {
            console.warn('[MasterAIAgent] Backend unreachable, using offline fallback for demo');

            // Fallback logic for demo purposes (if backend is down)
            const lowerText = userText.toLowerCase();
            let fallbackText = "I'm having trouble connecting to the server, but I can still help navigate.";
            let fallbackViewer: any = null;

            if (lowerText.includes('pricing') || lowerText.includes('cost')) {
                fallbackText = "Here are our pricing plans. We offer flexible tiers for every business size.";
                fallbackViewer = 'pricing';
            } else if (lowerText.includes('feature')) {
                fallbackText = "Check out our key features. We simplify queue management for you.";
                fallbackViewer = 'features';
            } else if (lowerText.includes('help') || lowerText.includes('faq')) {
                fallbackText = "Here are some frequently asked questions to help you get started.";
                fallbackViewer = 'faq';
            }

            if (fallbackViewer) {
                setChatHistory(prev => [...prev, { role: 'ai', text: fallbackText, relatedViewer: fallbackViewer }]);
                speak(fallbackText);
            } else {
                setChatHistory(prev => [...prev, { role: 'ai', text: "I'm sorry, I cannot connect to the brain right now. Please try again later." }]);
            }

            setIsProcessing(false);
        }
    };

    // Auto-scroll to bottom of chat
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({
                top: scrollRef.current.scrollHeight,
                behavior: 'smooth'
            });
        }
    }, [chatHistory, transcript]);


    return (
        <Fade in={isOpen}>
            <Box
                id="immersive-ai-overlay"
                sx={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    width: '100vw',
                    height: '100vh',
                    zIndex: 10000,
                    background: theme.bg,
                    backdropFilter: theme.glass,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: theme.text,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    transition: 'all 0.5s ease'
                }}
            >
                {/* Controls Top Right */}
                <Stack direction="row" spacing={2} sx={{ position: 'absolute', top: 40, right: 40 }}>
                    <IconButton
                        onClick={() => setIsDarkMode(!isDarkMode)}
                        sx={{
                            color: theme.iconColor,
                            bgcolor: isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(15,23,42,0.05)',
                            '&:hover': { bgcolor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.1)' }
                        }}
                    >
                        {isDarkMode ? <LightModeIcon sx={{ fontSize: 24 }} /> : <DarkModeIcon sx={{ fontSize: 24 }} />}
                    </IconButton>
                    <IconButton
                        onClick={() => setIsOpen(false)}
                        sx={{
                            color: theme.iconColor,
                            bgcolor: isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(15,23,42,0.05)',
                            '&:hover': { bgcolor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(15,23,42,0.1)' }
                        }}
                    >
                        <CloseIcon sx={{ fontSize: 32 }} />
                    </IconButton>
                </Stack>

                <Box
                    sx={{
                        flex: 1,
                        width: '100%',
                        height: '100%',
                        overflowY: 'auto',
                        overflowX: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                        position: 'relative',
                        zIndex: 1,
                        '&::-webkit-scrollbar': { width: '6px' },
                        '&::-webkit-scrollbar-track': { background: 'transparent' },
                        '&::-webkit-scrollbar-thumb': {
                            background: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                            borderRadius: '10px'
                        }
                    }}
                >
                    {/* Main Content Wrapper - Centers or Splits */}
                    <Box sx={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: latestAIResponse?.relatedViewer ? { xs: 'column', md: 'row' } : 'column',
                        alignItems: latestAIResponse?.relatedViewer ? 'flex-start' : 'center',
                        justifyContent: latestAIResponse?.relatedViewer ? 'space-between' : 'center', // Spread out
                        py: latestAIResponse?.relatedViewer ? 4 : 10,
                        px: latestAIResponse?.relatedViewer ? 8 : 0, // More padding on sides
                        gap: 2,
                        width: '100%',
                        maxWidth: '1600px', // Allow wider layout
                        mx: 'auto',
                        height: '100%',
                        minHeight: 'min-content'
                    }}>

                        {/* LEFT COLUMN: Agent, Transcript & Controls (Moves left when content shows) */}
                        <Box sx={{
                            flex: latestAIResponse?.relatedViewer ? '0 0 400px' : 'none', // Fixed width when split
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 4,
                            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                            width: latestAIResponse?.relatedViewer ? '400px' : 'auto',
                            maxWidth: latestAIResponse?.relatedViewer ? '400px' : '800px',
                            position: latestAIResponse?.relatedViewer ? 'sticky' : 'relative',
                            top: latestAIResponse?.relatedViewer ? 20 : 'auto',
                        }}>
                            {/* The Particle Sphere */}
                            <Box sx={{ position: 'relative', width: 300, height: 300, transition: 'all 0.8s ease' }}>
                                <ParticleSphere volume={volume} isListening={isListening} color={theme.accent} />
                                {isProcessing && (
                                    <CircularProgress
                                        size={200}
                                        thickness={1}
                                        sx={{
                                            position: 'absolute',
                                            top: '50%',
                                            left: '50%',
                                            marginTop: '-100px',
                                            marginLeft: '-100px',
                                            color: theme.accent,
                                            opacity: 0.5,
                                            animationDuration: '1s',
                                        }}
                                    />
                                )}
                            </Box>

                            {/* Scrollable Transcript - More compact when split */}
                            <Box
                                ref={scrollRef}
                                sx={{
                                    textAlign: 'center',
                                    maxHeight: latestAIResponse?.relatedViewer ? '25vh' : '30vh',
                                    overflowY: 'auto',
                                    width: '100%',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 2,
                                    maskImage: 'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)',
                                    WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)',
                                    '&::-webkit-scrollbar': { display: 'none' },
                                }}
                            >
                                {chatHistory.map((chat, index) => (
                                    <Box key={index} sx={{ opacity: index === chatHistory.length - 1 ? 1 : 0.6 }}>
                                        <Typography
                                            variant="body1"
                                            sx={{
                                                fontWeight: index === chatHistory.length - 1 ? 500 : 300,
                                                lineHeight: 1.6,
                                                color: chat.role === 'user' ? theme.accent : theme.text,
                                                fontSize: latestAIResponse?.relatedViewer ? '1.1rem' : '1.3rem',
                                                transition: 'all 0.5s ease'
                                            }}
                                        >
                                            {chat.role === 'user' ? `“${chat.text}”` : chat.text}
                                        </Typography>
                                    </Box>
                                ))}

                                {isListening && transcript && (
                                    <Typography
                                        variant="body1"
                                        sx={{
                                            fontWeight: 300,
                                            lineHeight: 1.6,
                                            color: isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
                                            fontSize: '1.2rem',
                                            fontStyle: 'italic',
                                        }}
                                    >
                                        {transcript}
                                    </Typography>
                                )}
                            </Box>

                            {/* Interaction Footer - MOVED INSIDE LEFT COLUMN */}
                            <Box
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: 2,
                                    width: '100%'
                                }}
                            >
                                <IconButton
                                    onClick={() => {
                                        if (!window.isSecureContext && window.location.hostname !== 'localhost') {
                                            alert("Microphone access requires a secure connection (HTTPS). Please try accessing via localhost or a secure domain.");
                                            return;
                                        }
                                        isListening ? stopListening() : startListening();
                                    }}
                                    sx={{
                                        width: 80,
                                        height: 80,
                                        bgcolor: isListening ? theme.accent : theme.cardBg,
                                        color: isListening ? (isDarkMode ? 'black' : 'white') : theme.text,
                                        '&:hover': { bgcolor: isListening ? theme.accent : theme.inputBg },
                                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                        border: `2px solid ${theme.cardBorder}`,
                                        boxShadow: isListening ? `0 0 50px ${theme.accent}88` : 'none'
                                    }}
                                >
                                    {isListening ? <MicIcon sx={{ fontSize: 40 }} /> : <MicOffIcon sx={{ fontSize: 40 }} />}
                                </IconButton>

                                <Typography variant="caption" sx={{ opacity: 0.6, letterSpacing: '0.1em', fontWeight: 600 }}>
                                    {isListening ? "LISTENING..." : "START VOICE CONVERSATION"}
                                </Typography>

                                {!isListening && (
                                    <TextField
                                        fullWidth
                                        placeholder="Type or speak to ZeroQ..."
                                        variant="outlined"
                                        sx={{ maxWidth: 400 }}
                                        onKeyPress={(e) => {
                                            if (e.key === 'Enter') {
                                                const target = e.target as HTMLInputElement;
                                                handleChat(target.value);
                                                target.value = '';
                                            }
                                        }}
                                        slotProps={{
                                            input: {
                                                sx: {
                                                    borderRadius: '30px',
                                                    bgcolor: theme.inputBg,
                                                    color: theme.text,
                                                    backdropFilter: 'blur(10px)',
                                                    '& fieldset': { borderColor: theme.cardBorder },
                                                    '&:hover fieldset': { borderColor: theme.accent },
                                                    '&.Mui-focused fieldset': { borderColor: theme.accent, borderWidth: '2px' }
                                                },
                                                endAdornment: <SearchIcon sx={{ color: theme.textSecondary, mr: 1 }} />
                                            }
                                        }}
                                    />
                                )}
                            </Box>
                        </Box>

                        {/* RIGHT COLUMN: Dynamic Content Viewer */}
                        {latestAIResponse?.relatedViewer && (
                            <Fade in={true} timeout={1000}>
                                <Box sx={{
                                    flex: 1, // Take all remaining space
                                    width: '100%',
                                    height: '100%',
                                    maxHeight: '90vh', // Slightly taller
                                    overflowY: 'auto',
                                    p: 4,
                                    bgcolor: isDarkMode ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.7)',
                                    borderRadius: '32px',
                                    border: `1px solid ${theme.cardBorder}`,
                                    backdropFilter: 'blur(20px)',
                                    boxShadow: '0 20px 80px rgba(0,0,0,0.1)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center', // Center content horizontally inside
                                    '&::-webkit-scrollbar': { width: '4px' },
                                    '&::-webkit-scrollbar-thumb': { bgcolor: theme.accent, borderRadius: '4px' }
                                }}>
                                    {/* Shops View */}
                                    {latestAIResponse.relatedViewer === 'shops' && (
                                        <Stack spacing={3} sx={{ width: '100%' }}>
                                            <Typography variant="h5" sx={{ fontWeight: 600 }}>Nearby Verified Queues</Typography>
                                            {latestAIResponse.shops?.map((shop: any) => (
                                                <Card key={shop.id} sx={{ bgcolor: theme.cardBg, borderRadius: '20px', border: `1px solid ${theme.cardBorder}` }}>
                                                    <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                                        <Avatar src={shop.logo_url} sx={{ width: 60, height: 60, borderRadius: '12px' }} />
                                                        <Box sx={{ flex: 1 }}>
                                                            <Typography variant="h6">{shop.name}</Typography>
                                                            <Typography variant="body2" sx={{ opacity: 0.7 }}>{shop.address}, {shop.city}</Typography>
                                                        </Box>
                                                        <Button variant="contained" sx={{ bgcolor: theme.accent, borderRadius: '12px' }} onClick={() => navigate(`/s/${shop.slug}`)}>Join</Button>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </Stack>
                                    )}

                                    {/* Pricing View */}
                                    {latestAIResponse.relatedViewer === 'pricing' && (
                                        <Box sx={{ width: '100%', pointerEvents: 'auto' }}>
                                            <Pricing />
                                        </Box>
                                    )}

                                    {/* Features View */}
                                    {latestAIResponse.relatedViewer === 'features' && (
                                        <Box sx={{ width: '100%', pointerEvents: 'auto', transform: 'scale(0.95)', transformOrigin: 'top center' }}>
                                            <Features />
                                        </Box>
                                    )}

                                    {/* FAQ View */}
                                    {latestAIResponse.relatedViewer === 'faq' && (
                                        <Box sx={{ width: '100%', pointerEvents: 'auto' }}>
                                            <FAQ />
                                        </Box>
                                    )}
                                </Box>
                            </Fade>
                        )}
                    </Box>
                </Box>
            </Box>
        </Fade>
    );
};

export default MasterAIAgent;
