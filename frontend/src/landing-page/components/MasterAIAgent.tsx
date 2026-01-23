import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Typography,
    Paper,
    IconButton,
    Fab,
    Zoom,
    Fade,
    Stack,
    TextField,
    CircularProgress,
    Card,
    CardContent,
    Button,
    Chip,
    Avatar
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import axios from 'axios';
import { useVoiceInterface } from '../../hooks/useVoiceInterface';
import { useAudioVisualizer } from '../../hooks/useAudioVisualizer';
import CanvasOrb from '../../components/agent/CanvasOrb';
import { useNavigate } from 'react-router-dom';

const MasterAIAgent: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [chatHistory, setChatHistory] = useState<Array<{ role: 'ai' | 'user', text: string, shops?: any[] }>>([
        { role: 'ai', text: "Welcome to ZeroQwait! I'm ZeroQ. Ask me anything about our product, pricing, or find shops near you!" }
    ]);
    const [feedbackMessage, setFeedbackMessage] = useState("Hi! Tap the orb to talk.");
    const navigate = useNavigate();

    const { isListening, transcript, startListening, stopListening, speak } = useVoiceInterface({
        onResult: (text) => handleChat(text)
    });

    const { volume } = useAudioVisualizer(isListening);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [chatHistory, feedbackMessage]);

    // Visibility & Auto-Open Logic
    useEffect(() => {
        // Auto-open after 3 seconds on first load
        const timer = setTimeout(() => {
            setIsOpen(true);
            speak("Welcome to ZeroQwait! how can I help you today?");
        }, 3000);

        // Listen for global toggle events (from Hero or AppBar)
        const handleToggle = () => setIsOpen(prev => !prev);
        window.addEventListener('toggle-ai-assistant', handleToggle);

        return () => {
            clearTimeout(timer);
            window.removeEventListener('toggle-ai-assistant', handleToggle);
        };
    }, []);

    const handleChat = async (userText: string) => {
        if (!userText.trim()) return;

        setChatHistory(prev => [...prev, { role: 'user', text: userText }]);
        setIsProcessing(true);
        setFeedbackMessage("Thinking...");

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

            // Process Actions
            actions.forEach((action: any) => {
                if (action.tool === 'navigate_to_page_section') {
                    const sectionId = action.result.target;
                    const element = document.getElementById(sectionId);
                    if (element) {
                        element.scrollIntoView({ behavior: 'smooth' });
                    }
                } else if (action.tool === 'search_shops') {
                    shopResults = action.result;
                }
            });

            setChatHistory(prev => [...prev, { role: 'ai', text: agentText, shops: shopResults }]);
            setFeedbackMessage(agentText);
            setIsProcessing(false);
            speak(agentText);
        } catch (err) {
            setIsProcessing(false);
            setFeedbackMessage("I'm running into some interference. Could you try that again?");
            speak("I'm sorry, I missed that. Try again?");
        }
    };

    return (
        <>
            {/* Floating FAB */}
            <Box sx={{ position: 'fixed', bottom: 32, right: 32, zIndex: 9999 }}>
                <Zoom in={!isOpen}>
                    <Fab
                        color="secondary"
                        aria-label="chat"
                        onClick={() => setIsOpen(true)}
                        sx={{
                            width: 64,
                            height: 64,
                            boxShadow: '0 8px 32px rgba(156, 39, 176, 0.4)',
                            background: 'linear-gradient(135deg, #9c27b0, #f06292)',
                            '&:hover': { transform: 'scale(1.1)' },
                            transition: 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)'
                        }}
                    >
                        <SmartToyIcon />
                    </Fab>
                </Zoom>
            </Box>

            {/* Chat Dialog */}
            <Fade in={isOpen}>
                <Paper
                    elevation={24}
                    sx={{
                        position: 'fixed',
                        bottom: { xs: 0, sm: 32 },
                        right: { xs: 0, sm: 32 },
                        width: { xs: '100%', sm: 400 },
                        height: { xs: '100%', sm: 600 },
                        borderRadius: { xs: 0, sm: '32px' },
                        display: 'flex',
                        flexDirection: 'column',
                        overflow: 'hidden',
                        zIndex: 10000,
                        background: 'rgba(255, 255, 255, 0.95)',
                        backdropFilter: 'blur(20px)',
                        border: '1px solid rgba(255, 255, 255, 0.3)'
                    }}
                >
                    {/* Header */}
                    <Box sx={{ p: 3, background: 'linear-gradient(135deg, #9c27b0, #f06292)', color: 'white' }}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Stack direction="row" spacing={2} alignItems="center">
                                <Avatar sx={{ bgcolor: 'white', color: '#9c27b0' }}>
                                    <SmartToyIcon />
                                </Avatar>
                                <Box>
                                    <Typography variant="h6" fontWeight="bold">ZeroQ</Typography>
                                    <Typography variant="caption" sx={{ opacity: 0.8 }}>Master AI Agent</Typography>
                                </Box>
                            </Stack>
                            <IconButton onClick={() => setIsOpen(false)} sx={{ color: 'white' }}>
                                <CloseIcon />
                            </IconButton>
                        </Stack>
                    </Box>

                    {/* Chat Messages */}
                    <Box ref={scrollRef} sx={{ flex: 1, p: 3, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {chatHistory.map((msg, i) => (
                            <Box key={i} sx={{ alignSelf: msg.role === 'ai' ? 'flex-start' : 'flex-end', maxWidth: '85%' }}>
                                <Paper
                                    elevation={0}
                                    sx={{
                                        p: 2,
                                        borderRadius: msg.role === 'ai' ? '20px 20px 20px 4px' : '20px 20px 4px 20px',
                                        bgcolor: msg.role === 'ai' ? 'grey.100' : 'primary.main',
                                        color: msg.role === 'ai' ? 'text.primary' : 'white'
                                    }}
                                >
                                    <Typography variant="body2">{msg.text}</Typography>
                                </Paper>

                                {msg.shops && msg.shops.length > 0 && (
                                    <Stack spacing={1} sx={{ mt: 2, width: '100%' }}>
                                        {msg.shops.map((shop: any) => (
                                            <Card key={shop.id} variant="outlined" sx={{ borderRadius: '16px' }}>
                                                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                                                    <Stack direction="row" spacing={1.5} alignItems="center">
                                                        <Avatar src={shop.logo_url} variant="rounded" sx={{ width: 40, height: 40 }}>{shop.name[0]}</Avatar>
                                                        <Box sx={{ flex: 1 }}>
                                                            <Typography variant="subtitle2" fontWeight="bold">{shop.name}</Typography>
                                                            <Stack direction="row" spacing={0.5} alignItems="center">
                                                                <LocationOnIcon sx={{ fontSize: 12, color: 'text.secondary' }} />
                                                                <Typography variant="caption" color="text.secondary">{shop.city}, {shop.state}</Typography>
                                                            </Stack>
                                                        </Box>
                                                        <Button
                                                            size="small"
                                                            variant="contained"
                                                            disableElevation
                                                            onClick={() => navigate(`/s/${shop.slug}`)}
                                                            sx={{ borderRadius: '10px', fontSize: '0.7rem', py: 0.5 }}
                                                        >
                                                            Visit
                                                        </Button>
                                                    </Stack>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </Stack>
                                )}
                            </Box>
                        ))}
                        {isProcessing && (
                            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', p: 1 }}>
                                <CircularProgress size={16} />
                                <Typography variant="caption" color="text.secondary">ZeroQ is typing...</Typography>
                            </Box>
                        )}
                    </Box>

                    {/* Interaction Area */}
                    <Box sx={{ p: 3, borderTop: '1px solid rgba(0,0,0,0.05)', bgcolor: 'rgba(0,0,0,0.02)' }}>
                        <Stack spacing={2} alignItems="center">
                            {/* Orb */}
                            <Box
                                onClick={() => isListening ? stopListening() : startListening()}
                                sx={{
                                    cursor: 'pointer',
                                    transition: 'transform 0.2s',
                                    '&:active': { transform: 'scale(0.95)' },
                                    transform: 'scale(0.3)', // Significantly scale down the orb for the widget
                                    width: 120,
                                    height: 120,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center'
                                }}
                            >
                                <CanvasOrb
                                    volume={volume}
                                    isListening={isListening}
                                    primaryColor="#9c27b0"
                                />
                            </Box>

                            {/* Feedback */}
                            <Typography variant="caption" color="text.secondary" textAlign="center">
                                {isListening ? (transcript || "Listening...") : feedbackMessage}
                            </Typography>

                            {/* Text Input Fallback */}
                            {!isListening && (
                                <TextField
                                    fullWidth
                                    placeholder="Type a message..."
                                    variant="outlined"
                                    size="small"
                                    onKeyPress={(e) => {
                                        if (e.key === 'Enter') {
                                            const target = e.target as HTMLInputElement;
                                            handleChat(target.value);
                                            target.value = '';
                                        }
                                    }}
                                    slotProps={{
                                        input: {
                                            sx: { borderRadius: '20px', bgcolor: 'white' },
                                            endAdornment: <SearchIcon sx={{ color: 'text.disabled', mr: 1 }} />
                                        }
                                    }}
                                />
                            )}
                        </Stack>
                    </Box>
                </Paper>
            </Fade>
        </>
    );
};

export default MasterAIAgent;
