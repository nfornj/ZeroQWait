import React from "react";
import { Alert, Box, Button, Stack, Typography } from "@mui/material";

interface AppErrorBoundaryState {
  hasError: boolean;
  errorMessage: string;
}

class AppErrorBoundary extends React.Component<
  { children: React.ReactNode },
  AppErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error?.message || "Unexpected application error",
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[AppErrorBoundary] Render crash:", error, errorInfo);
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoToLogin = () => {
    window.location.href = "/login";
  };

  render() {
    if (this.state.hasError) {
      return (
        <Box
          sx={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            p: 3,
          }}
        >
          <Stack spacing={2} sx={{ maxWidth: 640, width: "100%" }}>
            <Typography variant="h5">Dashboard failed to load</Typography>
            <Alert severity="error">
              {this.state.errorMessage || "Unexpected runtime error"}
            </Alert>
            <Stack direction="row" spacing={1.5}>
              <Button variant="contained" onClick={this.handleReload}>
                Reload
              </Button>
              <Button variant="outlined" onClick={this.handleGoToLogin}>
                Go to Login
              </Button>
            </Stack>
          </Stack>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default AppErrorBoundary;