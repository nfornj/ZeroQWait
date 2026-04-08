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

const decodeBase64Audio = (base64Audio: string): ArrayBuffer => {
    const binaryStr = atob(base64Audio);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i);
    }
    return bytes.buffer.slice(0) as ArrayBuffer;
};

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
    const audioCtxRef = useRef<AudioContext | null>(null);
    const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const ttsAbortRef = useRef<AbortController | null>(null);

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

        return () => {
            if (recognitionRef.current) {
                recognitionRef.current.stop();
            }
            if (ttsAbortRef.current) {
                ttsAbortRef.current.abort();
                ttsAbortRef.current = null;
            }
            try {
                if (currentSourceRef.current) {
                    currentSourceRef.current.stop();
                    currentSourceRef.current = null;
                }
            } catch (_err) {
                // no-op
            }
        };
    }, [language, continuous, onResult, onError]);

    const getAudioContext = useCallback(() => {
        if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
            audioCtxRef.current = new (
                window.AudioContext || (window as any).webkitAudioContext
            )();
        }
        return audioCtxRef.current;
    }, []);

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
        void (async () => {
            const plainText = text
                .replace(/\*\*(.*?)\*\*/g, '$1')
                .replace(/\*(.*?)\*/g, '$1')
                .replace(/#{1,6}\s/g, '')
                .replace(/`([^`]*)`/g, '$1')
                .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
                .replace(/\n+/g, ' ')
                .replace(/\s{2,}/g, ' ')
                .trim();

            if (!plainText) return;

            if (ttsAbortRef.current) {
                ttsAbortRef.current.abort();
            }
            ttsAbortRef.current = new AbortController();

            try {
                if (currentSourceRef.current) {
                    currentSourceRef.current.stop();
                    currentSourceRef.current = null;
                }
            } catch (_err) {
                // no-op
            }

            setIsSpeaking(true);
            try {
                const response = await fetch('/api/voice/tts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: plainText, voice: 'Vivian', speed: 1.0 }),
                    signal: ttsAbortRef.current.signal,
                });

                if (!response.ok) {
                    throw new Error(`TTS ${response.status}`);
                }

                let arrayBuffer: ArrayBuffer;
                const contentType = response.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    const payload = await response.json();
                    if (!payload?.audio) throw new Error('Invalid TTS JSON payload');
                    arrayBuffer = decodeBase64Audio(payload.audio);
                } else {
                    arrayBuffer = await response.arrayBuffer();
                }

                const audioCtx = getAudioContext();
                if (audioCtx.state === 'suspended') {
                    await audioCtx.resume();
                }

                const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
                const source = audioCtx.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(audioCtx.destination);
                currentSourceRef.current = source;

                await new Promise<void>((resolve) => {
                    source.onended = () => resolve();
                    source.start(0);
                });
            } catch (err: any) {
                if (err?.name !== 'AbortError') {
                    console.warn('[VoiceInterface] backend TTS failed:', err);
                }
            } finally {
                setIsSpeaking(false);
                currentSourceRef.current = null;
            }
        })();
    }, [getAudioContext]);

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
