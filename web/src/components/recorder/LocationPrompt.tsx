import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface LocationPromptProps {
  locationInput: string;
  countryInput: string;
  onLocationChange: (v: string) => void;
  onCountryChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

export function LocationPrompt({
  locationInput,
  countryInput,
  onLocationChange,
  onCountryChange,
  onSave,
  onCancel,
}: LocationPromptProps) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="w-[90%] max-w-sm bg-card border border-border rounded-xl p-5 flex flex-col gap-3">
        <h3 className="text-base font-semibold">Where are you?</h3>
        <p className="text-sm text-muted-foreground">
          We only store this locally on your device.
        </p>
        <Input
          placeholder="City, State/Region"
          value={locationInput}
          onChange={(e) => onLocationChange(e.target.value)}
          onKeyDown={(e) => e.stopPropagation()}
          autoFocus
        />
        <Input
          placeholder="Country code (optional, e.g. US)"
          value={countryInput}
          onChange={(e) => onCountryChange(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.stopPropagation()}
        />
        <div className="flex gap-2 justify-end">
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" onClick={onSave}>
            Save Location
          </Button>
        </div>
      </div>
    </div>
  );
}
