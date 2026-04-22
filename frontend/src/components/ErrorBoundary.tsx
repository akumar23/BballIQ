import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  /**
   * Children to render. If any child throws during render, the fallback UI
   * will be rendered in place of this subtree.
   */
  children: ReactNode
  /**
   * Optional callback invoked when the user clicks "Retry" in the fallback UI.
   * If omitted, the page will reload instead.
   */
  onReset?: () => void
  /**
   * When `compact` is true, renders an inline fallback suitable for a route
   * panel (e.g., inside `<main>`). When false (default), renders a full-height
   * fallback suitable for wrapping the whole application shell.
   */
  compact?: boolean
}

interface ErrorBoundaryState {
  error: Error | null
}

/**
 * Catches render-phase errors in descendant components and renders a friendly
 * fallback UI instead of crashing the entire React tree.
 *
 * Use at the app root to guard against total SPA crashes, and again around
 * each lazy-loaded route to isolate failures to a single page.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log for local observability. External reporting is intentionally out of scope.
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] Render error caught:', error, info.componentStack)
  }

  handleReset = (): void => {
    const { onReset } = this.props
    this.setState({ error: null })
    if (onReset) {
      onReset()
    } else if (typeof window !== 'undefined') {
      window.location.reload()
    }
  }

  render(): ReactNode {
    const { error } = this.state
    const { children, compact } = this.props

    if (!error) {
      return children
    }

    if (compact) {
      return (
        <div
          role="alert"
          className="flex flex-col items-center justify-center text-center py-16 px-6 bg-white border border-gray-200 rounded-lg shadow-sm"
        >
          <h2 className="text-lg font-bold text-gray-900 mb-2">Something went wrong on this page.</h2>
          <p className="text-sm text-gray-600 mb-1">
            Sorry about that — we hit an unexpected error while rendering this view.
          </p>
          <p className="text-xs text-red-600 font-mono mb-5 break-all max-w-xl">{error.message}</p>
          <button
            type="button"
            onClick={this.handleReset}
            className="px-4 py-2 text-xs uppercase tracking-[1.5px] bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      )
    }

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div
          role="alert"
          className="max-w-lg w-full bg-white border border-gray-200 rounded-lg shadow-sm p-8 text-center"
        >
          <h1 className="text-2xl font-bold text-gray-900 mb-3">Something broke.</h1>
          <p className="text-sm text-gray-600 mb-1">
            We ran into an unexpected error. Sorry for the inconvenience.
          </p>
          <p className="text-xs text-red-600 font-mono mb-6 break-all">{error.message}</p>
          <button
            type="button"
            onClick={this.handleReset}
            className="px-5 py-2 text-xs uppercase tracking-[1.5px] bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }
}
