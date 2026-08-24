import React from "react";
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  useCurrentFrame,
} from "remotion";
import type { TimelineSegment, VideoEditSpec } from "../types/video-edit-spec";
import { resolveAsset } from "./resolveAsset";
import { resolveAssetSource } from "./assetSource";
import { secondsToFrames } from "./time";

const TRANSITION_FRAMES = 10;

const SceneContent: React.FC<{ segment: TimelineSegment; spec: VideoEditSpec }> = ({
  segment,
  spec,
}) => {
  const frame = useCurrentFrame();
  const { fps } = spec.project;
  const durationInFrames = secondsToFrames(segment.end - segment.start, fps);

  // Crossfade simples nas bordas do segmento — a "transição" pedida na V1.
  const opacity = interpolate(
    frame,
    [0, TRANSITION_FRAMES, durationInFrames - TRANSITION_FRAMES, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const asset = resolveAsset(spec, segment.assetId);

  if (!asset) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#000000", opacity }} />
    );
  }

  const resolved = resolveAssetSource(asset.source);

  if (resolved.kind === "color") {
    return <AbsoluteFill style={{ backgroundColor: resolved.value, opacity }} />;
  }

  if (asset.type === "image") {
    return (
      <AbsoluteFill style={{ opacity }}>
        <Img src={resolved.value} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </AbsoluteFill>
    );
  }

  if (asset.type === "video") {
    const trimStartFrames = secondsToFrames(segment.trimStart ?? 0, fps);
    return (
      <AbsoluteFill style={{ opacity }}>
        <OffthreadVideo
          src={resolved.value}
          startFrom={trimStartFrames}
          playbackRate={segment.speed ?? 1}
          volume={segment.volume ?? 1}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
    );
  }

  return <AbsoluteFill style={{ backgroundColor: "#000000", opacity }} />;
};

/** Renderiza um segmento da timeline na sua janela de tempo (start/end). */
export const Scene: React.FC<{ segment: TimelineSegment; spec: VideoEditSpec }> = ({
  segment,
  spec,
}) => {
  const { fps } = spec.project;
  const from = secondsToFrames(segment.start, fps);
  const durationInFrames = secondsToFrames(segment.end - segment.start, fps);

  if (durationInFrames <= 0) {
    return null;
  }

  return (
    <Sequence from={from} durationInFrames={durationInFrames} name={segment.id}>
      <SceneContent segment={segment} spec={spec} />
    </Sequence>
  );
};
