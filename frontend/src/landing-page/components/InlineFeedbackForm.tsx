import React, { useRef, useState } from "react";
import axios from "axios";
import { CheckCircle2, Image, Loader2, MessageSquareWarning, X } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface InlineFeedbackFormProps {
  sessionId?: string;
  pageContext?: string;
  onDismiss?: () => void;
}

const InlineFeedbackForm: React.FC<InlineFeedbackFormProps> = ({
  sessionId,
  pageContext = "landing_page",
  onDismiss,
}) => {
  const [description, setDescription] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setError("Screenshot must be under 10 MB.");
      return;
    }
    setScreenshot(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError(null);
  };

  const removeScreenshot = () => {
    setScreenshot(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSubmit = async () => {
    if (!description.trim()) {
      setError("Please describe the issue.");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("description", description.trim());
      if (name.trim()) formData.append("name", name.trim());
      if (email.trim()) formData.append("email", email.trim());
      if (sessionId) formData.append("session_id", sessionId);
      formData.append("page_context", pageContext);
      if (screenshot) formData.append("screenshot", screenshot);

      const res = await axios.post("/api/chat-feedback/submit", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setTicketId(res.data.ticket_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (ticketId) {
    return (
      <Card className="w-full max-w-md border-primary/40">
        <CardContent className="flex gap-3 p-5">
          <CheckCircle2 className="size-6 shrink-0 text-primary" />
          <div>
            <p className="font-bold text-primary">Feedback submitted. Thank you.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Ticket ID: <span className="font-mono font-bold text-foreground">{ticketId}</span>
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquareWarning className="size-4 text-primary" />
          Submit Feedback
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="feedback-description">Describe the issue</Label>
          <Textarea
            id="feedback-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What happened? What did you expect?"
            maxLength={2000}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="feedback-name">Your name (optional)</Label>
            <Input id="feedback-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={100} />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="feedback-email">Email (optional)</Label>
            <Input id="feedback-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} maxLength={200} />
          </div>
        </div>

        {previewUrl ? (
          <div className="relative w-fit">
            <img src={previewUrl} alt="Screenshot preview" className="max-h-32 max-w-52 rounded-lg border object-contain" />
            <Button type="button" size="icon" variant="secondary" className="absolute -right-3 -top-3 size-7" onClick={removeScreenshot}>
              <X />
            </Button>
          </div>
        ) : (
          <Button type="button" variant="outline" size="sm" className="self-start" onClick={() => fileInputRef.current?.click()}>
            <Image data-icon="inline-start" />
            Attach screenshot
          </Button>
        )}
        <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={handleSubmit} disabled={submitting || !description.trim()}>
            {submitting && <Loader2 data-icon="inline-start" className="animate-spin" />}
            {submitting ? "Submitting..." : "Submit feedback"}
          </Button>
          {onDismiss && (
            <Button size="sm" variant="ghost" onClick={onDismiss}>
              Cancel
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default InlineFeedbackForm;
