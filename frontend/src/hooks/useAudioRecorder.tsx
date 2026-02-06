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
            console.log("[useAudioRecorder] Requesting microphone access...");
            // 1. Start Audio Recording (Server Side)
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log("[useAudioRecorder] Microphone access granted.");
            setHasPermission(true);
            setTranscript("");

            const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = recorder;
            chunksRef.current = [];

            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    chunksRef.current.push(event.data);
                    console.log(`[useAudioRecorder] Chunk received: ${event.data.size} bytes`);
                }
            };

            recorder.start();
            setIsRecording(true);
            resetSilenceTimer();
            console.log("[useAudioRecorder] MediaRecorder started.");

            // 2. Start Speech Recognition (Visual Feedback Only)
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            if (SpeechRecognition) {
                console.log("[useAudioRecorder] SpeechRecognition available, initializing...");
                const recognition = new SpeechRecognition();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';

                recognition.onstart = () => console.log("[useAudioRecorder] SpeechRecognition started.");

                recognition.onresult = (event: any) => {
                    const currentTranscript = Array.from(event.results)
                        .map((result: any) => result[0].transcript)
                        .join('');
                    console.log("[useAudioRecorder] Partial transcript:", currentTranscript);
                    if (currentTranscript.trim()) {
                        setTranscript(currentTranscript);
                        resetSilenceTimer(); // Reset timer on speech
                    }
                };

                recognition.onerror = (event: any) => {
                    console.warn("[useAudioRecorder] Browser ASR Error:", event.error);
                };

                recognition.onend = () => {
                    console.log("[useAudioRecorder] SpeechRecognition ended.");
                    // Auto-restart if still recording (handles timeouts/silence)
                    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
                        try {
                            console.log("[useAudioRecorder] Restarting SpeechRecognition...");
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
            } else {
                console.warn("[useAudioRecorder] SpeechRecognition NOT available in this browser.");
            }

        } catch (error) {
            console.error('Error accessing microphone:', error);
            setHasPermission(false);
        }
    }, [resetSilenceTimer]);

    const stopRecording = useCallback((): Promise<Blob | null> => {
        return new Promise((resolve) => {
            console.log("[useAudioRecorder] Stopping recording...");
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
                console.warn("[useAudioRecorder] MediaRecorder was inactive or null.");
                resolve(null);
                return;
            }

            mediaRecorderRef.current.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                console.log(`[useAudioRecorder] Recording stopped. Total blob size: ${blob.size} bytes`);
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
