import * as Sentry from "@sentry/react";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN || "",
  environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "development",
  tracesSampleRate: import.meta.env.VITE_SENTRY_ENVIRONMENT === "production" ? 0.5 : 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  beforeSend(event) {
    if (import.meta.env.VITE_SENTRY_ENVIRONMENT !== "production") {
      console.log("[Sentry]", event);
      return null;
    }
    return event;
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
