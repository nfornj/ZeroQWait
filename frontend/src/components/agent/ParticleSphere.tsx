import React, { useRef, useEffect } from 'react';
import { Box } from '@mui/material';

interface ParticleSphereProps {
    volume: number;
    isListening: boolean;
    color?: string;
}

const ParticleSphere: React.FC<ParticleSphereProps> = ({ volume, isListening, color = '#f5e1c0' }) => {
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

        const render = () => {
            const width = canvas.width;
            const height = canvas.height;
            const centerX = width / 2;
            const centerY = height / 2;

            ctx.clearRect(0, 0, width, height);

            rotationX += 0.003;
            rotationY += 0.005;

            // Audio reaction factor
            const scale = 1 + (volume * 1.2);

            particles.current.forEach((p) => {
                // Rotation logic
                let px = RADIUS * Math.sin(p.phi) * Math.cos(p.theta + rotationY);
                let py = RADIUS * Math.cos(p.phi + rotationX);
                let pz = RADIUS * Math.sin(p.phi) * Math.sin(p.theta + rotationY);

                // Simple 3D projection
                const perspective = 600;
                const fov = perspective / (perspective + pz);

                const sx = px * fov * scale + centerX;
                const sy = py * fov * scale + centerY;

                // Depth-based opacity and size
                const zNorm = (pz + RADIUS) / (RADIUS * 2);
                const alpha = (p.opacity * zNorm * scale) + (volume * 0.5);

                ctx.beginPath();
                ctx.arc(sx, sy, p.size * fov, 0, Math.PI * 2);
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
    }, [volume, color]);

    return (
        <Box sx={{ width: '100%', height: 400, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <canvas
                ref={canvasRef}
                width={800}
                height={800}
                style={{ width: 400, height: 400, transform: 'scale(1.2)' }}
            />
        </Box>
    );
};

export default ParticleSphere;
