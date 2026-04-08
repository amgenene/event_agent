"use client";

import { UserButton } from "@clerk/nextjs";
import { WaveformCanvas } from "@/components/recorder/WaveformCanvas";
import { LocationPrompt } from "@/components/recorder/LocationPrompt";
import { useRecorder } from "@/components/recorder/useRecorder";
import { Button } from "@/components/ui/button";
import type { Event as EventType } from "@/lib/types";

function TriangleLogo() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#888"
      strokeWidth="2"
    >
      <path d="M12 4L22 20H2L12 4Z" strokeLinejoin="round" />
    </svg>
  );
}

export function SearchPageClient() {
  const recorder = useRecorder();

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded-md flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-sm">
              EF
            </span>
          </div>
          <span className="font-semibold text-lg">EventFinder AI</span>
        </div>
        <UserButton />
      </header>

      <main className="flex-1 flex flex-col">
        {recorder.state === "transcribed" ||
        (recorder.state === "error" && recorder.transcript) ? (
          <TranscribedView recorder={recorder} />
        ) : recorder.state === "results" && recorder.events.length > 0 ? (
          <ResultsView recorder={recorder} />
        ) : (
          <RecordingView recorder={recorder} />
        )}
      </main>

      {recorder.locationPromptOpen && (
        <LocationPrompt
          locationInput={recorder.locationInput}
          countryInput={recorder.countryInput}
          onLocationChange={recorder.setLocationInput}
          onCountryChange={recorder.setCountryInput}
          onSave={recorder.saveLocation}
          onCancel={() => recorder.setLocationPromptOpen(false)}
        />
      )}
    </div>
  );
}

function RecordingView({
  recorder,
}: {
  recorder: ReturnType<typeof useRecorder>;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6">
      <WaveformCanvas
        volume={recorder.volume}
        getVolumeData={recorder.getVolumeData}
        state={recorder.state}
      />
      <p className="mt-3 text-sm text-muted-foreground text-center">
        {recorder.statusMessage}
      </p>

      <div className="flex items-center gap-4 mt-8">
        {recorder.state === "processing" ? (
          <span className="text-sm text-muted-foreground">Processing...</span>
        ) : recorder.state === "error" ? (
          <Button onClick={recorder.reset}>Try Again</Button>
        ) : (
          <Button
            onClick={
              recorder.state === "recording"
                ? recorder.stopRecording
                : recorder.startRecording
            }
            variant={recorder.state === "recording" ? "destructive" : "default"}
          >
            {recorder.state === "recording" ? "Stop" : "Start"}
            <kbd className="ml-2 text-xs bg-muted px-1.5 py-0.5 rounded">
              ⌘E
            </kbd>
          </Button>
        )}
        {(recorder.state === "recording" ||
          recorder.state === "idle" ||
          recorder.state === "error") && (
          <Button variant="ghost" onClick={recorder.cancelRecording}>
            Cancel
            <kbd className="ml-2 text-xs bg-muted px-1.5 py-0.5 rounded">
              esc
            </kbd>
          </Button>
        )}
      </div>
    </div>
  );
}

function TranscribedView({
  recorder,
}: {
  recorder: ReturnType<typeof useRecorder>;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-md space-y-4 text-center">
        <p className="text-xs uppercase tracking-wider text-muted-foreground">
          You said:
        </p>
        <div className="p-4 bg-card border border-border rounded-lg">
          <p className="text-base">
            {recorder.transcript || "(No speech detected)"}
          </p>
        </div>
        {recorder.queryUsed && (
          <p className="text-xs text-muted-foreground">
            Search query: {recorder.queryUsed}
          </p>
        )}
        <p className="text-sm text-muted-foreground">Search for events?</p>
      </div>

      <div className="flex items-center gap-3 mt-8">
        <Button onClick={recorder.searchWithTranscript}>
          Search
          <kbd className="ml-2 text-xs bg-muted px-1.5 py-0.5 rounded">
            Enter
          </kbd>
        </Button>
        <Button variant="outline" onClick={recorder.reset}>
          Retry
        </Button>
        <Button variant="ghost" onClick={recorder.cancelRecording}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function ResultsView({
  recorder,
}: {
  recorder: ReturnType<typeof useRecorder>;
}) {
  return (
    <div className="flex-1 flex flex-col px-6 py-8 max-w-2xl mx-auto w-full">
      <div className="mb-4 p-3 bg-card border border-border rounded-lg text-sm text-muted-foreground">
        <span className="text-xs text-muted-foreground/70">Query:</span>{" "}
        &quot;{recorder.queryUsed || recorder.transcript}&quot;
      </div>

      <h2 className="text-lg font-semibold mb-4">
        📅 Found {recorder.events.length} event(s)
      </h2>

      <div className="flex-1 overflow-y-auto space-y-3">
        {recorder.events.map((event: EventType) => (
          <EventCard key={event.id} event={event} />
        ))}
      </div>

      <div className="flex items-center gap-3 mt-6 pt-4 border-t border-border">
        <Button onClick={recorder.reset}>New Search</Button>
      </div>
    </div>
  );
}

function EventCard({ event }: { event: EventType }) {
  return (
    <div className="p-4 bg-card border border-border rounded-lg space-y-2">
      <h3 className="font-semibold">{event.title}</h3>
      <p className="text-sm text-muted-foreground">📍 {event.location}</p>
      <p className="text-sm text-muted-foreground">
        🗓️ {event.date} at {event.time}
      </p>
      <p className="text-sm text-muted-foreground">💰 {event.price}</p>
      {event.url && (
        <a
          href={event.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-400 hover:underline inline-block"
        >
          View Details →
        </a>
      )}
    </div>
  );
}
