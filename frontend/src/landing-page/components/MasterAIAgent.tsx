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
    const [location, setLocation] = useState<{ lat: number, lng: number } | null>(null);

    // Capture Geolocation
    useEffect(() => {
        if ("geolocation" in navigator) {
            navigator.geolocation.getCurrentPosition(
                (pos) => setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
                (err) => console.warn('[MasterAIAgent] Geolocation denied or unavailable:', err)
            );
        }
    }, []);

    // Updated State Type for Dynamic Layout
    const [chatHistory, setChatHistory] = useState<Array<{
        role: 'ai' | 'user',
        text: string,
        shops?: any[],
        relatedViewer?: 'shops' | 'pricing' | 'features' | 'faq' | null
    }>>([
        { role: 'ai', text: "Welcome to ZeroQwait! I'm ZeroQ. How can I help you today?" }
    ]);

    const [activeViewer, setActiveViewer] = useState<'shops' | 'pricing' | 'features' | 'faq' | null>(null);
    const [activeShops, setActiveShops] = useState<any[]>([]);

    const scrollRef = useRef<HTMLDivElement>(null);
    const latestAIResponse = chatHistory[chatHistory.length - 1];
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
            const response = await axios.post('/agent/master/chat', {
                message: userText,
                latitude: location?.lat,
                longitude: location?.lng,
                history: chatHistory.map(h => ({
                    role: h.role === 'ai' ? 'assistant' : 'user',
                    content: h.text
                }))
            });

            const { response: agentText, actions } = response.data;
            let currentShops = [...activeShops];
            let currentViewer = activeViewer;

            console.log('[DEBUG] MasterAgent COMPLETE Response:', response.data);

            if (actions && Array.isArray(actions)) {
                // Actions OVERRIDE current state
                actions.forEach((action: any) => {
                    if (action.tool === 'navigate_to_page_section') {
                        const sectionId = action.result.target;
                        currentViewer = sectionId as any;
                        currentShops = []; // Clear shops if moving to other sections
                    } else if (action.tool === 'search_shops') {
                        const shops = Array.isArray(action.result) ? action.result : (action.result?.shops || []);
                        if (shops.length > 0) {
                            currentShops = shops;
                            currentViewer = 'shops';
                        }
                    }
                });
            }

            // Persistence
            setActiveShops(currentShops);
            setActiveViewer(currentViewer);

            setChatHistory(prev => [...prev, {
                role: 'ai',
                text: agentText,
                shops: currentShops,
                relatedViewer: currentViewer
            }]);

            speak(agentText);
        } catch (error) {
            console.error('[DEBUG] MasterAgent API Error:', error);
            setChatHistory(prev => [...prev, { role: 'ai', text: "I'm sorry, I'm having trouble connecting to my database. Please check your internet or try again in a moment." }]);
        } finally {
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
                <Stack direction="row" spacing={2} sx={{ position: 'absolute', top: 40, right: 40, zIndex: 20000 }}>
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
                        flexDirection: latestAIResponse?.relatedViewer ? { xs: 'column', md: 'row-reverse' } : 'column',
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
                            flex: activeViewer ? '0 0 400px' : 'none', // Fixed width when split
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center', // Vertically center the content
                            gap: 4,
                            transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                            width: activeViewer ? '400px' : 'auto',
                            maxWidth: activeViewer ? '400px' : '800px',
                            minHeight: activeViewer ? '100vh' : 'auto', // Full height to allow centering
                            position: activeViewer ? 'sticky' : 'relative',
                            top: 0,
                        }}>
                            {/* The Particle Sphere */}
                            <Box sx={{ position: 'relative', width: 300, height: 300, transition: 'all 0.8s ease' }}>
                                <ParticleSphere volume={volume} isListening={isListening} color={theme.accent} isProcessing={isProcessing} />
                            </Box>

                            {/* Scrollable Transcript - More compact when split */}
                            <Box
                                ref={scrollRef}
                                sx={{
                                    textAlign: 'center',
                                    maxHeight: activeViewer ? '25vh' : '30vh',
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
                                                fontSize: activeViewer ? '1.1rem' : '1.3rem',
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
                        {activeViewer && (
                            <Fade in={true} timeout={1000}>
                                <Box sx={{
                                    flex: 1, // Take all remaining space
                                    width: '100%',
                                    height: '100%',
                                    maxHeight: '95vh', // Slightly taller
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
                                    justifyContent: 'center', // Vertically center the content
                                    '&::-webkit-scrollbar': { width: '4px' },
                                    '&::-webkit-scrollbar-thumb': { bgcolor: theme.accent, borderRadius: '4px' }
                                }}>
                                    {/* Shops View */}
                                    {activeViewer === 'shops' && (
                                        <Stack spacing={3} sx={{ width: '100%' }}>
                                            <Typography variant="h5" sx={{ fontWeight: 600 }}>Nearby Verified Queues</Typography>
                                            {activeShops?.map((shop: any) => (
                                                <Card
                                                    key={shop.id}
                                                    onClick={() => navigate(`/s/${shop.slug}`)}
                                                    sx={{
                                                        bgcolor: theme.cardBg,
                                                        borderRadius: '24px',
                                                        border: `1px solid ${theme.cardBorder}`,
                                                        cursor: 'pointer',
                                                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                                        overflow: 'visible',
                                                        position: 'relative',
                                                        '&:hover': {
                                                            transform: 'translateY(-4px) scale(1.02)',
                                                            boxShadow: `0 20px 40px -10px ${isDarkMode ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.1)'}`,
                                                            borderColor: theme.accent,
                                                            '& .shop-glow': { opacity: 0.5 }
                                                        }
                                                    }}
                                                >
                                                    {/* Glow Effect */}
                                                    <Box
                                                        className="shop-glow"
                                                        sx={{
                                                            position: 'absolute',
                                                            inset: 0,
                                                            opacity: 0,
                                                            transition: 'opacity 0.3s ease',
                                                            background: `radial-gradient(circle at 50% 0%, ${theme.accent}33, transparent 70%)`,
                                                            borderRadius: '24px',
                                                            pointerEvents: 'none'
                                                        }}
                                                    />

                                                    <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 3, p: 3, '&:last-child': { pb: 3 } }}>
                                                        <Avatar
                                                            src={shop.logo_url}
                                                            variant="rounded"
                                                            sx={{
                                                                width: 80,
                                                                height: 80,
                                                                borderRadius: '16px',
                                                                bgcolor: isDarkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                                                                border: `1px solid ${theme.cardBorder}`
                                                            }}
                                                        >
                                                            {shop.name.charAt(0)}
                                                        </Avatar>

                                                        <Box sx={{ flex: 1 }}>
                                                            <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
                                                                {shop.name}
                                                            </Typography>
                                                            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1, opacity: 0.8 }}>
                                                                <LocationOnIcon fontSize="small" sx={{ color: theme.accent }} />
                                                                <Typography variant="body2">
                                                                    {shop.city}
                                                                </Typography>
                                                            </Stack>
                                                            {/* Status Pill */}
                                                            <Chip
                                                                label="Queue Active"
                                                                size="small"
                                                                sx={{
                                                                    height: 24,
                                                                    bgcolor: `${theme.accent}22`,
                                                                    color: theme.accent,
                                                                    border: `1px solid ${theme.accent}44`,
                                                                    fontWeight: 600,
                                                                    fontSize: '0.75rem'
                                                                }}
                                                            />
                                                        </Box>

                                                        <Button
                                                            variant="contained"
                                                            sx={{
                                                                bgcolor: theme.accent,
                                                                borderRadius: '14px',
                                                                px: 3,
                                                                py: 1.5,
                                                                fontWeight: 700,
                                                                textTransform: 'none',
                                                                boxShadow: `0 8px 20px -8px ${theme.accent}`,
                                                                '&:hover': {
                                                                    bgcolor: theme.accent,
                                                                    filter: 'brightness(1.1)',
                                                                    transform: 'translateY(-1px)'
                                                                }
                                                            }}
                                                        >
                                                            Join
                                                        </Button>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </Stack>
                                    )}

                                    {/* Pricing View */}
                                    {activeViewer === 'pricing' && (
                                        <Box sx={{ width: '100%', py: 4 }}>
                                            <Pricing />
                                        </Box>
                                    )}

                                    {/* Features View */}
                                    {activeViewer === 'features' && (
                                        <Box sx={{ width: '100%', py: 4 }}>
                                            <Features />
                                        </Box>
                                    )}

                                    {/* Highlights/FAQ View */}
                                    {activeViewer === 'faq' && (
                                        <Box sx={{ width: '100%', py: 4 }}>
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
