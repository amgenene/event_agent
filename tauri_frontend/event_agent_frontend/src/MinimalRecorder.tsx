import React, { useEffect, useRef, useState, useCallback } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";

interface Event {
  id: string;
  title: string;
  location: string;
  date: string;
  time: string;
  description: string;
  url: string;
  price: string;
  category?: string;
}

interface SearchResponse {
  success: boolean;
  events: Event[];
  message: string;
}

type RecorderState = "idle" | "recording" | "processing" | "error" | "transcribed" | "results";

export default function MinimalRecorder() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);

  // Volume level from backend (0.0 to 1.0)
  const volumeRef = useRef<number>(0);
  const targetVolumeRef = useRef<number>(0);

  const [state, setState] = useState<RecorderState>("idle");
  const [statusMessage, setStatusMessage] = useState<string>("Press ⌥E to start");
  const [transcript, setTranscript] = useState<string>("");
  const [events, setEvents] = useState<Event[]>([]);
  const [savedLocation, setSavedLocation] = useState<{ location: string; country?: string } | null>(null);
  const [locationPromptOpen, setLocationPromptOpen] = useState<boolean>(false);
  const [locationInput, setLocationInput] = useState<string>("");
  const [countryInput, setCountryInput] = useState<string>("");
  const pendingSearchRef = useRef<boolean>(false);
  const stateRef = useRef<RecorderState>("idle");
  const locationPromptOpenRef = useRef<boolean>(false);
  const noiseFloorRef = useRef<number>(0);
  const lastAudioAtRef = useRef<number>(0);
  const handlersRef = useRef<{
    start: () => void;
    stop: () => void;
    cancel: () => void;
    search: () => void;
    saveLocation: () => void;
  } | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    locationPromptOpenRef.current = locationPromptOpen;
  }, [locationPromptOpen]);

  const loadSavedLocation = useCallback(async () => {
    try {
      const result = await invoke<{ location: string; country?: string } | null>("get_saved_location");
      if (result?.location) {
        console.log("Loaded saved location:", result);
        setSavedLocation(result);
        setLocationInput(result.location);
        setCountryInput(result.country || "");
      }
    } catch (e) {
      console.error("Failed to load saved location:", e);
    }
  }, []);

  const ensureLocation = useCallback(async () => {
    if (savedLocation?.location) {
      console.log("Using cached location:", savedLocation);
      return savedLocation;
    }

    try {
      const result = await invoke<{ location: string; country?: string } | null>("get_saved_location");
      if (result?.location) {
        console.log("Loaded location from disk:", result);
        setSavedLocation(result);
        setLocationInput(result.location);
        setCountryInput(result.country || "");
        return result;
      }
    } catch (e) {
      console.error("Failed to load saved location:", e);
    }

    console.warn("No saved location found; prompting user.");
    setLocationPromptOpen(true);
    return null;
  }, [savedLocation]);

  // Draw the waveform visualization
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d")!;
    const width = canvas.width;
    const height = canvas.height;
    const centerY = height / 2;

    // Clear and fill background
    ctx.fillStyle = "#1c1c1c";
    ctx.fillRect(0, 0, width, height);

    if (state === "error") {
      drawDottedLine(ctx, width, centerY);
    } else if (state === "recording") {
      // Smoothly interpolate volume
      volumeRef.current += (targetVolumeRef.current - volumeRef.current) * 0.2;

      const volume = volumeRef.current;

      if (volume < 0.01) {
        drawDottedLine(ctx, width, centerY);
      } else {
        // Draw real waveform based on volume
        drawVolumeWaveform(ctx, width, height, centerY, volume);
      }
    } else {
      drawDottedLine(ctx, width, centerY);
    }

    if (state === "recording") {
      animationRef.current = requestAnimationFrame(draw);
    }
  }, [state]);

  // Draw a flat dotted line
  function drawDottedLine(ctx: CanvasRenderingContext2D, width: number, centerY: number) {
    const dotSpacing = 8;
    const dotRadius = 1.5;

    ctx.fillStyle = "#666";
    for (let x = dotSpacing; x < width - dotSpacing; x += dotSpacing) {
      ctx.beginPath();
      ctx.arc(x, centerY, dotRadius, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Draw waveform modulated by volume
  function drawVolumeWaveform(
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    centerY: number,
    volume: number
  ) {
    const dotSpacing = 8;
    const dotRadius = 1.5;
    // Scale amplitude by volume, boosting it a bit to be visible
    const amplitude = Math.min(height * 0.4, (volume * 500) * (height * 0.4));

    // Time factor for movement
    const time = Date.now() / 100;

    ctx.fillStyle = "#aaa";

    const numDots = Math.floor((width - dotSpacing * 2) / dotSpacing);

    for (let i = 0; i < numDots; i++) {
      const x = dotSpacing + i * dotSpacing;

      // Create a nice organic wave shape
      // We use multiple sines to make it look less robotic
      const wave = Math.sin(x * 0.05 + time) * Math.sin(x * 0.1 + time * 1.5);

      const y = centerY + wave * amplitude;

      ctx.beginPath();
      ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Start recording using native Tauri plugin + Backend Monitor
  const start = useCallback(async () => {
    if (state === "recording" || state === "processing") return;

    setState("recording");
    setStatusMessage("🎙️ Recording... (⌥E to stop)");
    setEvents([]);
    setTranscript("");
    volumeRef.current = 0;
    targetVolumeRef.current = 0;
    noiseFloorRef.current = 0;

    try {
      await invoke("start_recording");
      console.log("Recording started");
    } catch (e) {
      console.error("Failed to start recording:", e);
      setState("error");
      setStatusMessage("❌ Failed to start recording");
    }
  }, [state, draw]);

  // Stop recording and process
  const stop = useCallback(async () => {
    if (state !== "recording") return;

    setState("processing");
    setStatusMessage("⏳ Processing audio...");

    try {
      const filePath = await invoke<string>("stop_recording");
      console.log("Recording stopped, file at:", filePath);

      if (filePath) {
        setStatusMessage("📝 Transcribing...");
        await transcribeRecording(filePath);
      } else {
        setState("error");
        setStatusMessage("❌ No recording file received");
      }
    } catch (e) {
      console.error("Failed to stop recording:", e);
      setState("error");
      setStatusMessage("❌ Failed to stop recording: " + String(e));
    }
  }, [state]);

  // Transcribe the recorded audio file
  async function transcribeRecording(filePath: string) {
    try {
      const response = await fetch(`http://127.0.0.1:8000/transcribe-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Transcription failed:", errorText);
        setState("error");
        setStatusMessage("❌ Transcription failed: " + errorText);
        return;
      }

      const data = await response.json();
      const text = data.text || "";
      setTranscript(text);

      if (text.trim()) {
        setState("transcribed");
        setStatusMessage("✅ Ready to search");
      } else {
        setState("error");
        setStatusMessage("❌ No speech detected");
      }
    } catch (e) {
      console.error("Transcription error:", e);
      setState("error");
      setStatusMessage("❌ Could not connect to server");
    }
  }

  // Search for events after transcription
  const searchWithTranscript = useCallback(async () => {
    if (!transcript.trim()) return;

    setState("processing");
    setStatusMessage("🔍 Searching for events...");

    try {
      const location = await ensureLocation();
      if (!location) {
        setState("transcribed");
        setStatusMessage("📍 Tell us where you are");
        pendingSearchRef.current = true;
        return;
      }

      console.log("Searching with location:", location);

      const res = await fetch("http://127.0.0.1:8000/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: transcript,
          preferences: {
            home_city: location.location,
            country: location.country,
            radius_miles: 10,
            max_transit_minutes: 45,
            time_window_days: 7,
          },
        }),
      });

      if (!res.ok) {
        setState("error");
        setStatusMessage("❌ Search failed");
        return;
      }

      const data: SearchResponse = await res.json();
      setEvents(data.events);
      if (data.events.length > 0) {
        setState("results");
        setStatusMessage(`✅ Found ${data.events.length} event(s)`);
      } else {
        setState("transcribed");
        setStatusMessage("No events found for your query");
      }
    } catch (e) {
      console.error(e);
      setState("error");
      setStatusMessage("❌ Could not connect to server");
    }
  }, [transcript, ensureLocation]);

  const saveLocation = useCallback(async () => {
    const location = locationInput.trim();
    if (!location) {
      return;
    }

    const payload = {
      location,
      country: countryInput.trim() || undefined,
    };

    try {
      console.log("Saving location:", payload);
      await invoke("set_saved_location", { location: payload });
      setSavedLocation(payload);
      setLocationPromptOpen(false);

      if (pendingSearchRef.current && transcript.trim()) {
        pendingSearchRef.current = false;
        searchWithTranscript();
      }
    } catch (e) {
      console.error("Failed to save location:", e);
    }
  }, [countryInput, locationInput, searchWithTranscript, transcript]);

  // Cancel and close window
  const cancel = useCallback(async () => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    // Stop backend monitor
    if (state === "recording") {
      try {
        await invoke("cancel_recording");
      } catch (e) {
        console.error("Failed to stop recording on cancel:", e);
      }
    }

    try {
      const window = getCurrentWindow();
      await window.hide();
    } catch (e) {
      console.error("Failed to hide window:", e);
    }
  }, [state]);

  useEffect(() => {
    handlersRef.current = {
      start,
      stop,
      cancel,
      search: searchWithTranscript,
      saveLocation,
    };
  }, [start, stop, cancel, searchWithTranscript, saveLocation]);

  // Reset to idle
  const reset = useCallback(() => {
    setState("idle");
    setStatusMessage("Press ⌥E to start");
    setTranscript("");
    setEvents([]);
  }, []);

  // Listen for audio levels from backend
  useEffect(() => {
    const unlisten = listen("audio-level", (event: any) => {
      const payload = event.payload as { rms: number; peak: number };
      if (stateRef.current !== "recording") {
        return;
      }

      const rms = payload.rms || 0;
      lastAudioAtRef.current = Date.now();

      if (noiseFloorRef.current === 0) {
        noiseFloorRef.current = rms;
      } else if (rms < noiseFloorRef.current * 1.5) {
        // Adapt noise floor only when we're not significantly above it
        noiseFloorRef.current = noiseFloorRef.current * 0.98 + rms * 0.02;
      }

      const gate = noiseFloorRef.current * 1.3 + 0.0025;
      const signal = Math.max(0, rms - gate);
      targetVolumeRef.current = Math.min(1, signal * 4.0);
    });

    return () => {
      unlisten.then(fn => fn());
    }
  }, []);

  // Listen for start-recording shortcut events
  useEffect(() => {
    const unlisten = listen("start-recording", () => {
      if (state === "recording") {
        stop();
      } else if (state !== "processing") {
        start();
      }
    });

    return () => {
      unlisten.then((fn) => fn());
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [state, start, stop]);

  // Ensure animation loop starts when recording state is active
  useEffect(() => {
    if (state === "recording") {
      animationRef.current = requestAnimationFrame(draw);
      return () => {
        if (animationRef.current) {
          cancelAnimationFrame(animationRef.current);
        }
      };
    }
  }, [state, draw]);

  // Initial draw on mount
  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#1c1c1c";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      drawDottedLine(ctx, canvas.width, canvas.height / 2);
    }
  }, []);

  useEffect(() => {
    loadSavedLocation();
  }, [loadSavedLocation]);

  // Keyboard shortcuts - Alt+E for start/stop
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const handlers = handlersRef.current;
      if (!handlers) {
        return;
      }

      if (locationPromptOpenRef.current) {
        if (e.key === "Enter") {
          e.preventDefault();
          handlers.saveLocation();
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          setLocationPromptOpen(false);
          return;
        }
        return;
      }

      const isAltE = (e.key === "e" || e.key === "E") && (e.altKey || e.metaKey);

      if (isAltE) {
        e.preventDefault();
        if (stateRef.current === "recording") {
          handlers.stop();
        } else if (stateRef.current === "idle" || stateRef.current === "error") {
          handlers.start();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        handlers.cancel();
      } else if (e.key === "Enter" && stateRef.current === "transcribed") {
        e.preventDefault();
        handlers.search();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const locationOverlay = locationPromptOpen ? (
    <div style={styles.locationOverlay}>
      <div style={styles.locationModal}>
        <div style={styles.locationTitle}>Where are you?</div>
        <div style={styles.locationSubtitle}>We only store this locally on your device.</div>
        <input
          style={styles.locationInput}
          placeholder="City, State/Region"
          value={locationInput}
          onChange={(e) => setLocationInput(e.target.value)}
          onKeyDown={(e) => e.stopPropagation()}
        />
        <input
          style={styles.locationInput}
          placeholder="Country code (optional, e.g. US)"
          value={countryInput}
          onChange={(e) => setCountryInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.stopPropagation()}
        />
        <div style={styles.locationActions}>
          <button style={styles.locationSaveButton} onClick={saveLocation}>
            Save Location
          </button>
          <button
            style={styles.locationCancelButton}
            onClick={() => setLocationPromptOpen(false)}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  ) : null;

  // Show transcription view - this is the key view after recording
  if (state === "transcribed" || (state === "error" && transcript)) {
    return (
      <div style={styles.container}>
        {locationOverlay}
        <div style={styles.transcriptContainer}>
          <div style={styles.transcriptLabel}>You said:</div>
          <div style={styles.transcriptBox}>
            <div style={styles.transcriptText}>{transcript || "(No speech detected)"}</div>
          </div>
          <div style={styles.searchPrompt}>Search for events?</div>
        </div>
        <div style={styles.toolbar}>
          <div style={styles.toolbarLeft}>
            <TriangleLogo />
          </div>
          <div style={styles.toolbarCenter}>
            <button style={styles.searchButton} onClick={searchWithTranscript}>
              Search
              <span style={styles.keyIndicator}>Enter</span>
            </button>
            <button style={styles.retryButton} onClick={reset}>
              Retry
            </button>
          </div>
          <div style={styles.toolbarRight}>
            <button style={styles.cancelButton} onClick={cancel}>
              Cancel
              <span style={styles.keyHint}>esc</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Show results view
  if (state === "results" && events.length > 0) {
    return (
      <div style={styles.container}>
        {locationOverlay}
        <div style={styles.resultsContainer}>
          <div style={styles.queryBox}>
            <span style={styles.queryLabel}>Query:</span> "{transcript}"
          </div>
          <h3 style={styles.resultsTitle}>📅 Found {events.length} event(s)</h3>
          <div style={styles.eventsList}>
            {events.map((event) => (
              <div key={event.id} style={styles.eventCard}>
                <h4 style={styles.eventTitle}>{event.title}</h4>
                <p style={styles.eventDetail}>📍 {event.location}</p>
                <p style={styles.eventDetail}>
                  🗓️ {event.date} at {event.time}
                </p>
                <p style={styles.eventDetail}>💰 {event.price}</p>
                {event.url && (
                  <a
                    href={event.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.eventLink}
                  >
                    View Details →
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
        <div style={styles.toolbar}>
          <div style={styles.toolbarLeft}>
            <TriangleLogo />
          </div>
          <div style={styles.toolbarCenter}>
            <button style={styles.actionButton} onClick={reset}>
              New Search
            </button>
          </div>
          <div style={styles.toolbarRight}>
            <button style={styles.cancelButton} onClick={cancel}>
              Close
              <span style={styles.keyHint}>esc</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Main recording view
  return (
    <div style={styles.container}>
      {locationOverlay}
      {/* Resize handle indicator */}
      <div style={styles.resizeHandle}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path
            d="M10 2L2 10M10 6L6 10M10 10L10 10"
            stroke="#666"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </div>

      {/* Waveform area */}
      <div style={styles.waveformArea}>
        <canvas ref={canvasRef} width={800} height={80} style={styles.canvas} />
        {/* Status message below waveform */}
        <div style={styles.statusMessage}>{statusMessage}</div>
      </div>

      {/* Bottom toolbar */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          <TriangleLogo />
        </div>

        <div style={styles.toolbarCenter}>
          {state === "processing" ? (
            <span style={styles.processingText}>Processing...</span>
          ) : state === "error" ? (
            <button style={styles.retryButton} onClick={reset}>
              Try Again
            </button>
          ) : (
            <button style={styles.stopButton} onClick={state === "recording" ? stop : start}>
              {state === "recording" ? "Stop" : "Start"}
              <span style={styles.keyIndicator}>⌥E</span>
            </button>
          )}
        </div>

        <div style={styles.toolbarRight}>
          <button style={styles.cancelButton} onClick={cancel}>
            Cancel
            <span style={styles.keyHint}>esc</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// Triangle logo component
function TriangleLogo() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#888" strokeWidth="2">
      <path d="M12 4L22 20H2L12 4Z" strokeLinejoin="round" />
    </svg>
  );
}

// Styles
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    backgroundColor: "#1c1c1c",
    color: "#fff",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    overflow: "hidden",
  },
  resizeHandle: {
    position: "absolute",
    top: 8,
    right: 8,
    opacity: 0.6,
  },
  waveformArea: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "0 16px",
  },
  canvas: {
    width: "100%",
    height: "80px",
    maxWidth: "100%",
  },
  statusMessage: {
    marginTop: 12,
    fontSize: 13,
    color: "#888",
    textAlign: "center",
  },
  toolbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 16px",
    backgroundColor: "#1c1c1c",
    borderTop: "1px solid #2a2a2a",
  },
  toolbarLeft: {
    flex: 1,
    display: "flex",
    alignItems: "center",
  },
  toolbarCenter: {
    flex: 2,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  toolbarRight: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-end",
  },
  stopButton: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 12px",
    backgroundColor: "transparent",
    color: "#fff",
    border: "none",
    fontSize: 14,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  keyIndicator: {
    display: "inline-flex",
    alignItems: "center",
    padding: "2px 8px",
    backgroundColor: "#3a3a3a",
    borderRadius: 4,
    fontSize: 12,
    color: "#ccc",
  },
  cancelButton: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 12px",
    backgroundColor: "transparent",
    color: "#888",
    border: "none",
    fontSize: 14,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  keyHint: {
    display: "inline-flex",
    alignItems: "center",
    padding: "2px 8px",
    backgroundColor: "#3a3a3a",
    borderRadius: 4,
    fontSize: 12,
    color: "#888",
  },
  processingText: {
    color: "#888",
    fontSize: 14,
  },
  actionButton: {
    padding: "8px 16px",
    backgroundColor: "#3a3a3a",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  searchButton: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 16px",
    backgroundColor: "#4a7c59",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  retryButton: {
    padding: "8px 16px",
    backgroundColor: "#3a3a3a",
    color: "#ccc",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    cursor: "pointer",
    fontFamily: "inherit",
  },
  // Transcription view styles
  transcriptContainer: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  transcriptLabel: {
    fontSize: 12,
    color: "#888",
    marginBottom: 12,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  transcriptBox: {
    width: "100%",
    maxWidth: 500,
    padding: 16,
    backgroundColor: "#2a2a2a",
    borderRadius: 8,
    border: "1px solid #3a3a3a",
  },
  transcriptText: {
    fontSize: 16,
    color: "#fff",
    textAlign: "center",
    lineHeight: 1.5,
  },
  searchPrompt: {
    marginTop: 16,
    fontSize: 14,
    color: "#666",
  },
  // Results view styles
  resultsContainer: {
    flex: 1,
    padding: 16,
    overflowY: "auto",
  },
  locationOverlay: {
    position: "absolute",
    inset: 0,
    backgroundColor: "rgba(0, 0, 0, 0.6)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 20,
  },
  locationModal: {
    width: "90%",
    maxWidth: 360,
    backgroundColor: "#1f1f1f",
    border: "1px solid #2f2f2f",
    borderRadius: 10,
    padding: 20,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  locationTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: "#fff",
  },
  locationSubtitle: {
    fontSize: 12,
    color: "#888",
  },
  locationInput: {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #3a3a3a",
    backgroundColor: "#121212",
    color: "#fff",
    fontSize: 14,
  },
  locationActions: {
    display: "flex",
    gap: 8,
    justifyContent: "flex-end",
  },
  locationSaveButton: {
    padding: "8px 14px",
    borderRadius: 6,
    border: "none",
    backgroundColor: "#4a7c59",
    color: "#fff",
    cursor: "pointer",
    fontSize: 13,
  },
  locationCancelButton: {
    padding: "8px 14px",
    borderRadius: 6,
    border: "1px solid #3a3a3a",
    backgroundColor: "transparent",
    color: "#aaa",
    cursor: "pointer",
    fontSize: 13,
  },
  queryBox: {
    padding: "8px 12px",
    backgroundColor: "#2a2a2a",
    borderRadius: 6,
    marginBottom: 12,
    fontSize: 13,
    color: "#aaa",
  },
  queryLabel: {
    color: "#666",
    marginRight: 4,
  },
  resultsTitle: {
    margin: "0 0 12px 0",
    fontSize: 16,
    fontWeight: 600,
  },
  eventsList: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  eventCard: {
    padding: 12,
    backgroundColor: "#2a2a2a",
    borderRadius: 8,
    border: "1px solid #3a3a3a",
  },
  eventTitle: {
    margin: "0 0 8px 0",
    fontSize: 14,
    fontWeight: 600,
  },
  eventDetail: {
    margin: "4px 0",
    fontSize: 12,
    color: "#aaa",
  },
  eventLink: {
    display: "inline-block",
    marginTop: 8,
    color: "#4dabf7",
    fontSize: 12,
    textDecoration: "none",
  },
};
