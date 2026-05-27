"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  errorMsg: string;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    errorMsg: "",
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMsg: error.message };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="w-full h-full min-h-[300px] flex flex-col items-center justify-center soft-container bg-white/50">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mb-4"></div>
            <h2 className="text-xl font-semibold text-gray-700">
              Stream Reconnecting...
            </h2>
            <p className="text-sm text-gray-500 mt-2">{this.state.errorMsg}</p>
            <button
              className="mt-6 soft-button"
              onClick={() => this.setState({ hasError: false, errorMsg: "" })}
            >
              Retry
            </button>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
