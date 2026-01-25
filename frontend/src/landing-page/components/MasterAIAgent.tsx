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

const MasterAIAgent: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isDarkMode, setIsDarkMode] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [chatHistory, setChatHistory] = useState<Array<{ role: 'ai' | 'user', text: string, shops?: any[] }>>([
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
        bg: isDarkMode ? 'rgba(5, 5, 10, 0.92)' : 'rgba(255, 255, 255, 0.95)',
        glass: isDarkMode ? 'blur(40px)' : 'blur(30px)',
        text: isDarkMode ? '#ffffff' : '#0f172a',
        textSecondary: isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(15, 23, 42, 0.7)',
        accent: isDarkMode ? '#f5e1c0' : '#A855F7', // Gold in dark, Purple in light
        cardBg: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(15, 23, 42, 0.03)',
        cardBorder: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(15, 23, 42, 0.08)',
        inputBg: isDarkMode ? 'rgba(255, 255, 255, 0.07)' : 'rgba(15, 23, 42, 0.05)',
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
                history: chatHistory.map(h => ({
                    role: h.role === 'ai' ? 'assistant' : 'user',
                    content: h.text
                }))
            });

            const { response: agentText, actions } = response.data;
            let shopResults: any[] = [];

            actions.forEach((action: any) => {
                if (action.tool === 'navigate_to_page_section') {
                    const sectionId = action.result.target;
                    const element = document.getElementById(sectionId);
                    if (element) {
                        element.scrollIntoView({ behavior: 'smooth' });
                        // Close immersive mode after navigation so they see the result
                        setTimeout(() => setIsOpen(false), 2000);
                    }
                } else if (action.tool === 'search_shops') {
                    shopResults = action.result;
                }
            });

            setChatHistory(prev => [...prev, { role: 'ai', text: agentText, shops: shopResults }]);
            setIsProcessing(false);
            speak(agentText);
        } catch (err) {
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
                    overflow: 'hidden',
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

                <Stack
                    direction={latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? "row" : "column"}
                    spacing={latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? 8 : 4}
                    alignItems="center"
                    justifyContent="center"
                    sx={{
                        maxWidth: '95%',
                        width: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? 1400 : 800,
                        transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}
                >
                    {/* Left Column: AI Assistant (Sphere + Transcript) */}
                    <Box sx={{
                        flex: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? 0.8 : 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 2,
                        transition: 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                        width: '100%'
                    }}>
                        {/* The Particle Sphere */}
                        <Box sx={{ position: 'relative', width: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? 300 : 400, height: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? 300 : 400, transition: 'all 0.8s ease' }}>
                            <ParticleSphere volume={volume} isListening={isListening} color={theme.accent} />
                            {isProcessing && (
                                <CircularProgress
                                    size={latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? 200 : 260}
                                    thickness={1}
                                    sx={{
                                        position: 'absolute',
                                        top: '50%',
                                        left: '50%',
                                        marginTop: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? '-100px' : '-130px',
                                        marginLeft: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? '-100px' : '-130px',
                                        color: theme.accent,
                                        opacity: 0.3,
                                        animationDuration: '1.5s',
                                        transition: 'all 0.8s ease'
                                    }}
                                />
                            )}
                        </Box>

                        {/* Scrollable Transcript Area */}
                        <Box
                            ref={scrollRef}
                            sx={{
                                textAlign: 'center',
                                mt: 2,
                                px: 4,
                                maxHeight: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? '30vh' : '40vh',
                                overflowY: 'auto',
                                width: '100%',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 3,
                                maskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)',
                                WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)',
                                '&::-webkit-scrollbar': { display: 'none' },
                                msOverflowStyle: 'none',
                                scrollbarWidth: 'none',
                                transition: 'all 0.8s ease'
                            }}
                        >
                            {chatHistory.map((chat, index) => (
                                <Box key={index} sx={{ opacity: index === chatHistory.length - 1 ? 1 : 0.4, transition: 'opacity 0.5s' }}>
                                    <Typography
                                        variant="body1"
                                        sx={{
                                            fontWeight: index === chatHistory.length - 1 ? 400 : 300,
                                            lineHeight: 1.6,
                                            letterSpacing: '0.01em',
                                            color: chat.role === 'user' ? theme.accent : theme.text,
                                            fontSize: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? '1.1rem' : { xs: '1.1rem', md: '1.4rem' },
                                            maxWidth: '600px',
                                            margin: '0 auto',
                                            transition: 'all 0.8s ease'
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
                                        letterSpacing: '0.01em',
                                        color: 'rgba(245, 225, 192, 0.6)',
                                        fontSize: latestAIResponse?.shops && latestAIResponse.shops.length > 0 ? '1.1rem' : { xs: '1.1rem', md: '1.4rem' },
                                        fontStyle: 'italic',
                                        transition: 'all 0.8s ease'
                                    }}
                                >
                                    {transcript}
                                </Typography>
                            )}

                            {isProcessing && (
                                <Typography variant="body2" sx={{ mt: 1, color: 'secondary.main', opacity: 0.6, fontStyle: 'italic' }}>
                                    Thinking...
                                </Typography>
                            )}
                        </Box>
                    </Box>

                    {/* Right Column: Shop Results List (Animated) */}
                    {latestAIResponse?.shops && latestAIResponse.shops.length > 0 && (
                        <Fade in={true} timeout={1000}>
                            <Box sx={{
                                flex: 1.2,
                                width: '100%',
                                maxHeight: '70vh',
                                overflowY: 'auto',
                                pr: 2,
                                '&::-webkit-scrollbar': { width: '4px' },
                                '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.1)', borderRadius: '10px' }
                            }}>
                                <Typography variant="h5" sx={{ mb: 3, fontWeight: 300, color: 'rgba(245, 225, 192, 0.9)' }}>
                                    Found {latestAIResponse.shops.length} results
                                </Typography>
                                <Stack spacing={3}>
                                    {latestAIResponse.shops.map((shop) => (
                                        <Card
                                            key={shop.id}
                                            sx={{
                                                bgcolor: theme.cardBg,
                                                borderRadius: '24px',
                                                color: theme.text,
                                                border: `1px solid ${theme.cardBorder}`,
                                                boxShadow: isDarkMode ? 'none' : '0 8px 32px rgba(15, 23, 42, 0.05)',
                                                transition: 'all 0.3s ease',
                                                '&:hover': {
                                                    bgcolor: isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.06)',
                                                    transform: 'translateY(-4px)',
                                                    borderColor: theme.accent
                                                }
                                            }}
                                        >
                                            <CardContent sx={{ p: 3 }}>
                                                <Stack direction="row" spacing={3} alignItems="center">
                                                    <Avatar
                                                        src={shop.logo_url}
                                                        sx={{ width: 80, height: 80, borderRadius: '20px', border: `1px solid ${theme.cardBorder}` }}
                                                    />
                                                    <Box sx={{ flex: 1 }}>
                                                        <Typography variant="h6" fontWeight="600" sx={{ mb: 0.5 }}>{shop.name}</Typography>
                                                        <Typography variant="body2" sx={{ color: theme.textSecondary, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                            <LocationOnIcon sx={{ fontSize: 16 }} />
                                                            {shop.address}, {shop.city}
                                                        </Typography>
                                                        <Box sx={{ mt: 1.5, display: 'flex', gap: 1 }}>
                                                            <Chip label="Open Now" size="small" sx={{ bgcolor: isDarkMode ? 'rgba(76, 175, 80, 0.1)' : 'rgba(76, 175, 80, 0.05)', color: '#2e7d32', border: '1px solid rgba(76, 175, 80, 0.2)' }} />
                                                            <Chip label={`${shop.average_service_time || 30}m wait`} size="small" sx={{ bgcolor: theme.inputBg, color: theme.text, border: `1px solid ${theme.cardBorder}` }} />
                                                        </Box>
                                                    </Box>
                                                    <Button
                                                        variant="contained"
                                                        sx={{
                                                            bgcolor: theme.accent,
                                                            color: isDarkMode ? 'black' : 'white',
                                                            fontWeight: 'bold',
                                                            px: 4,
                                                            py: 1.5,
                                                            borderRadius: '16px',
                                                            '&:hover': { bgcolor: theme.accent, opacity: 0.9 }
                                                        }}
                                                        onClick={() => navigate(`/s/${shop.slug}`)}
                                                    >
                                                        Join Queue
                                                    </Button>
                                                </Stack>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </Stack>
                            </Box>
                        </Fade>
                    )}
                </Stack>

                {/* Interaction Footer */}
                <Box
                    sx={{
                        position: 'absolute',
                        bottom: 60,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 2
                    }}
                >
                    {/* Insecure Context Warning - More Prominent */}
                    {(!window.isSecureContext && window.location.hostname !== 'localhost') && (
                        <Box sx={{
                            mb: 2,
                            p: 2,
                            bgcolor: 'rgba(211, 47, 47, 0.2)',
                            border: '2px solid #d32f2f',
                            borderRadius: '16px',
                            maxWidth: 500,
                            textAlign: 'center',
                            animation: 'pulse 2s infinite'
                        }}>
                            <Typography variant="body2" sx={{ color: '#ff5252', fontWeight: 'bold', mb: 0.5 }}>
                                🚨 Browser Security: Microphone Access Blocked
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block' }}>
                                Voice recognition requires <b>HTTPS</b> or <b>localhost</b>.
                                Browsers block microphone features on insecure (HTTP) origins.
                            </Typography>
                        </Box>
                    )}

                    <IconButton
                        onClick={() => {
                            if (!window.isSecureContext && window.location.hostname !== 'localhost') {
                                alert("Microphone access requires a secure connection (HTTPS). Please try accessing via localhost or a secure domain.");
                                return;
                            }
                            isListening ? stopListening() : startListening();
                        }}
                        sx={{
                            width: 90,
                            height: 90,
                            bgcolor: isListening ? theme.accent : theme.cardBg,
                            color: isListening ? (isDarkMode ? 'black' : 'white') : theme.text,
                            '&:hover': { bgcolor: isListening ? theme.accent : theme.inputBg },
                            transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
                            border: `1px solid ${theme.cardBorder}`,
                            boxShadow: isListening ? `0 0 40px ${theme.accent}66` : 'none'
                        }}
                    >
                        {isListening ? <MicIcon sx={{ fontSize: 45 }} /> : <MicOffIcon sx={{ fontSize: 45 }} />}
                    </IconButton>

                    <Typography variant="caption" sx={{ opacity: 0.4, letterSpacing: '0.1em' }}>
                        {isListening ? "STOP LISTENING" : "START VOICE CONVERSATION"}
                    </Typography>
                    <Typography variant="caption" sx={{ opacity: 0.2, fontSize: '0.6rem' }}>
                        v1.0.1-light
                    </Typography>

                    {/* Text Input Fallback (always visible if not listening) */}
                    {!isListening && (
                        <Box sx={{ mt: 3, width: { xs: '90vw', sm: 400 }, transition: 'all 0.3s' }}>
                            <TextField
                                fullWidth
                                placeholder="Type or speak to ZeroQ..."
                                variant="outlined"
                                autoFocus
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
                                            '& fieldset': { borderColor: theme.cardBorder },
                                            '&:hover fieldset': { borderColor: theme.accent },
                                            '&.Mui-focused fieldset': { borderColor: theme.accent, borderWidth: '2px' }
                                        },
                                        endAdornment: <SearchIcon sx={{ color: theme.textSecondary, mr: 1 }} />
                                    }
                                }}
                            />
                        </Box>
                    )}
                </Box>
            </Box>
        </Fade>
    );
};

export default MasterAIAgent;
