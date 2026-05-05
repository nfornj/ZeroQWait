import React from "react";
import { Button } from "./ui/button";

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
        <div className="flex min-h-screen items-center justify-center p-6">
          <div className="flex w-full max-w-xl flex-col gap-4">
            <h2 className="text-xl font-semibold text-foreground">Dashboard failed to load</h2>
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
              {this.state.errorMessage || "Unexpected runtime error"}
            </div>
            <div className="flex gap-3">
              <Button onClick={this.handleReload}>Reload</Button>
              <Button variant="outline" onClick={this.handleGoToLogin}>
                Go to Login
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default AppErrorBoundary;
