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

    // Session Management
    const [sessionId, setSessionId] = useState<string>("");

    useEffect(() => {
        let sid = sessionStorage.getItem("zeroq_session_id");
        if (!sid) {
            sid = Math.random().toString(36).substring(2) + Date.now().toString(36);
            sessionStorage.setItem("zeroq_session_id", sid);
        }
        setSessionId(sid);
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
                session_id: sessionId,
                latitude: location?.lat,
                longitude: location?.lng,
                history: chatHistory.map(h => ({
                    role: h.role === 'ai' ? 'assistant' : 'user',
                    content: h.text
                })),
                context: {
                    active_view: activeViewer,
                    visible_shops: activeShops.map(s => s.name)
                }
            });

            const { response: agentText, actions } = response.data;
            let currentShops = [...activeShops];
            let currentViewer = activeViewer;

            console.log('[DEBUG] MasterAgent COMPLETE Response:', response.data);

            if (actions && Array.isArray(actions) && actions.length > 0) {
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
            } else {
                // No navigation actions returned - reset back to centered chat for simple conversation
                currentViewer = null;
                currentShops = [];
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
                        flexDirection: activeViewer ? { xs: 'column', md: 'row-reverse' } : 'column',
                        alignItems: 'center',
                        justifyContent: activeViewer ? { xs: 'flex-start', md: 'space-between' } : 'center',
                        py: activeViewer ? { xs: 2, md: 4 } : { xs: 4, md: 10 },
                        px: { xs: 2, sm: 4, md: 6 },
                        gap: { xs: 2, md: 3 },
                        width: '100%',
                        maxWidth: '1600px',
                        mx: 'auto',
                        minHeight: 'min-content'
                    }}>

                        {/* LEFT COLUMN: Agent, Transcript & Controls */}
                        <Box sx={{
                            flex: activeViewer ? { xs: 'none', md: '0 0 35%' } : 'none',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: { xs: 2, md: 4 },
                            transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                            width: '100%',
                            maxWidth: activeViewer ? { xs: '100%', md: 420 } : { xs: '100%', md: 800 },
                            minHeight: 'auto',
                            position: { xs: 'relative', md: activeViewer ? 'sticky' : 'relative' },
                            top: { xs: 'auto', md: 0 },
                            py: { xs: 2, md: 0 },
                            textAlign: 'center'
                        }}>
                            <Box sx={{
                                position: 'relative',
                                width: { xs: 180, sm: 220, md: 280 },
                                height: { xs: 180, sm: 220, md: 280 },
                                transition: 'all 0.5s ease'
                            }}>
                                <ParticleSphere volume={volume} isListening={isListening} color={theme.accent} isProcessing={isProcessing} />
                            </Box>

                            <Box
                                ref={scrollRef}
                                sx={{
                                    textAlign: 'center',
                                    maxHeight: activeViewer ? '25vh' : '30vh',
                                    overflowY: 'auto',
                                    width: '100%',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: 2,
                                    px: { xs: 2, md: 0 },
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
                            </Box>

                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, width: '100%' }}>
                                <IconButton
                                    onClick={() => isListening ? stopListening() : startListening()}
                                    sx={{
                                        width: 80, height: 80,
                                        bgcolor: isListening ? theme.accent : theme.cardBg,
                                        color: isListening ? (isDarkMode ? 'black' : 'white') : theme.text,
                                        border: `2px solid ${theme.cardBorder}`,
                                        boxShadow: isListening ? `0 0 50px ${theme.accent}88` : 'none'
                                    }}
                                >
                                    {isListening ? <MicIcon sx={{ fontSize: 40 }} /> : <MicOffIcon sx={{ fontSize: 40 }} />}
                                </IconButton>
                                <Typography variant="caption" sx={{ opacity: 0.6, letterSpacing: '0.1em', fontWeight: 600 }}>
                                    {isListening ? "LISTENING..." : "START VOICE CONVERSATION"}
                                </Typography>
                            </Box>
                        </Box>

                        {/* RIGHT COLUMN: Content Viewer */}
                        {(activeViewer || isProcessing) && (
                            <Fade in={true} timeout={1000}>
                                <Box sx={{
                                    flex: 1,
                                    width: '100%',
                                    maxWidth: { xs: '100%', md: 'none' },
                                    maxHeight: { xs: '55vh', md: '90vh' },
                                    overflowY: 'auto',
                                    p: { xs: 2, sm: 3, md: 4 },
                                    borderRadius: { xs: '20px', md: '32px' },
                                    bgcolor: isDarkMode ? 'rgba(0,0,0,0.4)' : 'rgba(255,255,255,0.7)',
                                    border: `1px solid ${theme.cardBorder}`,
                                    backdropFilter: 'blur(20px)',
                                    boxShadow: '0 20px 80px rgba(0,0,0,0.1)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: (isProcessing && !activeViewer) ? 'center' : 'flex-start',
                                }}>
                                    {isProcessing && (
                                        <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 3 }}>
                                            <Box sx={{ height: 40, width: '60%', bgcolor: theme.cardBorder, borderRadius: 2, animation: 'pulse 1.5s infinite' }} />
                                            {[1, 2, 3].map(i => (
                                                <Box key={i} sx={{ height: 120, width: '100%', bgcolor: theme.cardBg, borderRadius: '24px', border: `1px solid ${theme.cardBorder}`, animation: 'pulse 1.5s infinite', animationDelay: `${i * 0.2}s` }} />
                                            ))}
                                            <style>{`@keyframes pulse { 0% { opacity: 0.3; } 50% { opacity: 0.6; } 100% { opacity: 0.3; } }`}</style>
                                        </Box>
                                    )}

                                    {!isProcessing && activeViewer === 'shops' && (
                                        <Stack spacing={3} sx={{ width: '100%' }}>
                                            <Typography variant="h5" sx={{ fontWeight: 600 }}>Nearby Verified Queues</Typography>
                                            {activeShops.length === 0 ? (
                                                <Box sx={{ textAlign: 'center', py: 10, opacity: 0.6 }}>
                                                    <SearchIcon sx={{ fontSize: 60, mb: 2 }} />
                                                    <Typography variant="h6">No shops found.</Typography>
                                                </Box>
                                            ) : (
                                                activeShops.map((shop: any) => (
                                                    <Card key={shop.id} onClick={() => navigate(`/s/${shop.slug}`)} sx={{ bgcolor: theme.cardBg, borderRadius: '24px', border: `1px solid ${theme.cardBorder}`, cursor: 'pointer' }}>
                                                        <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 3, p: 3 }}>
                                                            <Avatar src={shop.logo_url} sx={{ width: 64, height: 64, borderRadius: '16px', bgcolor: theme.accent }}>{shop.name[0]}</Avatar>
                                                            <Box sx={{ flex: 1 }}>
                                                                <Typography variant="h6" sx={{ fontWeight: 700 }}>{shop.name}</Typography>
                                                                <Typography variant="body2" sx={{ opacity: 0.7 }}>{shop.address}, {shop.city}</Typography>
                                                            </Box>
                                                            <Button variant="contained" sx={{ bgcolor: theme.accent, color: isDarkMode ? 'black' : 'white', borderRadius: '12px', fontWeight: 700 }}>JOIN</Button>
                                                        </CardContent>
                                                    </Card>
                                                ))
                                            )}
                                        </Stack>
                                    )}

                                    {!isProcessing && activeViewer === 'pricing' && <Pricing />}
                                    {!isProcessing && activeViewer === 'features' && <Features />}
                                    {!isProcessing && activeViewer === 'faq' && <FAQ />}
                                </Box>
                            </Fade>
                        )}
                    </Box>
                </Box>

                {/* STICKY INPUT FIELD - Always visible at bottom */}
                {!isListening && (
                    <Box sx={{
                        position: 'sticky',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        p: { xs: 2, md: 3 },
                        bgcolor: isDarkMode ? 'rgba(15,23,42,0.95)' : 'rgba(255,255,255,0.95)',
                        backdropFilter: 'blur(10px)',
                        borderTop: `1px solid ${theme.cardBorder}`,
                        display: 'flex',
                        justifyContent: 'center',
                        zIndex: 10
                    }}>
                        <TextField
                            fullWidth
                            placeholder="Type to ZeroQ..."
                            variant="outlined"
                            sx={{ maxWidth: 500 }}
                            onKeyPress={(e) => {
                                if (e.key === 'Enter') {
                                    const target = e.target as HTMLInputElement;
                                    handleChat(target.value);
                                    target.value = '';
                                }
                            }}
                            slotProps={{
                                input: {
                                    sx: { borderRadius: '30px', bgcolor: theme.inputBg, color: theme.text },
                                    endAdornment: <SearchIcon sx={{ color: theme.textSecondary, mr: 1 }} />
                                }
                            }}
                        />
                    </Box>
                )}
            </Box>
        </Fade>
    );
};

export default MasterAIAgent;
