import React, { useState } from 'react';
import {
    Box,
    IconButton,
    Menu,
    MenuItem,
    Typography,
    Tooltip,
    Divider,
    ListItemIcon
} from '@mui/material';
import PaletteIcon from '@mui/icons-material/Palette';
import CheckIcon from '@mui/icons-material/Check';
import { useThemeContext, GradientPreset, gradientPresets } from '../../../contexts/ThemeContext';

const ThemeCustomizer: React.FC = () => {
    const { dashboardGradient, setDashboardGradient } = useThemeContext();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleSelect = (preset: GradientPreset) => {
        setDashboardGradient(preset);
        handleClose();
    };

    const presets: { id: GradientPreset; label: string; color: string }[] = [
        { id: 'violet', label: 'Violet Dream', color: '#E0C3FC' },
        { id: 'ocean', label: 'Ocean Breeze', color: '#a8edea' },
        { id: 'sunset', label: 'Golden Hour', color: '#f6d365' },
        { id: 'minimal', label: 'Minimal White', color: '#FFFFFF' },
    ];

    return (
        <>
            <Tooltip title="Customize Theme">
                <IconButton
                    onClick={handleClick}
                    size="small"
                    sx={{ ml: 2 }}
                    aria-controls={open ? 'theme-menu' : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <PaletteIcon />
                </IconButton>
            </Tooltip>
            <Menu
                anchorEl={anchorEl}
                id="theme-menu"
                open={open}
                onClose={handleClose}
                onClick={handleClose}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        overflow: 'visible',
                        filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
                        mt: 1.5,
                        '&:before': {
                            content: '""',
                            display: 'block',
                            position: 'absolute',
                            top: 0,
                            right: 14,
                            width: 10,
                            height: 10,
                            bgcolor: 'background.paper',
                            transform: 'translateY(-50%) rotate(45deg)',
                            zIndex: 0,
                        },
                    },
                }}
                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
                <Box sx={{ px: 2, py: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={600}>
                        Background Theme
                    </Typography>
                </Box>
                <Divider />
                {presets.map((preset) => (
                    <MenuItem key={preset.id} onClick={() => handleSelect(preset.id)}>
                        <ListItemIcon>
                            <Box
                                sx={{
                                    width: 20,
                                    height: 20,
                                    borderRadius: '50%',
                                    // Default to light mode for preview, or could extract mode from context if needed
                                    background: gradientPresets[preset.id].light === 'none' ? '#f5f5f5' : gradientPresets[preset.id].light,
                                    border: '1px solid rgba(0,0,0,0.1)'
                                }}
                            />
                        </ListItemIcon>
                        <Typography variant="body2" sx={{ flexGrow: 1 }}>
                            {preset.label}
                        </Typography>
                        {dashboardGradient === preset.id && (
                            <CheckIcon fontSize="small" color="primary" sx={{ ml: 2 }} />
                        )}
                    </MenuItem>
                ))}
            </Menu>
        </>
    );
};

export default ThemeCustomizer;
