import React, { useState, useEffect, useRef, useCallback } from 'react';
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
import { useAudioRecorder } from '../../hooks/useAudioRecorder';
import { useAudioVisualizer } from '../../hooks/useAudioVisualizer';
import ParticleSphere from '../../components/agent/ParticleSphere';
import { useNavigate } from 'react-router-dom';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import ReactMarkdown from 'react-markdown';

import Pricing from './Pricing';
import Features from './Features';
import FAQ from './FAQ';
import { constructShopUrl, isLocalhost } from '../../utils/domainUtils';

const MasterAIAgent: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isDarkMode, setIsDarkMode] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [isTranscribing, setIsTranscribing] = useState(false);
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

    // Ref to hold the submit function (solves circular dependency)
    const submitAudioRef = useRef<() => Promise<void>>();

    // Voice Recorder (Server-Side ASR + Browser Preview + Auto-Submit)
    // Pass wrapper that calls the ref
    const { isRecording, startRecording, stopRecording, hasPermission, transcript } = useAudioRecorder(() => {
        if (submitAudioRef.current) {
            submitAudioRef.current();
        }
    });

    // Audio Submission Logic (Extracted for Auto-Submit)
    const submitAudio = useCallback(async () => {
        const audioBlob = await stopRecording();
        if (audioBlob) {
            setIsTranscribing(true);
            try {
                const formData = new FormData();
                formData.append('file', audioBlob, 'recording.webm');

                const response = await axios.post('/api/voice/transcribe', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });

                const text = response.data.text;
                if (text && text.trim()) {
                    handleChat(text);
                }
            } catch (error) {
                console.error('Transcription failed:', error);
            } finally {
                setIsTranscribing(false);
            }
        }
    }, [stopRecording]); // handleChat is stable

    // Update ref whenever submitAudio changes
    useEffect(() => {
        submitAudioRef.current = submitAudio;
    }, [submitAudio]);

    // Audio Visualizer
    const { volume } = useAudioVisualizer(isRecording);

    // Text-to-Speech Helper
    const speak = (text: string) => {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            window.speechSynthesis.speak(utterance);
        }
    };

    const handleVoiceToggle = async () => {
        if (isRecording) {
            await submitAudio();
        } else {
            await startRecording();
        }
    };

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
    }, [chatHistory]);


    return (
        <Fade in={isOpen}>
            <Box
                id="immersive-ai-overlay"
                sx={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    width: '100vw',
                    height: { xs: '100dvh', md: '100vh' },
                    zIndex: 10000,
                    background: theme.bg,
                    backdropFilter: theme.glass,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'flex-start',
                    color: theme.text,
                    overflow: 'hidden', // Changed to hidden - scrolling happens inside child
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
                        flexDirection: activeViewer ? { xs: 'column', md: 'row' } : 'column',
                        alignItems: activeViewer ? { xs: 'stretch', md: 'flex-start' } : 'center',
                        justifyContent: 'center',
                        py: { xs: 2, sm: 3, md: 4 },
                        px: { xs: 2, sm: 3, md: 4, lg: 6 },
                        gap: { xs: 3, sm: 3, md: 4 },
                        width: '100%',
                        maxWidth: activeViewer ? '1400px' : '800px',
                        mx: 'auto',
                        minHeight: activeViewer ? 'auto' : '60vh',
                        transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)'
                    }}>

                        {/* CHAT COLUMN: Agent, Transcript & Controls */}
                        <Box sx={{
                            flex: activeViewer ? { xs: '1 1 auto', md: '0 0 40%' } : 'none',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'flex-start',
                            gap: { xs: 2, sm: 2.5, md: 3 },
                            transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                            width: '100%',
                            maxWidth: activeViewer ? { xs: '100%', md: '420px' } : { xs: '100%', sm: '500px', md: '600px' },
                            minHeight: activeViewer ? { xs: 'auto', md: '50vh' } : 'auto',
                            position: 'relative',
                            py: { xs: 1, md: 2 },
                            order: { xs: 0, md: activeViewer ? 1 : 0 }
                        }}>
                            <Box sx={{
                                position: 'relative',
                                width: activeViewer ? { xs: 80, sm: 100, md: 120 } : { xs: 150, sm: 180, md: 220 },
                                height: activeViewer ? { xs: 80, sm: 100, md: 120 } : { xs: 150, sm: 180, md: 220 },
                                transition: 'all 0.5s ease',
                                flexShrink: 0,
                                mb: activeViewer ? 1 : 2
                            }}>
                                <ParticleSphere volume={volume} isListening={isRecording} color={theme.accent} isProcessing={isProcessing} />
                            </Box>

                            <Box
                                ref={scrollRef}
                                sx={{
                                    width: '100%',
                                    maxHeight: activeViewer ? { xs: '35vh', sm: '40vh', md: '50vh' } : { xs: '25vh', sm: '30vh', md: '35vh' },
                                    overflowY: 'auto',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 1.5,
                                    px: { xs: 1, sm: 1.5, md: 2 },
                                    py: 1,
                                    maskImage: 'linear-gradient(to bottom, transparent, black 8%, black 92%, transparent)',
                                    WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 8%, black 92%, transparent)',
                                    '&::-webkit-scrollbar': { width: '4px' },
                                    '&::-webkit-scrollbar-thumb': {
                                        background: isDarkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)',
                                        borderRadius: '4px'
                                    }
                                }}
                            >
                                {chatHistory.map((chat, index) => (
                                    <Box
                                        key={index}
                                        sx={{
                                            width: '100%',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: chat.role === 'user' ? 'flex-end' : 'flex-start',
                                            opacity: index < chatHistory.length - 2 ? 0.75 : 1,
                                            transition: 'opacity 0.3s ease'
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                bgcolor: chat.role === 'user' ? theme.accent : theme.cardBg,
                                                color: chat.role === 'user' ? (isDarkMode ? '#000' : '#fff') : theme.text,
                                                py: { xs: 1.5, md: 2 },
                                                px: { xs: 2, md: 2.5 },
                                                borderRadius: chat.role === 'user' ? '20px 20px 4px 20px' : '20px 20px 20px 4px',
                                                maxWidth: { xs: '88%', sm: '85%', md: '85%' },
                                                border: chat.role === 'user' ? 'none' : `1px solid ${theme.cardBorder}`,
                                                boxShadow: chat.role === 'user'
                                                    ? '0 2px 8px rgba(0,0,0,0.1)'
                                                    : '0 2px 12px rgba(0,0,0,0.05)',
                                                '& p': {
                                                    m: 0,
                                                    mb: 0.75,
                                                    lineHeight: 1.5,
                                                    fontSize: { xs: '0.9rem', sm: '0.95rem', md: '1rem' }
                                                },
                                                '& p:last-child': { mb: 0 },
                                                '& ul, & ol': { pl: 2, m: 0, mb: 0.75 },
                                                '& li': { mb: 0.25, fontSize: { xs: '0.85rem', sm: '0.9rem', md: '0.95rem' } },
                                                '& strong': { fontWeight: 600, color: chat.role === 'user' ? 'inherit' : theme.accent }
                                            }}
                                        >
                                            {chat.role === 'user' ? (
                                                <Typography variant="body1" sx={{ fontSize: { xs: '0.9rem', md: '1rem' }, fontWeight: 500 }}>{chat.text}</Typography>
                                            ) : (
                                                <ReactMarkdown>{chat.text}</ReactMarkdown>
                                            )}
                                        </Box>
                                    </Box>
                                ))}
                            </Box>

                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, width: '100%', maxWidth: '500px' }}>
                                <IconButton
                                    onClick={handleVoiceToggle}
                                    disabled={isTranscribing}
                                    sx={{
                                        width: 80, height: 80,
                                        bgcolor: (isRecording || isTranscribing) ? theme.accent : theme.cardBg,
                                        color: (isRecording || isTranscribing) ? (isDarkMode ? 'black' : 'white') : theme.text,
                                        border: `2px solid ${theme.cardBorder}`,
                                        boxShadow: isRecording ? `0 0 50px ${theme.accent}88` : 'none',
                                        opacity: isTranscribing ? 0.7 : 1,
                                        transition: 'all 0.3s ease'
                                    }}
                                >
                                    {isTranscribing ? <CircularProgress size={30} color="inherit" /> : (isRecording ? <MicIcon sx={{ fontSize: 40 }} /> : <MicOffIcon sx={{ fontSize: 40 }} />)}
                                </IconButton>
                                <Typography variant="caption" sx={{
                                    opacity: (isRecording || isTranscribing) ? 1 : 0.6,
                                    letterSpacing: '0.1em',
                                    fontWeight: 600,
                                    minHeight: '24px',
                                    height: 'auto',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: (isRecording || isTranscribing) ? theme.accent : 'inherit',
                                    transition: 'all 0.2s ease',
                                    textAlign: 'center',
                                    maxWidth: '600px',
                                    width: '100%',
                                    margin: '0 auto',
                                    lineHeight: '1.6'
                                }}>
                                    {isTranscribing ? "TRANSCRIBING..." : (isRecording ? (transcript || "RECORDING...") : "START VOICE CONVERSATION")}
                                </Typography>

                                {/* INTEGRATED INPUT FIELD */}
                                {(!isRecording && !isTranscribing) && (
                                    <TextField
                                        fullWidth
                                        placeholder="Type to ZeroQ..."
                                        variant="outlined"
                                        onKeyPress={(e) => {
                                            if (e.key === 'Enter') {
                                                const target = e.target as HTMLInputElement;
                                                if (target.value.trim()) {
                                                    handleChat(target.value);
                                                    target.value = '';
                                                }
                                            }
                                        }}
                                        sx={{ mt: 2 }}
                                        slotProps={{
                                            input: {
                                                sx: {
                                                    borderRadius: '30px',
                                                    bgcolor: theme.inputBg,
                                                    color: theme.text,
                                                    backdropFilter: 'blur(10px)',
                                                    border: `1px solid ${theme.cardBorder}`,
                                                },
                                                endAdornment: <SearchIcon sx={{ color: theme.textSecondary, mr: 1 }} />
                                            }
                                        }}
                                    />
                                )}
                            </Box>
                        </Box>

                        {/* RESULTS PANEL: Content Viewer */}
                        {(activeViewer || isProcessing) && (
                            <Fade in={true} timeout={600}>
                                <Box sx={{
                                    flex: { xs: '1 1 auto', md: '1 1 60%' },
                                    width: '100%',
                                    maxWidth: { xs: '100%', sm: '100%', md: '650px' },
                                    minHeight: { xs: '40vh', md: '50vh' },
                                    maxHeight: { xs: '60vh', sm: '65vh', md: '75vh' },
                                    overflowY: 'auto',
                                    p: { xs: 2, sm: 2.5, md: 3 },
                                    borderRadius: { xs: '16px', sm: '20px', md: '24px' },
                                    bgcolor: isDarkMode ? 'rgba(15,15,25,0.7)' : 'rgba(255,255,255,0.9)',
                                    border: `1px solid ${isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`,
                                    backdropFilter: 'blur(20px)',
                                    boxShadow: isDarkMode
                                        ? '0 12px 40px rgba(0,0,0,0.3)'
                                        : '0 12px 40px rgba(0,0,0,0.06)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'stretch',
                                    justifyContent: (isProcessing && !activeViewer) ? 'center' : 'flex-start',
                                    transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                                    order: { xs: 1, md: 0 },
                                    '&::-webkit-scrollbar': { width: '5px' },
                                    '&::-webkit-scrollbar-thumb': {
                                        background: isDarkMode ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)',
                                        borderRadius: '5px'
                                    }
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
                                                            <Button
                                                                variant="contained"
                                                                onClick={() => {
                                                                    const targetSlug = shop.slug || `shop-${shop.id}`;

                                                                    if (isLocalhost()) {
                                                                        // Keeps dev flow simple (SPA routing)
                                                                        navigate(`/shop-ai/${shop.id}`);
                                                                    } else {
                                                                        // Full redirect to subdomain
                                                                        window.location.href = constructShopUrl(targetSlug, '/ai');
                                                                    }
                                                                }}
                                                                sx={{ bgcolor: theme.accent, color: isDarkMode ? 'black' : 'white', borderRadius: '12px', fontWeight: 700 }}
                                                            >
                                                                JOIN
                                                            </Button>
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
            </Box>
        </Fade>
    );
};

export default MasterAIAgent;
