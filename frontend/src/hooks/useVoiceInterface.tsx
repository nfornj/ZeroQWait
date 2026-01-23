import { useState, useEffect, useCallback, useRef } from 'react';

interface VoiceCommand {
    command: string;
    action: () => void;
    keywords: string[];
}

interface UseVoiceInterfaceOptions {
    commands?: VoiceCommand[];
    language?: string;
    continuous?: boolean;
    onResult?: (transcript: string) => void;
    onError?: (error: string) => void;
}

interface UseVoiceInterfaceReturn {
    isListening: boolean;
    isSupported: boolean;
    transcript: string;
    startListening: () => void;
    stopListening: () => void;
    speak: (text: string) => void;
    isSpeaking: boolean;
}

export const useVoiceInterface = (
    options: UseVoiceInterfaceOptions = {}
): UseVoiceInterfaceReturn => {
    const {
        commands = [],
        language = 'en-US',
        continuous = false,
        onResult,
        onError
    } = options;

    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isSupported, setIsSupported] = useState(false);

    const recognitionRef = useRef<any>(null);
    const synthesisRef = useRef<SpeechSynthesis | null>(null);

    useEffect(() => {
        // Check for browser support
        const SpeechRecognition =
            (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

        if (SpeechRecognition) {
            // Also check if we are in a secure context (HTTPS or localhost)
            // Browsers like Chrome disable SpeechRecognition/Mic on insecure origins
            if (!window.isSecureContext && window.location.hostname !== 'localhost') {
                console.warn('Speech Recognition is disabled due to insecure context (HTTP). Please use HTTPS or localhost.');
                setIsSupported(true); // Still "supported" but blocked
            } else {
                setIsSupported(true);
            }
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = continuous;
            recognitionRef.current.interimResults = true;
            recognitionRef.current.lang = language;

            recognitionRef.current.onresult = (event: any) => {
                const current = event.resultIndex;
                const transcriptText = event.results[current][0].transcript;
                setTranscript(transcriptText);

                if (event.results[current].isFinal) {
                    onResult?.(transcriptText);
                    processCommand(transcriptText);
                }
            };

            recognitionRef.current.onerror = (event: any) => {
                console.error('Speech recognition error:', event.error);
                onError?.(event.error);
                setIsListening(false);
            };

            recognitionRef.current.onend = () => {
                setIsListening(false);
            };
        } else {
            setIsSupported(false);
        }

        // Initialize speech synthesis
        if ('speechSynthesis' in window) {
            synthesisRef.current = window.speechSynthesis;
        }

        return () => {
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
            if (synthesisRef.current) {
                synthesisRef.current.cancel();
            }
        };
    }, [language, continuous, onResult, onError]);

    const processCommand = useCallback((text: string) => {
        const lowerText = text.toLowerCase();

        for (const command of commands) {
            const matches = command.keywords.some(keyword =>
                lowerText.includes(keyword.toLowerCase())
            );

            if (matches) {
                command.action();
                break;
            }
        }
    }, [commands]);

    const startListening = useCallback(() => {
        if (recognitionRef.current && !isListening) {
            setTranscript('');
            recognitionRef.current.start();
            setIsListening(true);
        }
    }, [isListening]);

    const stopListening = useCallback(() => {
        if (recognitionRef.current && isListening) {
            recognitionRef.current.stop();
            setIsListening(false);
        }
    }, [isListening]);

    const speak = useCallback((text: string) => {
        if (synthesisRef.current) {
            // Cancel any ongoing speech
            synthesisRef.current.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = language;
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;

            utterance.onstart = () => setIsSpeaking(true);
            utterance.onend = () => setIsSpeaking(false);
            utterance.onerror = () => setIsSpeaking(false);

            synthesisRef.current.speak(utterance);
        }
    }, [language]);

    return {
        isListening,
        isSupported,
        transcript,
        startListening,
        stopListening,
        speak,
        isSpeaking
    };
};
