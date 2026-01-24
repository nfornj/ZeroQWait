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
    Avatar
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

const MasterAIAgent: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [chatHistory, setChatHistory] = useState<Array<{ role: 'ai' | 'user', text: string, shops?: any[] }>>([
        { role: 'ai', text: "Welcome to ZeroQwait! I'm ZeroQ. How can I help you today?" }
    ]);
    const navigate = useNavigate();

    const { isListening, transcript, startListening, stopListening, speak } = useVoiceInterface({
        onResult: (text) => handleChat(text)
    });

    const { volume } = useAudioVisualizer(isListening);

    // Visibility & Global Triggers
    useEffect(() => {
        const timer = setTimeout(() => {
            if (!isOpen) {
                setIsOpen(true);
            }
        }, 5000);

        const handleToggle = () => setIsOpen(prev => !prev);
        window.addEventListener('toggle-ai-assistant', handleToggle);

        return () => {
            clearTimeout(timer);
            window.removeEventListener('toggle-ai-assistant', handleToggle);
        };
    }, [isOpen]);

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
            const errorMsg = "I missed that. Could you say it again?";
            setChatHistory(prev => [...prev, { role: 'ai', text: errorMsg }]);
            speak(errorMsg);
        }
    };

    const latestAIResponse = chatHistory.filter(m => m.role === 'ai').slice(-1)[0];

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
                    background: 'rgba(5, 5, 10, 0.9)',
                    backdropFilter: 'blur(50px)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    overflow: 'hidden'
                }}
            >
                {/* Close Button Top Right */}
                <IconButton
                    onClick={() => setIsOpen(false)}
                    sx={{ position: 'absolute', top: 40, right: 40, color: 'white', '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' } }}
                >
                    <CloseIcon sx={{ fontSize: 40 }} />
                </IconButton>

                <Stack spacing={4} alignItems="center" sx={{ maxWidth: '80%', width: 800 }}>

                    {/* The Particle Sphere */}
                    <Box sx={{ position: 'relative', width: 400, height: 400 }}>
                        <ParticleSphere volume={volume} isListening={isListening} />
                        {isProcessing && (
                            <CircularProgress
                                size={260}
                                thickness={1}
                                sx={{
                                    position: 'absolute',
                                    top: '50%',
                                    left: '50%',
                                    marginTop: '-130px',
                                    marginLeft: '-130px',
                                    color: 'rgba(245, 225, 192, 0.2)',
                                    animationDuration: '1.5s'
                                }}
                            />
                        )}
                    </Box>

                    {/* Minimalist Output Text Area */}
                    <Box sx={{ textAlign: 'center', mt: 2, px: 4 }}>
                        <Fade in={!isProcessing} key={isListening ? 'listening' : latestAIResponse?.text}>
                            <Typography
                                variant="h3"
                                sx={{
                                    fontWeight: 200,
                                    lineHeight: 1.3,
                                    letterSpacing: '0.01em',
                                    color: 'rgba(255, 255, 255, 0.95)',
                                    textShadow: '0 0 30px rgba(245, 225, 192, 0.2)',
                                    fontSize: { xs: '1.5rem', md: '2.5rem' }
                                }}
                            >
                                {isListening ? (transcript || "I'm listening...") : latestAIResponse?.text}
                            </Typography>
                        </Fade>

                        {isProcessing && (
                            <Typography variant="h6" sx={{ mt: 2, color: 'secondary.main', opacity: 0.6, fontStyle: 'italic' }}>
                                Thinking...
                            </Typography>
                        )}
                    </Box>

                    {/* Shop Results Cards (Compact) */}
                    {latestAIResponse?.shops && latestAIResponse.shops.length > 0 && (
                        <Fade in={true}>
                            <Stack direction="row" spacing={2} sx={{ mt: 4, overflowX: 'auto', width: '100%', pb: 2, justifyContent: 'center' }}>
                                {latestAIResponse.shops.map((shop) => (
                                    <Card key={shop.id} sx={{ minWidth: 260, bgcolor: 'rgba(255,255,255,0.08)', borderRadius: '20px', color: 'white' }}>
                                        <CardContent sx={{ p: 2 }}>
                                            <Stack direction="row" spacing={2} alignItems="center">
                                                <Avatar src={shop.logo_url} sx={{ width: 48, height: 48, borderRadius: '12px' }} />
                                                <Box sx={{ flex: 1 }}>
                                                    <Typography variant="subtitle1" fontWeight="600">{shop.name}</Typography>
                                                    <Typography variant="caption" sx={{ opacity: 0.6 }}>{shop.city}</Typography>
                                                </Box>
                                                <Button
                                                    size="small"
                                                    variant="contained"
                                                    sx={{ bgcolor: 'white', color: 'black', '&:hover': { bgcolor: 'rgba(255,255,255,0.8)' } }}
                                                    onClick={() => navigate(`/s/${shop.slug}`)}
                                                >
                                                    Visit
                                                </Button>
                                            </Stack>
                                        </CardContent>
                                    </Card>
                                ))}
                            </Stack>
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
                    {/* Insecure Context Warning */}
                    {!window.isSecureContext && window.location.hostname !== 'localhost' && (
                        <Box sx={{ mb: 2, p: 1, px: 2, bgcolor: 'rgba(255, 152, 0, 0.2)', border: '1px solid #ff9800', borderRadius: '10px' }}>
                            <Typography variant="caption" sx={{ color: '#ff9800', fontWeight: 'bold' }}>
                                ⚠️ Microphone blocked. Use HTTPS or localhost to enable voice.
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
                            bgcolor: isListening ? '#f5e1c0' : 'rgba(255,255,255,0.1)',
                            color: isListening ? 'black' : 'white',
                            '&:hover': { bgcolor: isListening ? '#fff' : 'rgba(255,255,255,0.15)' },
                            transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
                            boxShadow: isListening ? '0 0 40px rgba(245, 225, 192, 0.4)' : 'none'
                        }}
                    >
                        {isListening ? <MicIcon sx={{ fontSize: 45 }} /> : <MicOffIcon sx={{ fontSize: 45 }} />}
                    </IconButton>

                    <Typography variant="caption" sx={{ opacity: 0.4, letterSpacing: '0.1em' }}>
                        {isListening ? "STOP LISTENING" : "START VOICE CONVERSATION"}
                    </Typography>
                </Box>
            </Box>
        </Fade>
    );
};

export default MasterAIAgent;
