import { useCallback, useEffect, useRef } from "react";

interface WaveformCanvasProps {
  volume: number;
  getVolumeData: () => Uint8Array | null;
  state: "idle" | "recording" | "processing" | "error" | "transcribed" | "results";
}

export function WaveformCanvas({ volume, getVolumeData, state }: WaveformCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);

  const drawDottedLine = useCallback(
    (ctx: CanvasRenderingContext2D, width: number, centerY: number) => {
      const dotSpacing = 8;
      const dotRadius = 1.5;
      ctx.fillStyle = "#666";
      for (let x = dotSpacing; x < width - dotSpacing; x += dotSpacing) {
        ctx.beginPath();
        ctx.arc(x, centerY, dotRadius, 0, Math.PI * 2);
        ctx.fill();
      }
    },
    []
  );

  const drawVolumeWaveform = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      width: number,
      height: number,
      centerY: number,
      vol: number
    ) => {
      const dotSpacing = 8;
      const dotRadius = 1.5;
      const amplitude = Math.min(height * 0.4, (vol * 500) * (height * 0.4));
      const time = Date.now() / 100;

      const audioData = getVolumeData();

      ctx.fillStyle = "#aaa";
      const numDots = Math.floor((width - dotSpacing * 2) / dotSpacing);

      for (let i = 0; i < numDots; i++) {
        const x = dotSpacing + i * dotSpacing;

        let wave: number;
        if (audioData) {
          const idx = Math.floor(
            (i / numDots) * audioData.length
          );
          const sample = (audioData[idx] - 128) / 128;
          wave = sample;
        } else {
          wave =
            Math.sin(x * 0.05 + time) *
            Math.sin(x * 0.1 + time * 1.5);
        }

        const y = centerY + wave * amplitude;

        ctx.beginPath();
        ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
        ctx.fill();
      }
    },
    [getVolumeData]
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const centerY = height / 2;

    ctx.fillStyle = "#1c1c1c";
    ctx.fillRect(0, 0, width, height);

    if (state === "recording") {
      if (volume < 0.01) {
        drawDottedLine(ctx, width, centerY);
      } else {
        drawVolumeWaveform(ctx, width, height, centerY, volume);
      }
      animationRef.current = requestAnimationFrame(draw);
    } else {
      drawDottedLine(ctx, width, centerY);
    }
  }, [state, volume, drawDottedLine, drawVolumeWaveform]);

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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#1c1c1c";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        drawDottedLine(ctx, canvas.width, canvas.height / 2);
      }
    }
  }, [drawDottedLine]);

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={80}
      className="w-full max-w-2xl h-20"
    />
  );
}
