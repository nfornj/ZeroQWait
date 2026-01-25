import React, { useRef, useEffect } from 'react';
import { Box } from '@mui/material';

interface CanvasOrbProps {
    volume: number;
    isListening: boolean;
    primaryColor?: string;
}

/**
 * High-performance Canvas-based Orb and Orbit system.
 * Reacts in real-time to audio volume.
 */
const CanvasOrb: React.FC<CanvasOrbProps> = ({ volume, isListening, primaryColor = '#1976d2' }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const frameRef = useRef<number>();
    const timeRef = useRef(0);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const render = () => {
            const { width, height } = canvas;
            ctx.clearRect(0, 0, width, height);

            const centerX = width / 2;
            const centerY = height / 2;
            const baseRadius = 60;
            const pulse = volume * 40;
            const currentRadius = baseRadius + pulse;

            timeRef.current += 0.02 + (volume * 0.1);

            // 1. Draw Orbit Ring (The "Orbit")
            if (isListening) {
                ctx.beginPath();
                ctx.strokeStyle = primaryColor;
                ctx.lineWidth = 2;
                ctx.setLineDash([10, 20]);
                ctx.lineDashOffset = -timeRef.current * 10;

                const orbitRadiusX = currentRadius + 50 + (volume * 80);
                const orbitRadiusY = currentRadius + 30 + (volume * 40);
                ctx.ellipse(centerX, centerY, orbitRadiusX, orbitRadiusY, timeRef.current * 0.2, 0, Math.PI * 2);
                ctx.stroke();
                ctx.setLineDash([]); // Reset
            }

            // 2. Draw Glow Aura
            const gradient = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, currentRadius + 100);
            gradient.addColorStop(0, `${primaryColor}66`);
            gradient.addColorStop(0.5, `${primaryColor}22`);
            gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(centerX, centerY, currentRadius + 100, 0, Math.PI * 2);
            ctx.fill();

            // 3. Draw Core Orb
            const coreGradient = ctx.createRadialGradient(
                centerX - (currentRadius * 0.3),
                centerY - (currentRadius * 0.3),
                0,
                centerX,
                centerY,
                currentRadius
            );
            coreGradient.addColorStop(0, '#ffffff');
            coreGradient.addColorStop(1, primaryColor);

            ctx.fillStyle = coreGradient;
            ctx.beginPath();
            ctx.arc(centerX, centerY, currentRadius, 0, Math.PI * 2);
            ctx.shadowBlur = pulse + 10;
            ctx.shadowColor = primaryColor;
            ctx.fill();
            ctx.shadowBlur = 0; // Reset

            // 4. Floating Particles (Dynamic based on volume)
            if (isListening) {
                const particleCount = 12;
                for (let i = 0; i < particleCount; i++) {
                    const angle = (timeRef.current + (i * Math.PI * 2 / particleCount));
                    const dist = currentRadius + 80 + (Math.sin(timeRef.current * 2 + i) * 20);
                    const px = centerX + Math.cos(angle) * dist;
                    const py = centerY + Math.sin(angle) * dist;

                    ctx.fillStyle = primaryColor;
                    ctx.beginPath();
                    ctx.arc(px, py, 3 + volume * 5, 0, Math.PI * 2);
                    ctx.fill();
                }
            }

            frameRef.current = requestAnimationFrame(render);
        };

        render();

        return () => {
            if (frameRef.current) cancelAnimationFrame(frameRef.current);
        };
    }, [volume, isListening, primaryColor]);

    return (
        <Box
            sx={{
                width: 400,
                height: 400,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}
        >
            <canvas
                ref={canvasRef}
                width={800}
                height={800}
                style={{
                    width: '100%',
                    height: '100%',
                    transform: 'translateZ(0)' // Hardware acceleration hint
                }}
            />
        </Box>
    );
};

export default CanvasOrb;
