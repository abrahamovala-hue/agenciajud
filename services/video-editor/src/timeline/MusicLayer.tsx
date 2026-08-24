import React from "react";
import { Audio, Sequence, interpolate, useCurrentFrame } from "remotion";
import type { MusicTrack, VideoEditSpec } from "../types/video-edit-spec";
import { resolveAsset } from "./resolveAsset";
import { resolveAssetSource } from "./assetSource";
import { secondsToFrames } from "./time";

const VolumeEnvelope: React.FC<{ track: MusicTrack; durationInFrames: number; fps: number; src: string }> = ({
  track,
  durationInFrames,
  fps,
  src,
}) => {
  const frame = useCurrentFrame();
  const fadeInFrames = secondsToFrames(track.fadeIn ?? 0, fps);
  const fadeOutFrames = secondsToFrames(track.fadeOut ?? 0, fps);

  const volume = interpolate(
    frame,
    [
      0,
      Math.max(fadeInFrames, 0.001),
      Math.max(durationInFrames - fadeOutFrames, fadeInFrames + 0.001),
      durationInFrames,
    ],
    [0, track.volume, track.volume, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return <Audio src={src} volume={volume} />;
};

/** Renderiza uma faixa de música/áudio com envelope de fade-in/fade-out. */
export const MusicLayer: React.FC<{ track: MusicTrack; spec: VideoEditSpec }> = ({ track, spec }) => {
  const { fps } = spec.project;
  const from = secondsToFrames(track.start, fps);
  const durationInFrames = secondsToFrames(track.end - track.start, fps);
  const asset = resolveAsset(spec, track.assetId);

  if (!asset || asset.type !== "audio" || durationInFrames <= 0) {
    return null;
  }

  const resolved = resolveAssetSource(asset.source);

  return (
    <Sequence from={from} durationInFrames={durationInFrames} name={`music-${track.assetId}`}>
      <VolumeEnvelope track={track} durationInFrames={durationInFrames} fps={fps} src={resolved.value} />
    </Sequence>
  );
};
