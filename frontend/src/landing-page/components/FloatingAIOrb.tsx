import React, { useState } from 'react';
import { Box, Typography, Fade } from '@mui/material';
import { styled, keyframes } from '@mui/material/styles';
import ParticleSphere from '../../components/agent/ParticleSphere';

const float = keyframes`
  0% { transform: translateY(0px) rotate(0deg); }
  50% { transform: translateY(-20px) rotate(2deg); }
  100% { transform: translateY(0px) rotate(0deg); }
`;

const pulse = keyframes`
  0% { box-shadow: 0 0 0 0 rgba(168, 85, 247, 0.4); }
  70% { box-shadow: 0 0 40px 20px rgba(168, 85, 247, 0); }
  100% { box-shadow: 0 0 0 0 rgba(168, 85, 247, 0); }
`;

const OrbWrapper = styled(Box)(({ theme }) => ({
    position: 'relative',
    width: '180px',
    height: '180px',
    cursor: 'pointer',
    animation: `${float} 6s ease-in-out infinite`,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    filter: 'drop-shadow(0 0 20px rgba(168, 85, 247, 0.3))',
    '&:hover': {
        filter: 'drop-shadow(0 0 30px rgba(168, 85, 247, 0.5))',
        '& .orb-label': {
            opacity: 1,
            transform: 'translateY(-10px)',
        }
    },
    [theme.breakpoints.down('sm')]: {
        width: '112px',
        height: '112px',
        filter: 'drop-shadow(0 0 16px rgba(168, 85, 247, 0.24))',
    },
}));

const GlowEffect = styled(Box)(({ theme }) => ({
    position: 'absolute',
    width: '140px',
    height: '140px',
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(168, 85, 247, 0.2) 0%, transparent 70%)',
    animation: `${pulse} 4s infinite`,
    pointerEvents: 'none',
    [theme.breakpoints.down('sm')]: {
        width: '92px',
        height: '92px',
    },
}));

const Label = styled(Typography)(({ theme }) => ({
    position: 'absolute',
    top: '-75px',
    color: '#A855F7',
    fontWeight: 600,
    fontSize: '0.9rem',
    letterSpacing: '0.05em',
    opacity: 0,
    transform: 'translateY(0px)',
    transition: 'all 0.3s ease',
    textAlign: 'center',
    whiteSpace: 'nowrap',
    textShadow: '0 0 10px rgba(168, 85, 247, 0.2)',
    [theme.breakpoints.down('sm')]: {
        top: '-34px',
        opacity: 1,
        fontSize: '0.72rem',
        letterSpacing: '0.14em',
    },
}));

const FloatingAIOrb: React.FC = () => {
    const [isHovered, setIsHovered] = useState(false);

    const handleClick = () => {
        console.log('[DEBUG] Dispatching trigger-zeroq-assistant');
        window.dispatchEvent(new CustomEvent('trigger-zeroq-assistant'));
    };

    return (
        <OrbWrapper
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onClick={handleClick}
        >
            <GlowEffect />
            <Box sx={{ transform: { xs: 'scale(0.32)', sm: 'scale(0.45)' }, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <ParticleSphere volume={isHovered ? 0.1 : 0.05} isListening={false} color="#D8B4FE" />
            </Box>
            <Label className="orb-label">
                MEET ZEROQ
            </Label>
        </OrbWrapper>
    );
};

export default FloatingAIOrb;
