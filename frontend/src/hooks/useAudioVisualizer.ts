import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Hook to capture microphone audio and provide real-time frequency/volume data.
 */
export const useAudioVisualizer = (isListening: boolean) => {
    const [volume, setVolume] = useState(0);
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const dataArrayRef = useRef<Uint8Array | null>(null);
    const animationFrameRef = useRef<number>();
    const streamRef = useRef<MediaStream | null>(null);

    const startAudio = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;

            const AudioContextClass = (window.AudioContext || (window as any).webkitAudioContext);
            const audioContext = new AudioContextClass();
            audioContextRef.current = audioContext;

            const source = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;

            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            source.connect(analyser);
            analyserRef.current = analyser;
            dataArrayRef.current = dataArray;

            const update = () => {
                if (!analyserRef.current || !dataArrayRef.current) return;

                analyserRef.current.getByteFrequencyData(dataArrayRef.current as any);

                // Calculate average volume (0-1)
                let sum = 0;
                for (let i = 0; i < dataArrayRef.current.length; i++) {
                    sum += dataArrayRef.current[i];
                }
                const avg = sum / dataArrayRef.current.length;
                setVolume(avg / 128); // Normalized 0 to 1-ish

                animationFrameRef.current = requestAnimationFrame(update);
            };

            update();
        } catch (err) {
            console.error("Error accessing microphone for visualizer:", err);
        }
    }, []);

    const stopAudio = useCallback(() => {
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
        setVolume(0);
    }, []);

    useEffect(() => {
        if (isListening) {
            startAudio();
        } else {
            stopAudio();
        }

        return () => stopAudio();
    }, [isListening, startAudio, stopAudio]);

    return { volume, analyser: analyserRef.current, dataArray: dataArrayRef.current };
};
