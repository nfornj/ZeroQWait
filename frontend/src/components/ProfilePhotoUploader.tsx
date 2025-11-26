import React, { useState, useRef, useEffect, useCallback } from 'react';
import Webcam from 'react-webcam';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Box,
    Tabs,
    Tab,
    Typography,
    Avatar,
    IconButton,
    Alert,
    CircularProgress,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import PhotoCameraIcon from '@mui/icons-material/PhotoCamera';
import FlipCameraIosIcon from '@mui/icons-material/FlipCameraIos';
import CloseIcon from '@mui/icons-material/Close';

interface ProfilePhotoUploaderProps {
    open: boolean;
    onClose: () => void;
    onUpload: (photoUrl: string) => Promise<void>;
    currentPhotoUrl?: string;
}

const ProfilePhotoUploader: React.FC<ProfilePhotoUploaderProps> = ({
    open,
    onClose,
    onUpload,
    currentPhotoUrl,
}) => {
    const [tabValue, setTabValue] = useState(0);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string>('');
    const [capturedImage, setCapturedImage] = useState<string>('');
    const [facingMode, setFacingMode] = useState<'user' | 'environment'>('user');
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');

    const webcamRef = useRef<Webcam>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (!open) {
            setSelectedFile(null);
            setPreviewUrl('');
            setCapturedImage('');
            setError('');
            setTabValue(0);
        }
    }, [open]);

    const switchCamera = () => {
        setFacingMode(facingMode === 'user' ? 'environment' : 'user');
    };

    const capturePhoto = useCallback(() => {
        const imageSrc = webcamRef.current?.getScreenshot();
        if (imageSrc) {
            setCapturedImage(imageSrc);
        }
    }, [webcamRef]);

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        // Validate file type
        if (!file.type.startsWith('image/')) {
            setError('Please select an image file');
            return;
        }

        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            setError('Image size must be less than 5MB');
            return;
        }

        setSelectedFile(file);
        setError('');

        // Create preview
        const reader = new FileReader();
        reader.onloadend = () => {
            setPreviewUrl(reader.result as string);
        };
        reader.readAsDataURL(file);
    };

    const handleUploadFile = async () => {
        if (!previewUrl) return;

        try {
            setUploading(true);
            setError('');
            
            // In a real app, you would upload to a storage service (S3, Cloudinary, etc.)
            // For now, we'll use the base64 data URL
            await onUpload(previewUrl);
            
            onClose();
        } catch (err: any) {
            setError(err.message || 'Failed to upload photo');
        } finally {
            setUploading(false);
        }
    };

    const handleUploadCapture = async () => {
        if (!capturedImage) return;

        try {
            setUploading(true);
            setError('');
            
            await onUpload(capturedImage);
            
            onClose();
        } catch (err: any) {
            setError(err.message || 'Failed to upload photo');
        } finally {
            setUploading(false);
        }
    };

    const retakePhoto = () => {
        setCapturedImage('');
    };

    return (
        <Dialog 
            open={open} 
            onClose={onClose} 
            maxWidth="sm" 
            fullWidth
            PaperProps={{
                sx: { borderRadius: 2 }
            }}
        >
            <DialogTitle>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6">Update Profile Photo</Typography>
                    <IconButton onClick={onClose} size="small">
                        <CloseIcon />
                    </IconButton>
                </Box>
            </DialogTitle>

            <DialogContent>
                {error && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                        {error}
                    </Alert>
                )}

                <Tabs 
                    value={tabValue} 
                    onChange={(_, newValue) => {
                        setTabValue(newValue);
                        setCapturedImage('');
                        setPreviewUrl('');
                        setSelectedFile(null);
                        setError('');
                    }}
                    variant="fullWidth"
                    sx={{ mb: 3 }}
                >
                    <Tab icon={<CloudUploadIcon />} label="Upload File" />
                    <Tab icon={<CameraAltIcon />} label="Take Photo" />
                </Tabs>

                {/* Upload File Tab */}
                {tabValue === 0 && (
                    <Box>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            onChange={handleFileSelect}
                            style={{ display: 'none' }}
                        />

                        {previewUrl ? (
                            <Box textAlign="center">
                                <Avatar
                                    src={previewUrl}
                                    sx={{
                                        width: 200,
                                        height: 200,
                                        margin: '0 auto 16px',
                                        border: '4px solid',
                                        borderColor: 'primary.main',
                                    }}
                                />
                                <Button
                                    variant="outlined"
                                    onClick={() => fileInputRef.current?.click()}
                                    sx={{ mt: 2 }}
                                >
                                    Choose Different Photo
                                </Button>
                            </Box>
                        ) : (
                            <Box
                                sx={{
                                    border: '2px dashed',
                                    borderColor: 'divider',
                                    borderRadius: 2,
                                    p: 4,
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    '&:hover': {
                                        borderColor: 'primary.main',
                                        bgcolor: 'action.hover',
                                    },
                                }}
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <CloudUploadIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                                <Typography variant="h6" gutterBottom>
                                    Click to upload
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    JPG, PNG or GIF (max 5MB)
                                </Typography>
                            </Box>
                        )}
                    </Box>
                )}

                {/* Take Photo Tab */}
                {tabValue === 1 && (
                    <Box>
                        {!capturedImage && (
                            <Box position="relative" sx={{ aspectRatio: '4/3', bgcolor: 'black', borderRadius: 2, overflow: 'hidden' }}>
                                <Webcam
                                    ref={webcamRef}
                                    audio={false}
                                    screenshotFormat="image/jpeg"
                                    videoConstraints={{
                                        facingMode: facingMode,
                                        width: 1280,
                                        height: 720,
                                    }}
                                    style={{
                                        width: '100%',
                                        height: '100%',
                                        objectFit: 'cover',
                                    }}
                                    mirrored={facingMode === 'user'}
                                    onUserMediaError={(err) => {
                                        console.error('Camera error:', err);
                                        setError('Could not access camera. Please check permissions.');
                                    }}
                                />
                                {/* Face guide overlay */}
                                <Box
                                    sx={{
                                        position: 'absolute',
                                        top: '50%',
                                        left: '50%',
                                        transform: 'translate(-50%, -50%)',
                                        width: '200px',
                                        height: '250px',
                                        border: '4px solid',
                                        borderColor: '#FF5A5F',
                                        borderRadius: '50%',
                                        boxShadow: '0 0 0 9999px rgba(0,0,0,0.5)',
                                        pointerEvents: 'none',
                                    }}
                                >
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            position: 'absolute',
                                            top: -40,
                                            left: '50%',
                                            transform: 'translateX(-50%)',
                                            color: 'white',
                                            bgcolor: '#FF5A5F',
                                            px: 2,
                                            py: 1,
                                            borderRadius: 2,
                                            whiteSpace: 'nowrap',
                                            fontWeight: 600,
                                        }}
                                    >
                                        📸 Center your face here
                                    </Typography>
                                </Box>
                                <Box
                                    sx={{
                                        position: 'absolute',
                                        bottom: 20,
                                        left: '50%',
                                        transform: 'translateX(-50%)',
                                        display: 'flex',
                                        gap: 2,
                                        alignItems: 'center',
                                    }}
                                >
                                    <IconButton
                                        onClick={switchCamera}
                                        sx={{
                                            bgcolor: 'rgba(255,255,255,0.9)',
                                            '&:hover': { bgcolor: 'white' },
                                            width: 50,
                                            height: 50,
                                        }}
                                    >
                                        <FlipCameraIosIcon />
                                    </IconButton>
                                    <Button
                                        variant="contained"
                                        size="large"
                                        onClick={capturePhoto}
                                        startIcon={<PhotoCameraIcon />}
                                        sx={{
                                            px: 4,
                                            py: 1.5,
                                            fontSize: '1.1rem',
                                            bgcolor: '#FF5A5F',
                                            '&:hover': { bgcolor: '#E54950' },
                                            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                                        }}
                                    >
                                        Capture
                                    </Button>
                                </Box>
                            </Box>
                        )}

                        {capturedImage && (
                            <Box textAlign="center">
                                <Avatar
                                    src={capturedImage}
                                    sx={{
                                        width: 200,
                                        height: 200,
                                        margin: '0 auto 16px',
                                        border: '4px solid',
                                        borderColor: 'primary.main',
                                    }}
                                />
                                <Button
                                    variant="outlined"
                                    onClick={retakePhoto}
                                    sx={{ mt: 2 }}
                                >
                                    Retake Photo
                                </Button>
                            </Box>
                        )}
                    </Box>
                )}
            </DialogContent>

            <DialogActions sx={{ p: 3 }}>
                <Button onClick={onClose} disabled={uploading}>
                    Cancel
                </Button>
                <Button
                    onClick={tabValue === 0 ? handleUploadFile : handleUploadCapture}
                    variant="contained"
                    disabled={
                        uploading ||
                        (tabValue === 0 && !previewUrl) ||
                        (tabValue === 1 && !capturedImage)
                    }
                    startIcon={uploading && <CircularProgress size={20} />}
                >
                    {uploading ? 'Uploading...' : 'Upload Photo'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default ProfilePhotoUploader;
