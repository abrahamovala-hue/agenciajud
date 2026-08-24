import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import type { CaptionSegment } from "../types/video-edit-spec";
import { secondsToFrames } from "./time";

/** Renderiza uma linha de legenda (estilo subtitle) na sua janela de tempo. */
export const CaptionLayer: React.FC<{ segment: CaptionSegment; fps: number }> = ({
  segment,
  fps,
}) => {
  const from = secondsToFrames(segment.start, fps);
  const durationInFrames = secondsToFrames(segment.end - segment.start, fps);

  if (durationInFrames <= 0) {
    return null;
  }

  return (
    <Sequence from={from} durationInFrames={durationInFrames} name={`caption-${from}`}>
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: "22%" }}>
        <div
          style={{
            fontFamily: "sans-serif",
            fontSize: 32,
            fontWeight: 600,
            color: "#FFFFFF",
            background: "rgba(0,0,0,0.55)",
            padding: "0.4em 0.7em",
            borderRadius: 8,
            textAlign: "center",
            maxWidth: "80%",
          }}
        >
          {segment.text}
        </div>
      </AbsoluteFill>
    </Sequence>
  );
};
