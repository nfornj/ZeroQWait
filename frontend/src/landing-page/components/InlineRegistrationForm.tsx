import React, { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, CheckCircle2, Eye, EyeOff, Loader2, PartyPopper, Store, User, XCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export interface FormField {
  name: string;
  type:
    | "choice"
    | "text"
    | "email"
    | "password"
    | "tel"
    | "chip_select"
    | "confirm";
  label: string;
  placeholder?: string;
  required?: boolean;
  min_length?: number;
  max_length?: number;
  show_strength?: boolean;
  allow_custom?: boolean;
  custom_placeholder?: string;
  validate_async?: string;
  options?: Array<{
    value: string;
    label: string;
    icon?: string;
    description?: string;
  }>;
}

export interface FormStepData {
  type: "form_step";
  step: string;
  message: string;
  prompt: string;
  fields: FormField[];
  progress: number;
  step_number: number;
  total_steps: number;
  summary?: Record<string, string>;
  errors?: Record<string, string>;
}

export interface FormDoneData {
  type: "form_done";
  success: boolean;
  message: string;
  account_type?: string;
  username?: string;
  email?: string;
  shop?: { name: string; slug: string; type: string } | null;
}

interface InlineRegistrationFormProps {
  formStep: FormStepData;
  sessionId: string;
  theme: any;
  isDarkMode: boolean;
  disabled?: boolean;
  onFormResult: (result: FormStepData | FormDoneData) => void;
}

const iconForOption = (name?: string) => {
  if (name === "store") return Store;
  if (name === "person") return User;
  return User;
};

function getPasswordStrength(password: string): {
  label: string;
  colorClass: string;
  value: number;
} {
  if (password.length < 8) return { label: "Too short", colorClass: "bg-destructive", value: 20 };
  let score = 0;
  if (/[a-z]/.test(password)) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;
  if (password.length >= 12) score++;
  if (score <= 2) return { label: "Weak", colorClass: "bg-amber-500", value: 40 };
  if (score <= 3) return { label: "Good", colorClass: "bg-blue-500", value: 70 };
  return { label: "Strong", colorClass: "bg-emerald-500", value: 100 };
}

const InlineRegistrationForm: React.FC<InlineRegistrationFormProps> = ({
  formStep,
  sessionId,
  disabled = false,
  onFormResult,
}) => {
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>(formStep.errors || {});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showCustomChip, setShowCustomChip] = useState(false);
  const [asyncStatus, setAsyncStatus] = useState<Record<string, { checking: boolean; available?: boolean; message?: string }>>({});
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    if (formStep.errors) setErrors(formStep.errors);
  }, [formStep.errors]);

  const asyncValidate = useCallback((field: string, value: string, url: string) => {
    if (debounceTimers.current[field]) clearTimeout(debounceTimers.current[field]);
    if (!value || value.length < 2) {
      setAsyncStatus((prev) => ({ ...prev, [field]: { checking: false } }));
      return;
    }

    setAsyncStatus((prev) => ({ ...prev, [field]: { checking: true } }));
    debounceTimers.current[field] = setTimeout(async () => {
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value }),
        });
        const data = await res.json();
        setAsyncStatus((prev) => ({
          ...prev,
          [field]: { checking: false, available: data.available, message: data.message },
        }));
        if (!data.available) {
          setErrors((prev) => ({ ...prev, [field]: data.message }));
        } else {
          setErrors((prev) => {
            const next = { ...prev };
            delete next[field];
            return next;
          });
        }
      } catch {
        setAsyncStatus((prev) => ({ ...prev, [field]: { checking: false } }));
      }
    }, 500);
  }, []);

  const handleChange = (name: string, value: string, field?: FormField) => {
    setValues((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
    if (field?.validate_async && value.length >= (field.min_length || 2)) {
      asyncValidate(name, value, field.validate_async);
    }
  };

  const postStep = async (data: Record<string, string>) => {
    const res = await fetch("/api/agent/registration/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, data }),
    });
    return res.json();
  };

  const handleSubmit = async () => {
    if (disabled || isSubmitting) return;

    const clientErrors: Record<string, string> = {};
    for (const field of formStep.fields) {
      if (field.required && !values[field.name]?.trim()) {
        clientErrors[field.name] = `${field.label} is required`;
      }
      if (field.min_length && (values[field.name]?.length || 0) < field.min_length) {
        clientErrors[field.name] = `Must be at least ${field.min_length} characters`;
      }
    }
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      return;
    }
    if (Object.values(asyncStatus).some((status) => status.available === false)) return;

    setIsSubmitting(true);
    try {
      const result = await postStep(values);
      if (result.errors) {
        setErrors(result.errors);
        return;
      }
      onFormResult(result);
    } catch {
      setErrors({ _general: "Something went wrong. Please try again." });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChoiceSelect = async (field: FormField, value: string) => {
    if (disabled || isSubmitting) return;
    setValues({ [field.name]: value });
    setIsSubmitting(true);
    try {
      const result = await postStep({ [field.name]: value });
      if (result.errors) setErrors(result.errors);
      else onFormResult(result);
    } catch {
      setErrors({ _general: "Something went wrong." });
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderChoiceField = (field: FormField) => (
    <div className="mt-3 flex flex-col gap-3">
      {field.options?.map((option) => {
        const Icon = iconForOption(option.icon);
        const selected = values[field.name] === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => handleChoiceSelect(field, option.value)}
            disabled={disabled || isSubmitting}
            className={cn(
              "flex w-full items-center gap-3 rounded-xl border p-4 text-left transition",
              selected ? "border-primary bg-primary/10" : "hover:border-primary/60 hover:bg-muted/50",
              disabled && "cursor-default opacity-70",
            )}
          >
            <Icon className="size-7 shrink-0 text-primary" />
            <span>
              <span className="block font-semibold">{option.label}</span>
              {option.description && <span className="text-sm text-muted-foreground">{option.description}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );

  const renderTextField = (field: FormField) => {
    const isPassword = field.type === "password";
    const password = isPassword ? values[field.name] || "" : "";
    const strength = isPassword ? getPasswordStrength(password) : null;
    const status = asyncStatus[field.name];
    const inputType = isPassword && !showPassword ? "password" : field.type === "email" ? "email" : field.type === "tel" ? "tel" : "text";

    return (
      <div className="mt-3 flex flex-col gap-2" key={field.name}>
        <Label htmlFor={field.name}>{field.label}</Label>
        <div className="relative">
          <Input
            id={field.name}
            type={inputType}
            placeholder={field.placeholder}
            value={values[field.name] || ""}
            onChange={(event) => handleChange(field.name, event.target.value, field)}
            disabled={disabled || isSubmitting}
            maxLength={field.max_length || 200}
            aria-invalid={!!errors[field.name]}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleSubmit();
              }
            }}
            className={cn((isPassword || status) && "pr-20")}
          />
          <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1">
            {isPassword && (
              <Button type="button" variant="ghost" size="icon" className="size-7" onClick={() => setShowPassword((prev) => !prev)}>
                {showPassword ? <EyeOff /> : <Eye />}
              </Button>
            )}
            {status?.checking && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
            {status && !status.checking && status.available === true && <CheckCircle2 className="size-4 text-emerald-500" />}
            {status && !status.checking && status.available === false && <XCircle className="size-4 text-destructive" />}
          </div>
        </div>
        {errors[field.name] && <p className="text-xs text-destructive">{errors[field.name]}</p>}
        {isPassword && field.show_strength && password.length > 0 && strength && (
          <div className="flex flex-col gap-1">
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full transition-all", strength.colorClass)} style={{ width: `${strength.value}%` }} />
            </div>
            <p className="text-xs text-muted-foreground">{strength.label}</p>
          </div>
        )}
        {status && !status.checking && status.message && !errors[field.name] && (
          <p className={cn("text-xs", status.available ? "text-emerald-600" : "text-destructive")}>{status.message}</p>
        )}
      </div>
    );
  };

  const renderChipSelect = (field: FormField) => {
    const selected = values[field.name] || "";
    return (
      <div className="mt-3 flex flex-col gap-2">
        <div className="flex flex-wrap gap-2">
          {field.options?.map((option) => (
            <Button
              key={option.value}
              type="button"
              variant={selected === option.value ? "default" : "outline"}
              size="sm"
              onClick={() => {
                if (!disabled && !isSubmitting) {
                  handleChange(field.name, option.value);
                  setShowCustomChip(false);
                }
              }}
            >
              {option.label}
            </Button>
          ))}
          {field.allow_custom && (
            <Button type="button" variant="outline" size="sm" onClick={() => !disabled && setShowCustomChip(true)}>
              Other...
            </Button>
          )}
        </div>
        {showCustomChip && (
          <Input
            placeholder={field.custom_placeholder || "Enter custom type"}
            value={values[field.name] || ""}
            onChange={(event) => handleChange(field.name, event.target.value)}
            disabled={disabled || isSubmitting}
          />
        )}
        {errors[field.name] && <p className="text-xs text-destructive">{errors[field.name]}</p>}
      </div>
    );
  };

  const renderConfirm = () => {
    const summary = formStep.summary || {};
    return (
      <Card className="mt-3">
        <CardContent className="flex flex-col gap-2 p-4">
          {Object.entries(summary).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-4 text-sm">
              <span className="capitalize text-muted-foreground">{key.replace(/_/g, " ")}</span>
              <span className="font-semibold text-right">{value}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    );
  };

  const field0 = formStep.fields[0];
  const isChoice = field0?.type === "choice";
  const isChip = field0?.type === "chip_select";
  const isConfirm = field0?.type === "confirm";
  const isAddressGroup = formStep.step === "shop_address";
  const needsSubmitButton = !isChoice;

  return (
    <div className="mt-1 w-full">
      <div className="mb-4 flex items-center gap-3">
        <Progress value={formStep.progress} className="h-2 flex-1" />
        <span className="whitespace-nowrap text-xs text-muted-foreground">
          {formStep.step_number}/{formStep.total_steps}
        </span>
      </div>

      {errors._general && (
        <Alert variant="destructive" className="mb-3">
          <AlertDescription>{errors._general}</AlertDescription>
        </Alert>
      )}

      {isChoice && renderChoiceField(field0)}
      {isChip && renderChipSelect(field0)}
      {isConfirm && renderConfirm()}
      {isAddressGroup && formStep.fields.map((field) => renderTextField(field))}
      {!isChoice && !isChip && !isConfirm && !isAddressGroup && formStep.fields.map((field) => renderTextField(field))}

      {needsSubmitButton && !disabled && (
        <Button className="mt-4 w-full" onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? (
            <Loader2 data-icon="inline-start" className="animate-spin" />
          ) : isConfirm ? (
            <PartyPopper data-icon="inline-start" />
          ) : (
            <ArrowRight data-icon="inline-start" />
          )}
          {isConfirm ? "Complete Registration" : "Continue"}
        </Button>
      )}

      {disabled && (
        <p className="mt-3 flex items-center gap-1 text-xs text-emerald-600">
          <CheckCircle2 className="size-3.5" />
          Completed
        </p>
      )}
    </div>
  );
};

export default InlineRegistrationForm;
