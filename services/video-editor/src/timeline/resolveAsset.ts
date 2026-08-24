import type { Asset, VideoEditSpec } from "../types/video-edit-spec";

/** Procura um asset pelo id nas três listas (`videos`, `images`, `audio`). */
export const resolveAsset = (
  spec: VideoEditSpec,
  assetId: string,
): Asset | undefined => {
  return (
    spec.assets.videos.find((asset) => asset.id === assetId) ??
    spec.assets.images.find((asset) => asset.id === assetId) ??
    spec.assets.audio.find((asset) => asset.id === assetId)
  );
};
