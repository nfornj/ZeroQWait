import React, { useRef, useEffect } from 'react';

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

    // Interaction Refs
    const mouseRef = useRef({ x: 0, y: 0 });
    const isHoveredRef = useRef(false);

    // Initial constants - Boosted for brightness
    const PARTICLE_COUNT = 2000;
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
                opacity: Math.random() * 0.5 + 0.5 // Boosted basal opacity for brightness
            };
        });

        let rotationX = 0;
        let rotationY = 0;
        let lastTime = performance.now();
        let currentScale = 1;

        const render = () => {
            const currentTime = performance.now();
            const deltaTime = (currentTime - lastTime) / 1000;
            lastTime = currentTime;

            const width = canvas.width;
            const height = canvas.height;
            const centerX = width / 2;
            const centerY = height / 2;

            ctx.clearRect(0, 0, width, height);

            // Dynamic rotation logic
            const baseSpeed = 0.5;
            const speedMultiplier = isProcessing ? 12 : (1 + (volume * 10));

            // Mouse Interaction Logic
            // Mouse X affects Y-rotation (Spin), Mouse Y affects X-rotation (Tilt)
            const mouseX = mouseRef.current.x;
            const mouseY = mouseRef.current.y;

            const mouseInfluenceX = isHoveredRef.current ? (mouseY * 2) : 0;
            const mouseInfluenceY = isHoveredRef.current ? (mouseX * 2) : 0;

            rotationX += (baseSpeed * speedMultiplier + mouseInfluenceX) * deltaTime;
            rotationY += ((baseSpeed * 1.5) * speedMultiplier + mouseInfluenceY) * deltaTime;

            // Scale Logic (Breathing on hover)
            const targetScale = isHoveredRef.current ? 1.1 : 1.0;
            currentScale += (targetScale - currentScale) * 5 * deltaTime; // Smooth Lerp

            // Audio reaction factor
            const processingPulse = isProcessing ? (1 + Math.sin(currentTime / 1000 * 6) * 0.15) : 1;
            const scale = (currentScale + (volume * 1.5)) * processingPulse;

            particles.current.forEach((p) => {
                // 1. Base Spherical -> Cartesian
                let x = RADIUS * Math.sin(p.phi) * Math.cos(p.theta);
                let y = RADIUS * Math.cos(p.phi);
                let z = RADIUS * Math.sin(p.phi) * Math.sin(p.theta);

                // 2. Rotate around Y axis (Spin)
                const cosY = Math.cos(rotationY);
                const sinY = Math.sin(rotationY);
                let x1 = x * cosY - z * sinY;
                let z1 = x * sinY + z * cosY;
                let y1 = y;

                // 3. Rotate around X axis (Tilt)
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

                // Opacity Calculation - Brighter Base
                let alpha = (p.opacity * zNorm) + (volume * 0.8);
                if (isHoveredRef.current) alpha += 0.15; // Extra brightness on hover

                ctx.beginPath();
                ctx.arc(sx, sy, (p.size * fov) * (1 + volume), 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.globalAlpha = Math.min(Math.max(alpha, 0), 1);
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

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * 2 - 1; // -1 to 1
        const y = ((e.clientY - rect.top) / rect.height) * 2 - 1; // -1 to 1
        mouseRef.current = { x, y };
    };

    return (
        <div
            onMouseEnter={() => isHoveredRef.current = true}
            onMouseLeave={() => {
                isHoveredRef.current = false;
                mouseRef.current = { x: 0, y: 0 };
            }}
            onMouseMove={handleMouseMove}
            className="mx-auto flex aspect-square w-full max-w-[200px] cursor-pointer items-center justify-center transition-transform sm:max-w-[280px] md:max-w-[400px]"
        >
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
        </div>
    );
};

export default ParticleSphere;
