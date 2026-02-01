import React, { useRef, useEffect } from 'react';
import { Box } from '@mui/material';

interface ParticleSphereProps {
    volume: number;
    isListening: boolean;
    color?: string;
    isProcessing?: boolean;
}

const ParticleSphere: React.FC<ParticleSphereProps> = ({ volume, isListening, color = '#f5e1c0', isProcessing = false }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const particles = useRef<any[]>([]);
    const animationFrameId = useRef<number>();

    // Initial constants
    const PARTICLE_COUNT = 1500;
    const RADIUS = 180;

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Initialize particles in a 3D sphere
        particles.current = Array.from({ length: PARTICLE_COUNT }, () => {
            const phi = Math.acos(-1 + Math.random() * 2);
            const theta = Math.random() * Math.PI * 2;
            return {
                phi,
                theta,
                size: Math.random() * 1.5 + 0.5,
                opacity: Math.random() * 0.5 + 0.2
            };
        });

        let rotationX = 0;
        let rotationY = 0;
        let lastTime = performance.now();

        const render = () => {
            const currentTime = performance.now();
            const deltaTime = (currentTime - lastTime) / 1000;
            lastTime = currentTime;

            const width = canvas.width;
            const height = canvas.height;
            const centerX = width / 2;
            const centerY = height / 2;

            ctx.clearRect(0, 0, width, height);

            // Dynamic rotation based on volume OR processing state
            const baseSpeed = 0.5;
            // Spin fast if processing, or react to volume
            const speedMultiplier = isProcessing ? 12 : (1 + (volume * 10));

            rotationX += baseSpeed * speedMultiplier * deltaTime;
            rotationY += (baseSpeed * 1.5) * speedMultiplier * deltaTime;

            // Audio reaction factor - Stronger pulse
            // If processing, breathe deeply
            const processingPulse = isProcessing ? (1 + Math.sin(currentTime / 1000 * 6) * 0.15) : 1;
            const scale = (1 + (volume * 1.5)) * processingPulse;

            particles.current.forEach((p) => {
                // 1. Base Spherical -> Cartesian
                // phi (0..pi) is angle from UP (Y axis)
                // theta (0..2pi) is angle around Y axis
                let x = RADIUS * Math.sin(p.phi) * Math.cos(p.theta);
                let y = RADIUS * Math.cos(p.phi);
                let z = RADIUS * Math.sin(p.phi) * Math.sin(p.theta);

                // 2. Rotate around Y axis (Spin)
                // x' = x cos(ry) - z sin(ry)
                // z' = x sin(ry) + z cos(ry)
                const cosY = Math.cos(rotationY);
                const sinY = Math.sin(rotationY);
                let x1 = x * cosY - z * sinY;
                let z1 = x * sinY + z * cosY;
                let y1 = y;

                // 3. Rotate around X axis (Tilt)
                // y' = y cos(rx) - z sin(rx)
                // z' = y sin(rx) + z cos(rx)
                const cosX = Math.cos(rotationX);
                const sinX = Math.sin(rotationX);
                let y2 = y1 * cosX - z1 * sinX;
                let z2 = y1 * sinX + z1 * cosX;
                let x2 = x1;

                // Final Coordinates
                const px = x2;
                const py = y2;
                const pz = z2;

                // Simple 3D projection
                const perspective = 600;
                const fov = perspective / (perspective + pz);

                const sx = px * fov * scale + centerX;
                const sy = py * fov * scale + centerY;

                // Depth-based opacity and size
                const zNorm = (pz + RADIUS) / (RADIUS * 2);
                // Boost opacity with volume for "glowing" effect
                const alpha = (p.opacity * zNorm) + (volume * 0.8);

                ctx.beginPath();
                ctx.arc(sx, sy, (p.size * fov) * (1 + volume), 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.globalAlpha = Math.min(alpha, 1);
                ctx.fill();
            });

            animationFrameId.current = requestAnimationFrame(render);
        };

        render();

        return () => {
            if (animationFrameId.current) {
                cancelAnimationFrame(animationFrameId.current);
            }
        };
    }, [volume, color, isProcessing]);

    return (
        <Box sx={{
            width: '100%',
            maxWidth: { xs: 200, sm: 280, md: 400 },
            aspectRatio: '1',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            mx: 'auto'
        }}>
            <canvas
                ref={canvasRef}
                width={800}
                height={800}
                style={{
                    width: '100%',
                    height: '100%',
                    maxWidth: '100%',
                    maxHeight: '100%'
                }}
            />
        </Box>
    );
};

export default ParticleSphere;
