import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";
import type { OverlayAnimation, OverlayPosition, TextOverlay } from "../types/video-edit-spec";
import { secondsToFrames } from "./time";

const ANIMATION_FRAMES = 8;

const positionStyle: Record<OverlayPosition, React.CSSProperties> = {
  top: { justifyContent: "center", alignItems: "flex-start", paddingTop: "8%" },
  center: { justifyContent: "center", alignItems: "center" },
  bottom: { justifyContent: "center", alignItems: "flex-end", paddingBottom: "10%" },
  "top-left": { justifyContent: "flex-start", alignItems: "flex-start", padding: "8%" },
  "top-right": { justifyContent: "flex-end", alignItems: "flex-start", padding: "8%" },
  "bottom-left": { justifyContent: "flex-start", alignItems: "flex-end", padding: "8%" },
  "bottom-right": { justifyContent: "flex-end", alignItems: "flex-end", padding: "8%" },
};

const animatedStyle = (
  animation: OverlayAnimation | undefined,
  frame: number,
  durationInFrames: number,
): React.CSSProperties => {
  const fadeOpacity = interpolate(
    frame,
    [0, ANIMATION_FRAMES, Math.max(durationInFrames - ANIMATION_FRAMES, ANIMATION_FRAMES), durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  if (animation === "slide-up") {
    const translateY = interpolate(frame, [0, ANIMATION_FRAMES], [24, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return { opacity: fadeOpacity, transform: `translateY(${translateY}px)` };
  }

  if (animation === "pop") {
    const scale = interpolate(frame, [0, ANIMATION_FRAMES], [0.85, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return { opacity: fadeOpacity, transform: `scale(${scale})` };
  }

  if (animation === "none") {
    return { opacity: 1 };
  }

  // "fade" e default
  return { opacity: fadeOpacity };
};

const TextLayerContent: React.FC<{
  overlay: TextOverlay;
  durationInFrames: number;
  variant: "overlay" | "cta";
}> = ({ overlay, durationInFrames, variant }) => {
  const frame = useCurrentFrame();
  const style = animatedStyle(overlay.animation, frame, durationInFrames);

  const isCta = variant === "cta";

  return (
    <AbsoluteFill style={positionStyle[overlay.position]}>
      <div
        style={{
          ...style,
          fontFamily: "sans-serif",
          fontSize: overlay.style?.fontSize ?? (isCta ? 56 : 44),
          fontWeight: overlay.style?.fontWeight === "normal" ? 400 : 700,
          color: overlay.style?.color ?? "#FFFFFF",
          backgroundColor: overlay.style?.background,
          padding: overlay.style?.background ? "0.3em 0.6em" : undefined,
          borderRadius: overlay.style?.background ? 12 : undefined,
          textAlign: "center",
          maxWidth: "85%",
          textShadow: overlay.style?.background ? undefined : "0 2px 12px rgba(0,0,0,0.55)",
        }}
      >
        {overlay.text}
      </div>
    </AbsoluteFill>
  );
};

/** Renderiza um texto (overlay comum ou CTA) na sua janela de tempo. */
export const TextLayer: React.FC<{
  overlay: TextOverlay;
  fps: number;
  variant?: "overlay" | "cta";
}> = ({ overlay, fps, variant = "overlay" }) => {
  const from = secondsToFrames(overlay.start, fps);
  const durationInFrames = secondsToFrames(overlay.end - overlay.start, fps);

  if (durationInFrames <= 0) {
    return null;
  }

  return (
    <Sequence from={from} durationInFrames={durationInFrames} name={overlay.id}>
      <TextLayerContent overlay={overlay} durationInFrames={durationInFrames} variant={variant} />
    </Sequence>
  );
};
