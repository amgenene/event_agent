import "./App.css";
import * as Sentry from "@sentry/react";
import MinimalRecorder from "./MinimalRecorder";

function App() {
  return (
    <Sentry.ErrorBoundary
      fallback={({ error, eventId }) => (
        <div style={{
          padding: 24,
          backgroundColor: "#1c1c1c",
          color: "#fff",
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
        }}>
          <div style={{ fontSize: 48 }}>⚠️</div>
          <h2 style={{ margin: 0 }}>Something went wrong</h2>
          <p style={{ color: "#888", margin: 0, textAlign: "center", maxWidth: 400 }}>
            An unexpected error occurred. The issue has been reported.
          </p>
          {import.meta.env.VITE_SENTRY_ENVIRONMENT !== "production" && (
            <pre style={{
              background: "#2a2a2a",
              padding: 12,
              borderRadius: 8,
              fontSize: 12,
              maxWidth: 500,
              overflow: "auto",
              color: "#ef4444",
            }}>
              {error?.message || "Unknown error"}
            </pre>
          )}
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: "8px 20px",
              backgroundColor: "#6366f1",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            Reload
          </button>
        </div>
      )}
    >
      <main className="container" style={{
        background: "#0a0a0f",
        minHeight: "100vh",
        padding: 0
      }}>
        <MinimalRecorder />
      </main>
    </Sentry.ErrorBoundary>
  );
}

export default App;
