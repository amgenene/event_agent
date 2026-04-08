import { useCallback, useEffect, useRef, useState } from "react";
import * as Sentry from "@sentry/nextjs";
import type { Event, LocationData, RecorderState } from "@/lib/types";
import { loadSavedLocation, saveSavedLocation } from "@/lib/location";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://event-searcher.com";

export function useRecorder() {
  const [state, setState] = useState<RecorderState>("idle");
  const [statusMessage, setStatusMessage] = useState("Press ⌘E to start");
  const [transcript, setTranscript] = useState("");
  const [events, setEvents] = useState<Event[]>([]);
  const [queryUsed, setQueryUsed] = useState("");
  const [savedLocation, setSavedLocation] = useState<LocationData | null>(null);
  const [locationPromptOpen, setLocationPromptOpen] = useState(false);
  const [locationInput, setLocationInput] = useState("");
  const [countryInput, setCountryInput] = useState("");

  const stateRef = useRef<RecorderState>("idle");
  const locationPromptOpenRef = useRef(false);
  const pendingSearchRef = useRef(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationRef = useRef<number | null>(null);
  const volumeRef = useRef(0);
  const targetVolumeRef = useRef(0);
  const noiseFloorRef = useRef(0);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    locationPromptOpenRef.current = locationPromptOpen;
  }, [locationPromptOpen]);

  useEffect(() => {
    const loc = loadSavedLocation();
    if (loc) {
      setSavedLocation(loc);
      setLocationInput(loc.location);
      setCountryInput(loc.country || "");
    }
  }, []);

  const ensureLocation = useCallback((): Promise<LocationData | null> => {
    return new Promise((resolve) => {
      const loc = loadSavedLocation();
      if (loc) {
        setSavedLocation(loc);
        setLocationInput(loc.location);
        setCountryInput(loc.country || "");
        resolve(loc);
        return;
      }
      setLocationPromptOpen(true);
      const check = setInterval(() => {
        const updated = loadSavedLocation();
        if (updated) {
          clearInterval(check);
          resolve(updated);
        }
      }, 200);
      setTimeout(() => {
        clearInterval(check);
        resolve(null);
      }, 60000);
    });
  }, []);

  const getVolumeData = useCallback((): Uint8Array | null => {
    if (!analyserRef.current) return null;
    const data = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteTimeDomainData(data);
    return data;
  }, []);

  const startRecording = useCallback(async () => {
    if (state === "recording" || state === "processing") return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      audioContextRef.current = audioContext;
      analyserRef.current = analyser;

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4",
      });
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.start(100);
      mediaRecorderRef.current = mediaRecorder;

      Sentry.addBreadcrumb({
        category: "recording",
        message: "Recording started",
        level: "info",
      });

      setState("recording");
      setStatusMessage("🎙️ Recording... (⌘E to stop)");
      setEvents([]);
      setTranscript("");
      volumeRef.current = 0;
      targetVolumeRef.current = 0;
      noiseFloorRef.current = 0;

      const analyze = () => {
        if (stateRef.current !== "recording") return;

        const data = analyserRef.current
          ? new Uint8Array(analyserRef.current.frequencyBinCount)
          : null;
        if (data) {
          analyserRef.current!.getByteTimeDomainData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i++) {
            const v = (data[i] - 128) / 128;
            sum += v * v;
          }
          const rms = Math.sqrt(sum / data.length);
          const gate = noiseFloorRef.current * 1.3 + 0.0025;
          const signal = Math.max(0, rms - gate);
          targetVolumeRef.current = Math.min(1, signal * 4.0);
          if (noiseFloorRef.current === 0) {
            noiseFloorRef.current = rms;
          } else if (rms < noiseFloorRef.current * 1.5) {
            noiseFloorRef.current = noiseFloorRef.current * 0.98 + rms * 0.02;
          }
        }

        volumeRef.current += (targetVolumeRef.current - volumeRef.current) * 0.2;
        animationRef.current = requestAnimationFrame(analyze);
      };
      animationRef.current = requestAnimationFrame(analyze);
    } catch (e) {
      console.error("Failed to start recording:", e);
      Sentry.captureException(e, { tags: { action: "start_recording" } });
      setState("error");
      setStatusMessage("❌ Microphone access denied. Please allow microphone access.");
    }
  }, [state]);

  const stopRecording = useCallback(async () => {
    if (state !== "recording") return;

    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }

    const mediaRecorder = mediaRecorderRef.current;
    if (!mediaRecorder) return;

    setState("processing");
    setStatusMessage("⏳ Processing audio...");

    const stream = mediaRecorder.stream;
    stream.getTracks().forEach((t) => t.stop());

    if (audioContextRef.current) {
      await audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    mediaRecorderRef.current = null;

    await new Promise<void>((resolve) => {
      mediaRecorder.onstop = () => resolve();
      mediaRecorder.stop();
    });

    const blob = new Blob(chunksRef.current, {
      type:
        MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4",
    });

    await transcribeRecording(blob);
  }, [state]);

  const cancelRecording = useCallback(() => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    mediaRecorderRef.current = null;

    setState("idle");
    setStatusMessage("Press ⌘E to start");
  }, []);

  const transcribeRecording = useCallback(async (audioBlob: Blob) => {
    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");

      const response = await fetch(`${API_BASE}/transcribe`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        Sentry.captureMessage("Transcription failed", {
          level: "error",
          tags: { action: "transcribe" },
          extra: { error: errorText, status: response.status },
        });
        setState("error");
        setStatusMessage("❌ Transcription failed: " + errorText);
        return;
      }

      const data = await response.json() as { text?: string };
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
      Sentry.captureException(e, { tags: { action: "transcribe" } });
      setState("error");
      setStatusMessage("❌ Could not connect to server");
    }
  }, []);

  const searchWithTranscript = useCallback(async () => {
    if (!transcript.trim()) return;

    const span = Sentry.startInactiveSpan({
      name: "search_events",
      op: "search",
      attributes: { transcript_length: transcript.length },
    });

    setState("processing");
    setStatusMessage("🔍 Searching for events...");

    try {
      const location = await ensureLocation();
      if (!location) {
        setState("transcribed");
        setStatusMessage("📍 Tell us where you are");
        pendingSearchRef.current = true;
        span.end();
        return;
      }

      const res = await fetch(`${API_BASE}/search`, {
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
        Sentry.captureMessage("Search failed", {
          level: "error",
          tags: { action: "search" },
          extra: { status: res.status },
        });
        setState("error");
        setStatusMessage("❌ Search failed");
        span.end();
        return;
      }

      const data = await res.json() as { events?: Event[]; query_use?: string };
      const events = data.events || [];
      setEvents(events);
      setQueryUsed(data.query_use || "");
      if (events.length > 0) {
        setState("results");
        setStatusMessage(`✅ Found ${events.length} event(s)`);
        Sentry.addBreadcrumb({
          category: "search",
          message: `Found ${events.length} events`,
          level: "info",
          data: { event_count: events.length },
        });
      } else {
        setState("transcribed");
        setStatusMessage("No events found for your query");
      }
      span.end();
    } catch (e) {
      console.error(e);
      Sentry.captureException(e, { tags: { action: "search" } });
      setState("error");
      setStatusMessage("❌ Could not connect to server");
      span.end();
    }
  }, [transcript, ensureLocation]);

  const saveLocation = useCallback(() => {
    const location = locationInput.trim();
    if (!location) return;

    const payload: LocationData = {
      location,
      country: countryInput.trim() || undefined,
    };

    saveSavedLocation(payload);
    setSavedLocation(payload);
    setLocationPromptOpen(false);

    if (pendingSearchRef.current && transcript.trim()) {
      pendingSearchRef.current = false;
      searchWithTranscript();
    }
  }, [countryInput, locationInput, searchWithTranscript, transcript]);

  const reset = useCallback(() => {
    setState("idle");
    setStatusMessage("Press ⌘E to start");
    setTranscript("");
    setEvents([]);
    setQueryUsed("");
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (locationPromptOpenRef.current) {
        if (e.key === "Enter") {
          e.preventDefault();
          saveLocation();
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          setLocationPromptOpen(false);
          return;
        }
        return;
      }

      const isCmdE =
        (e.key === "e" || e.key === "E") && (e.metaKey || e.altKey);

      if (isCmdE) {
        e.preventDefault();
        if (stateRef.current === "recording") {
          stopRecording();
        } else if (
          stateRef.current === "idle" ||
          stateRef.current === "error"
        ) {
          startRecording();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        cancelRecording();
      } else if (e.key === "Enter" && stateRef.current === "transcribed") {
        e.preventDefault();
        searchWithTranscript();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    startRecording,
    stopRecording,
    cancelRecording,
    searchWithTranscript,
    saveLocation,
  ]);

  return {
    state,
    statusMessage,
    transcript,
    events,
    queryUsed,
    savedLocation,
    locationPromptOpen,
    locationInput,
    countryInput,
    volume: volumeRef.current,
    getVolumeData,
    setLocationPromptOpen,
    setLocationInput,
    setCountryInput,
    startRecording,
    stopRecording,
    cancelRecording,
    searchWithTranscript,
    saveLocation,
    reset,
  };
}
