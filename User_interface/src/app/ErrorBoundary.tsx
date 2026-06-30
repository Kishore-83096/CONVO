import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  public constructor(props: ErrorBoundaryProps) {
    super(props);

    this.state = {
      hasError: false,
    };
  }

  public static getDerivedStateFromError(
    error: Error,
  ): ErrorBoundaryState {
    return {
      hasError: true,
      error,
    };
  }

  public componentDidCatch(
    error: Error,
    errorInfo: ErrorInfo,
  ): void {
    console.error("Application Error:", error);
    console.error(errorInfo);
  }

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            padding: 24,
            fontFamily: "Inter, sans-serif",
          }}
        >
          <div
            style={{
              maxWidth: 480,
              textAlign: "center",
            }}
          >
            <h1>Something went wrong.</h1>

            <p>
              An unexpected error occurred while rendering the
              application.
            </p>

            <button
              onClick={() => window.location.reload()}
            >
              Reload Application
            </button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}