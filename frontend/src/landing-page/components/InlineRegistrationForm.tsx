/**
 * InlineRegistrationForm — renders interactive form steps INSIDE chat bubbles.
 *
 * Receives a `formStep` payload (from the backend's form_step SSE event) and
 * renders the appropriate form widget (choice cards, text field, chip select,
 * address group, confirm summary, etc.). On submit it calls the registration
 * step API and fires `onFormResult` so the parent chat component can push the
 * next form_step or done message.
 */
import React, { useState, useCallback, useRef, useEffect } from "react";
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  InputAdornment,
  LinearProgress,
  Stack,
  TextField,
  Typography,
  Collapse,
  Alert,
} from "@mui/material";
import StoreIcon from "@mui/icons-material/Store";
import PersonIcon from "@mui/icons-material/Person";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import CelebrationIcon from "@mui/icons-material/Celebration";

// ---------- Types ----------

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
  disabled?: boolean; // true when this step is already completed
  onFormResult: (result: FormStepData | FormDoneData) => void;
}

// ---------- Helpers ----------

const ICON_MAP: Record<string, React.ReactNode> = {
  store: <StoreIcon sx={{ fontSize: 32 }} />,
  person: <PersonIcon sx={{ fontSize: 32 }} />,
};

function getPasswordStrength(pw: string): {
  label: string;
  color: string;
  value: number;
} {
  if (pw.length < 8) return { label: "Too short", color: "#f44336", value: 20 };
  let score = 0;
  if (/[a-z]/.test(pw)) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  if (pw.length >= 12) score++;
  if (score <= 2) return { label: "Weak", color: "#ff9800", value: 40 };
  if (score <= 3) return { label: "Good", color: "#2196f3", value: 70 };
  return { label: "Strong", color: "#4caf50", value: 100 };
}

// ---------- Component ----------

const InlineRegistrationForm: React.FC<InlineRegistrationFormProps> = ({
  formStep,
  sessionId,
  theme,
  isDarkMode,
  disabled = false,
  onFormResult,
}) => {
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>(
    formStep.errors || {},
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showCustomChip, setShowCustomChip] = useState(false);
  const [asyncStatus, setAsyncStatus] = useState<
    Record<string, { checking: boolean; available?: boolean; message?: string }>
  >({});
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>(
    {},
  );

  // Initialize errors from formStep if they arrive late
  useEffect(() => {
    if (formStep.errors) setErrors(formStep.errors);
  }, [formStep.errors]);

  // --- Real-time async validation (debounced) ---
  const asyncValidate = useCallback(
    (field: string, value: string, url: string) => {
      if (debounceTimers.current[field])
        clearTimeout(debounceTimers.current[field]);
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
            [field]: {
              checking: false,
              available: data.available,
              message: data.message,
            },
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
    },
    [],
  );

  const handleChange = (name: string, value: string, field?: FormField) => {
    setValues((prev) => ({ ...prev, [name]: value }));
    // Clear local error
    setErrors((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
    // Fire async validation if configured
    if (field?.validate_async && value.length >= (field.min_length || 2)) {
      asyncValidate(name, value, field.validate_async);
    }
  };

  const handleSubmit = async () => {
    if (disabled || isSubmitting) return;

    // Client-side required check
    const clientErrors: Record<string, string> = {};
    for (const field of formStep.fields) {
      if (field.required && !values[field.name]?.trim()) {
        clientErrors[field.name] = `${field.label} is required`;
      }
      if (
        field.min_length &&
        (values[field.name]?.length || 0) < field.min_length
      ) {
        clientErrors[field.name] =
          `Must be at least ${field.min_length} characters`;
      }
    }
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      return;
    }

    // Check async validation hasn't flagged anything
    const asyncBlocked = Object.entries(asyncStatus).some(
      ([, s]) => s.available === false,
    );
    if (asyncBlocked) return;

    setIsSubmitting(true);
    try {
      const res = await fetch("/api/agent/registration/step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, data: values }),
      });
      const result = await res.json();

      if (result.errors) {
        setErrors(result.errors);
        setIsSubmitting(false);
        return;
      }

      onFormResult(result);
    } catch (err) {
      console.error("Registration step failed:", err);
      setErrors({ _general: "Something went wrong. Please try again." });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Auto-submit on choice selection
  const handleChoiceSelect = async (field: FormField, value: string) => {
    if (disabled || isSubmitting) return;
    setValues({ [field.name]: value });
    setIsSubmitting(true);
    try {
      const res = await fetch("/api/agent/registration/step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          data: { [field.name]: value },
        }),
      });
      const result = await res.json();
      if (result.errors) {
        setErrors(result.errors);
      } else {
        onFormResult(result);
      }
    } catch {
      setErrors({ _general: "Something went wrong." });
    } finally {
      setIsSubmitting(false);
    }
  };

  // ---- Renderers per field type ----

  const renderChoiceField = (field: FormField) => (
    <Stack spacing={1.5} sx={{ mt: 1 }}>
      {field.options?.map((opt) => (
        <Card
          key={opt.value}
          sx={{
            borderRadius: "16px",
            border: `2px solid ${values[field.name] === opt.value ? theme.accent : theme.cardBorder}`,
            bgcolor:
              values[field.name] === opt.value
                ? isDarkMode
                  ? "rgba(255,255,255,0.05)"
                  : "rgba(0,0,0,0.02)"
                : "transparent",
            transition: "all 0.2s ease",
            cursor: disabled ? "default" : "pointer",
            opacity: disabled ? 0.7 : 1,
            "&:hover": disabled
              ? {}
              : {
                  borderColor: theme.accent,
                  transform: "translateY(-2px)",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                },
          }}
        >
          <CardActionArea
            onClick={() => handleChoiceSelect(field, opt.value)}
            disabled={disabled || isSubmitting}
            sx={{
              p: 2,
              display: "flex",
              alignItems: "center",
              gap: 2,
              justifyContent: "flex-start",
            }}
          >
            {opt.icon && ICON_MAP[opt.icon] && (
              <Box sx={{ color: theme.accent }}>{ICON_MAP[opt.icon]}</Box>
            )}
            <Box>
              <Typography
                variant="subtitle1"
                sx={{ fontWeight: 600, color: theme.text }}
              >
                {opt.label}
              </Typography>
              {opt.description && (
                <Typography
                  variant="body2"
                  sx={{ color: theme.textSecondary, mt: 0.25 }}
                >
                  {opt.description}
                </Typography>
              )}
            </Box>
          </CardActionArea>
        </Card>
      ))}
    </Stack>
  );

  const renderTextField = (field: FormField) => {
    const isPassword = field.type === "password";
    const password = isPassword ? values[field.name] || "" : "";
    const strength = isPassword ? getPasswordStrength(password) : null;
    const status = asyncStatus[field.name];

    return (
      <Box sx={{ mt: 1 }}>
        <TextField
          fullWidth
          type={
            isPassword && !showPassword
              ? "password"
              : field.type === "email"
                ? "email"
                : field.type === "tel"
                  ? "tel"
                  : "text"
          }
          label={field.label}
          placeholder={field.placeholder}
          value={values[field.name] || ""}
          onChange={(e) => handleChange(field.name, e.target.value, field)}
          disabled={disabled || isSubmitting}
          error={!!errors[field.name]}
          helperText={errors[field.name]}
          inputProps={{ maxLength: field.max_length || 200 }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                {isPassword && (
                  <IconButton
                    size="small"
                    onClick={() => setShowPassword(!showPassword)}
                    edge="end"
                  >
                    {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                )}
                {status?.checking && <CircularProgress size={18} />}
                {status && !status.checking && status.available === true && (
                  <CheckCircleIcon sx={{ color: "#4caf50", fontSize: 20 }} />
                )}
                {status && !status.checking && status.available === false && (
                  <ErrorIcon sx={{ color: "#f44336", fontSize: 20 }} />
                )}
              </InputAdornment>
            ),
            sx: {
              borderRadius: "14px",
              bgcolor: isDarkMode
                ? "rgba(255,255,255,0.04)"
                : "rgba(0,0,0,0.02)",
            },
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              "& fieldset": { borderColor: theme.cardBorder },
              "&:hover fieldset": { borderColor: theme.accent },
              "&.Mui-focused fieldset": { borderColor: theme.accent },
            },
            "& .MuiInputLabel-root.Mui-focused": { color: theme.accent },
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        {isPassword &&
          field.show_strength &&
          password.length > 0 &&
          strength && (
            <Box sx={{ mt: 1 }}>
              <LinearProgress
                variant="determinate"
                value={strength.value}
                sx={{
                  height: 4,
                  borderRadius: 2,
                  bgcolor: isDarkMode
                    ? "rgba(255,255,255,0.1)"
                    : "rgba(0,0,0,0.08)",
                  "& .MuiLinearProgress-bar": {
                    bgcolor: strength.color,
                    borderRadius: 2,
                  },
                }}
              />
              <Typography
                variant="caption"
                sx={{ color: strength.color, mt: 0.5 }}
              >
                {strength.label}
              </Typography>
            </Box>
          )}
        {status &&
          !status.checking &&
          status.message &&
          !errors[field.name] && (
            <Typography
              variant="caption"
              sx={{
                color: status.available ? "#4caf50" : "#f44336",
                mt: 0.5,
                display: "block",
              }}
            >
              {status.message}
            </Typography>
          )}
      </Box>
    );
  };

  const renderChipSelect = (field: FormField) => {
    const selected = values[field.name] || "";

    return (
      <Box sx={{ mt: 1 }}>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 1 }}>
          {field.options?.map((opt) => (
            <Chip
              key={opt.value}
              label={opt.label}
              onClick={() => {
                if (!disabled && !isSubmitting) {
                  handleChange(field.name, opt.value);
                  setShowCustomChip(false);
                }
              }}
              sx={{
                borderRadius: "12px",
                fontWeight: selected === opt.value ? 600 : 400,
                bgcolor: selected === opt.value ? theme.accent : "transparent",
                color:
                  selected === opt.value
                    ? isDarkMode
                      ? "#000"
                      : "#fff"
                    : theme.text,
                border: `1px solid ${selected === opt.value ? theme.accent : theme.cardBorder}`,
                "&:hover": {
                  bgcolor:
                    selected === opt.value
                      ? theme.accent
                      : isDarkMode
                        ? "rgba(255,255,255,0.08)"
                        : "rgba(0,0,0,0.04)",
                },
                transition: "all 0.15s ease",
                cursor: disabled ? "default" : "pointer",
              }}
            />
          ))}
          {field.allow_custom && (
            <Chip
              label="Other..."
              variant="outlined"
              onClick={() => !disabled && setShowCustomChip(true)}
              sx={{
                borderRadius: "12px",
                borderStyle: "dashed",
                color: theme.textSecondary,
              }}
            />
          )}
        </Box>
        <Collapse in={showCustomChip}>
          <TextField
            fullWidth
            size="small"
            placeholder={field.custom_placeholder || "Enter custom type"}
            value={values[field.name] || ""}
            onChange={(e) => handleChange(field.name, e.target.value)}
            disabled={disabled || isSubmitting}
            sx={{ mt: 1, "& .MuiOutlinedInput-root": { borderRadius: "12px" } }}
          />
        </Collapse>
        {errors[field.name] && (
          <Typography
            variant="caption"
            color="error"
            sx={{ mt: 0.5, display: "block" }}
          >
            {errors[field.name]}
          </Typography>
        )}
      </Box>
    );
  };

  const renderAddressFields = (fields: FormField[]) => (
    <Stack spacing={1.5} sx={{ mt: 1 }}>
      {fields.map((field) => (
        <TextField
          key={field.name}
          fullWidth
          size="small"
          label={field.label}
          placeholder={field.placeholder}
          value={values[field.name] || ""}
          onChange={(e) => handleChange(field.name, e.target.value)}
          disabled={disabled || isSubmitting}
          error={!!errors[field.name]}
          helperText={errors[field.name]}
          InputProps={{
            sx: {
              borderRadius: "12px",
              bgcolor: isDarkMode
                ? "rgba(255,255,255,0.04)"
                : "rgba(0,0,0,0.02)",
            },
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              "& fieldset": { borderColor: theme.cardBorder },
              "&:hover fieldset": { borderColor: theme.accent },
              "&.Mui-focused fieldset": { borderColor: theme.accent },
            },
          }}
        />
      ))}
    </Stack>
  );

  const renderConfirm = () => {
    const summary = formStep.summary || {};
    return (
      <Box sx={{ mt: 1 }}>
        <Card
          sx={{
            borderRadius: "16px",
            border: `1px solid ${theme.cardBorder}`,
            bgcolor: isDarkMode ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.01)",
          }}
        >
          <CardContent>
            <Stack spacing={1}>
              {Object.entries(summary).map(([key, val]) => (
                <Box
                  key={key}
                  sx={{ display: "flex", justifyContent: "space-between" }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      color: theme.textSecondary,
                      textTransform: "capitalize",
                    }}
                  >
                    {key.replace(/_/g, " ")}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600, color: theme.text }}
                  >
                    {val}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Box>
    );
  };

  // ---- Main Render ----

  // Determine what to render based on fields
  const field0 = formStep.fields[0];
  const isChoice = field0?.type === "choice";
  const isChip = field0?.type === "chip_select";
  const isConfirm = field0?.type === "confirm";
  const isAddressGroup = formStep.step === "shop_address";
  const needsSubmitButton = !isChoice; // choices auto-submit

  return (
    <Box
      sx={{
        width: "100%",
        mt: 0.5,
        animation: disabled ? "none" : "fadeSlideIn 0.3s ease",
        "@keyframes fadeSlideIn": {
          from: { opacity: 0, transform: "translateY(8px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
      }}
    >
      {/* Progress bar */}
      <Box sx={{ mb: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
        <LinearProgress
          variant="determinate"
          value={formStep.progress}
          sx={{
            flex: 1,
            height: 6,
            borderRadius: 3,
            bgcolor: isDarkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
            "& .MuiLinearProgress-bar": {
              bgcolor: theme.accent,
              borderRadius: 3,
            },
          }}
        />
        <Typography
          variant="caption"
          sx={{ color: theme.textSecondary, whiteSpace: "nowrap" }}
        >
          {formStep.step_number}/{formStep.total_steps}
        </Typography>
      </Box>

      {/* General errors */}
      <Collapse in={!!errors._general}>
        <Alert
          severity="error"
          sx={{ mb: 1, borderRadius: "12px" }}
          onClose={() =>
            setErrors((prev) => {
              const n = { ...prev };
              delete n._general;
              return n;
            })
          }
        >
          {errors._general}
        </Alert>
      </Collapse>

      {/* Field rendering */}
      {isChoice && renderChoiceField(field0)}
      {isChip && renderChipSelect(field0)}
      {isConfirm && renderConfirm()}
      {isAddressGroup && renderAddressFields(formStep.fields)}
      {!isChoice &&
        !isChip &&
        !isConfirm &&
        !isAddressGroup &&
        formStep.fields.map((f) => (
          <React.Fragment key={f.name}>{renderTextField(f)}</React.Fragment>
        ))}

      {/* Submit button */}
      {needsSubmitButton && !disabled && (
        <Button
          fullWidth
          variant="contained"
          onClick={handleSubmit}
          disabled={isSubmitting}
          endIcon={
            isSubmitting ? (
              <CircularProgress size={18} color="inherit" />
            ) : isConfirm ? (
              <CelebrationIcon />
            ) : (
              <ArrowForwardIcon />
            )
          }
          sx={{
            mt: 2,
            py: 1.25,
            borderRadius: "14px",
            fontWeight: 700,
            fontSize: "0.95rem",
            textTransform: "none",
            bgcolor: theme.accent,
            color: isDarkMode ? "#000" : "#fff",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            "&:hover": {
              bgcolor: theme.accent,
              filter: "brightness(1.1)",
              boxShadow: "0 6px 16px rgba(0,0,0,0.2)",
            },
          }}
        >
          {isConfirm ? "Complete Registration" : "Continue"}
        </Button>
      )}

      {disabled && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mt: 1 }}>
          <CheckCircleIcon sx={{ fontSize: 16, color: "#4caf50" }} />
          <Typography variant="caption" sx={{ color: "#4caf50" }}>
            Completed
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default InlineRegistrationForm;
