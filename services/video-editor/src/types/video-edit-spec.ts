/**
 * Re-export puro. A definição real do VideoEditSpec vive em
 * `src/schema/video-edit-spec.schema.ts` (schema Zod, tipos inferidos via
 * `z.infer`). Este arquivo existe só para os módulos em `src/timeline/*`
 * continuarem importando de um caminho estável de "tipos", sem precisar
 * saber que a fonte é um schema Zod.
 */
export type {
  VideoFormat,
  AssetType,
  Asset,
  ProjectAssets,
  ProjectMeta,
  TimelineSegment,
  OverlayPosition,
  OverlayAnimation,
  TextOverlayStyle,
  TextOverlay,
  CaptionSegment,
  Captions,
  MusicTrack,
  CallToAction,
  ExportCodec,
  ExportSettings,
  VideoEditSpec,
} from "../schema/video-edit-spec.schema";
