import { useState, useRef, useCallback } from 'react';

interface UseAudioRecorderReturn {
    isRecording: boolean;
    startRecording: () => Promise<void>;
    stopRecording: () => Promise<Blob | null>;
    hasPermission: boolean;
    transcript: string;
}

export const useAudioRecorder = (onSilence?: () => void): UseAudioRecorderReturn => {
    const [isRecording, setIsRecording] = useState(false);
    const [hasPermission, setHasPermission] = useState(false);
    const [transcript, setTranscript] = useState("");

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const recognitionRef = useRef<any>(null);
    const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);

    const resetSilenceTimer = useCallback(() => {
        if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
        }

        if (onSilence) {
            silenceTimerRef.current = setTimeout(() => {
                console.log("[useAudioRecorder] Silence detected, triggering auto-submit...");
                onSilence();
            }, 2500); // 2.5 seconds of silence
        }
    }, [onSilence]);

    const startRecording = useCallback(async () => {
        try {
            // 1. Start Audio Recording (Server Side)
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setHasPermission(true);
            setTranscript("");

            const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = recorder;
            chunksRef.current = [];

            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    chunksRef.current.push(event.data);
                }
            };

            recorder.start();
            setIsRecording(true);
            resetSilenceTimer();

            // 2. Start Speech Recognition (Visual Feedback Only)
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            if (SpeechRecognition) {
                const recognition = new SpeechRecognition();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';

                recognition.onresult = (event: any) => {
                    const currentTranscript = Array.from(event.results)
                        .map((result: any) => result[0].transcript)
                        .join('');
                    if (currentTranscript.trim()) {
                        setTranscript(currentTranscript);
                        resetSilenceTimer(); // Reset timer on speech
                    }
                };

                recognition.onerror = (event: any) => {
                    console.warn("Browser ASR Error (Visual Only):", event.error);
                };

                recognition.onend = () => {
                    // Auto-restart if still recording (handles timeouts/silence)
                    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
                        try {
                            recognition.start();
                        } catch (e) {
                            console.warn("Failed to restart ASR:", e);
                        }
                    }
                };

                try {
                    recognition.start();
                    recognitionRef.current = recognition;
                } catch (e) {
                    console.warn("Could not start Browser ASR:", e);
                }
            }

        } catch (error) {
            console.error('Error accessing microphone:', error);
            setHasPermission(false);
        }
    }, []);

    const stopRecording = useCallback((): Promise<Blob | null> => {
        return new Promise((resolve) => {
            // Stop Browser ASR
            if (recognitionRef.current) {
                recognitionRef.current.stop();
                recognitionRef.current = null;
            }

            if (silenceTimerRef.current) {
                clearTimeout(silenceTimerRef.current);
                silenceTimerRef.current = null;
            }

            if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
                resolve(null);
                return;
            }

            mediaRecorderRef.current.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                chunksRef.current = [];
                setIsRecording(false);

                // Stop all tracks to release mic
                mediaRecorderRef.current?.stream.getTracks().forEach(track => track.stop());

                resolve(blob);
            };

            mediaRecorderRef.current.stop();
        });
    }, []);

    return {
        isRecording,
        startRecording,
        stopRecording,
        hasPermission,
        transcript
    };
};
