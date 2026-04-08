import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: "https://6f095d57277d81ad5bf0825b70019383@o4511151704440832.ingest.us.sentry.io/4511151753723904",
  environment: process.env.NODE_ENV || "development",
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.5 : 1.0,
});
