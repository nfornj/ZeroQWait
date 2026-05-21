import React, { useState, useRef, useEffect, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Upload, Camera, RefreshCw, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import { Avatar, AvatarImage, AvatarFallback } from './ui/avatar';
import { cn } from '../lib/utils';

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
  const [activeTab, setActiveTab] = useState<'upload' | 'camera'>('upload');
  const [previewUrl, setPreviewUrl] = useState('');
  const [capturedImage, setCapturedImage] = useState('');
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('user');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const webcamRef = useRef<Webcam>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      setPreviewUrl('');
      setCapturedImage('');
      setError('');
      setActiveTab('upload');
    }
  }, [open]);

  const capturePhoto = useCallback(() => {
    const imageSrc = webcamRef.current?.getScreenshot();
    if (imageSrc) setCapturedImage(imageSrc);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { setError('Please select an image file'); return; }
    if (file.size > 5 * 1024 * 1024) { setError('Image size must be less than 5MB'); return; }
    setError('');
    const reader = new FileReader();
    reader.onloadend = () => setPreviewUrl(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleUpload = async (imageData: string) => {
    if (!imageData) return;
    setUploading(true);
    setError('');
    try {
      await onUpload(imageData);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to upload photo');
    } finally {
      setUploading(false);
    }
  };

  const isUploadReady = activeTab === 'upload' ? !!previewUrl : !!capturedImage;
  const handleConfirm = () => {
    if (activeTab === 'upload') handleUpload(previewUrl);
    else handleUpload(capturedImage);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Update Profile Photo</DialogTitle>
        </DialogHeader>

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
            <button onClick={() => setError('')} className="ml-2 text-red-400 hover:text-red-300"><X className="inline h-3 w-3" /></button>
          </div>
        )}

        <Tabs value={activeTab} onValueChange={(v) => {
          setActiveTab(v as 'upload' | 'camera');
          setCapturedImage('');
          setPreviewUrl('');
          setError('');
        }}>
          <TabsList className="w-full">
            <TabsTrigger value="upload" className="flex-1 gap-2"><Upload className="h-4 w-4" />Upload File</TabsTrigger>
            <TabsTrigger value="camera" className="flex-1 gap-2"><Camera className="h-4 w-4" />Take Photo</TabsTrigger>
          </TabsList>

          {/* Upload tab */}
          <TabsContent value="upload" className="mt-4">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />
            {previewUrl ? (
              <div className="flex flex-col items-center gap-4">
                <Avatar className="h-40 w-40 border-4 border-primary">
                  <AvatarImage src={previewUrl} />
                  <AvatarFallback>Preview</AvatarFallback>
                </Avatar>
                <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
                  Choose Different Photo
                </Button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "flex w-full flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border p-10 text-center transition-colors",
                  "hover:border-primary hover:bg-muted/30 cursor-pointer"
                )}
              >
                <Upload className="h-12 w-12 text-muted-foreground" />
                <div>
                  <p className="font-semibold text-foreground">Click to upload</p>
                  <p className="text-sm text-muted-foreground">JPG, PNG or GIF (max 5MB)</p>
                </div>
              </button>
            )}
          </TabsContent>

          {/* Camera tab */}
          <TabsContent value="camera" className="mt-4">
            {!capturedImage ? (
              <div className="relative overflow-hidden rounded-xl bg-black" style={{ aspectRatio: '4/3' }}>
                <Webcam
                  ref={webcamRef}
                  audio={false}
                  screenshotFormat="image/jpeg"
                  videoConstraints={{ facingMode, width: 1280, height: 720 }}
                  className="h-full w-full object-cover"
                  mirrored={facingMode === 'user'}
                  onUserMediaError={() => setError('Could not access camera. Please check permissions.')}
                />
                {/* Face guide */}
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                  <div
                    className="rounded-full border-4 border-violet-500"
                    style={{ width: 180, height: 220, boxShadow: '0 0 0 9999px rgba(0,0,0,0.45)' }}
                  />
                  <span className="absolute top-[calc(50%-140px)] rounded bg-violet-600 px-3 py-1 text-xs font-semibold text-white">
                    Center your face here
                  </span>
                </div>
                {/* Controls */}
                <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setFacingMode(facingMode === 'user' ? 'environment' : 'user')}
                    className="flex h-10 w-10 items-center justify-center rounded-full bg-white/90 text-black shadow-lg hover:bg-white"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </button>
                  <Button onClick={capturePhoto} className="gap-2 bg-violet-600 hover:bg-violet-500 px-6">
                    <Camera className="h-4 w-4" /> Capture
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                <Avatar className="h-40 w-40 border-4 border-primary">
                  <AvatarImage src={capturedImage} />
                  <AvatarFallback>Capture</AvatarFallback>
                </Avatar>
                <Button variant="outline" onClick={() => setCapturedImage('')}>
                  Retake Photo
                </Button>
              </div>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} disabled={uploading}>Cancel</Button>
          <Button
            onClick={handleConfirm}
            disabled={uploading || !isUploadReady}
            className="bg-violet-600 hover:bg-violet-500 text-white"
          >
            {uploading ? 'Uploading...' : 'Upload Photo'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ProfilePhotoUploader;
