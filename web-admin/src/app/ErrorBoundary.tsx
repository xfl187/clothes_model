import { Component } from 'react';
import type { ErrorInfo, PropsWithChildren, ReactNode } from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Web Admin render failure', {
      error: error.name,
      componentStack: info.componentStack,
    });
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main className="fatal-error" role="alert">
          <p className="eyebrow">界面无法继续</p>
          <h1>管理端发生了安全停止。</h1>
          <p>请刷新页面；若问题持续存在，请检查浏览器控制台中的非敏感诊断。</p>
        </main>
      );
    }
    return this.props.children;
  }
}
