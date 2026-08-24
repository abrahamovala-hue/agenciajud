/**
 * Video Edit Spec — schema runtime (Zod) + tipos TypeScript
 * -----------------------------------------------------------
 *
 * Esta é a ÚNICA definição do formato VideoEditSpec. Os tipos TypeScript em
 * `src/types/video-edit-spec.ts` são apenas um re-export de `z.infer<...>`
 * daqui — não existe uma segunda definição manual que possa divergir.
 *
 * Motivo de usar Zod como fonte (em vez de manter `interface` + validador
 * separado): o Video Editor Agent (futuro) vai gerar VideoEditSpec
 * automaticamente. Um schema Zod nos dá, de um único lugar: validação
 * estrutural, validação semântica (cross-field) e o tipo TypeScript — os
 * três sempre em sincronia, porque o tipo é derivado do schema, não escrito
 * à mão ao lado dele.
 *
 * Todos os campos de tempo continuam em SEGUNDOS (ver justificativa no
 * arquivo de tipos original).
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const VideoFormatSchema = z.enum(["vertical", "horizontal", "square"]);
export type VideoFormat = z.infer<typeof VideoFormatSchema>;

export const AssetTypeSchema = z.enum(["video", "image", "audio"]);
export type AssetType = z.infer<typeof AssetTypeSchema>;

export const OverlayPositionSchema = z.enum([
  "top",
  "center",
  "bottom",
  "top-left",
  "top-right",
  "bottom-left",
  "bottom-right",
]);
export type OverlayPosition = z.infer<typeof OverlayPositionSchema>;

export const OverlayAnimationSchema = z.enum(["none", "fade", "slide-up", "pop"]);
export type OverlayAnimation = z.infer<typeof OverlayAnimationSchema>;

export const ExportCodecSchema = z.enum(["h264", "h265", "vp8", "vp9", "prores"]);
export type ExportCodec = z.infer<typeof ExportCodecSchema>;

// ---------------------------------------------------------------------------
// PROJECT
// ---------------------------------------------------------------------------

export const ProjectMetaSchema = z.object({
  id: z.string().min(1),
  title: z.string().optional(),
  format: VideoFormatSchema,
  width: z.number().positive(),
  height: z.number().positive(),
  fps: z.number().positive(),
  /** Duração total da composição, em segundos. */
  duration: z.number().positive(),
});
export type ProjectMeta = z.infer<typeof ProjectMetaSchema>;

// ---------------------------------------------------------------------------
// ASSETS
// ---------------------------------------------------------------------------

export const AssetSchema = z.object({
  id: z.string().min(1),
  /**
   * Ver convenção completa em `src/timeline/assetSource.ts`. Resumo: "#..."
   * = cor placeholder; "http(s)://..." = URL remota; qualquer outro valor =
   * caminho relativo dentro de `public/`.
   */
  source: z.string().min(1),
  type: AssetTypeSchema,
});
export type Asset = z.infer<typeof AssetSchema>;

export const ProjectAssetsSchema = z.object({
  videos: z.array(AssetSchema),
  images: z.array(AssetSchema),
  audio: z.array(AssetSchema),
});
export type ProjectAssets = z.infer<typeof ProjectAssetsSchema>;

// ---------------------------------------------------------------------------
// TIMELINE
// ---------------------------------------------------------------------------

export const TimelineSegmentSchema = z
  .object({
    id: z.string().min(1),
    assetId: z.string().min(1),
    start: z.number().nonnegative(),
    end: z.number(),
    trimStart: z.number().nonnegative().optional(),
    trimEnd: z.number().optional(),
    speed: z.number().positive().optional(),
    /** 0–1. */
    volume: z.number().min(0).max(1).optional(),
  })
  .refine((segment) => segment.end > segment.start, {
    message: "end deve ser maior que start",
    path: ["end"],
  })
  .refine(
    (segment) => segment.trimEnd === undefined || segment.trimEnd > (segment.trimStart ?? 0),
    { message: "trimEnd deve ser maior que trimStart", path: ["trimEnd"] },
  );
export type TimelineSegment = z.infer<typeof TimelineSegmentSchema>;

// ---------------------------------------------------------------------------
// TEXT / OVERLAYS
// ---------------------------------------------------------------------------

export const TextOverlayStyleSchema = z.object({
  fontSize: z.number().positive().optional(),
  color: z.string().optional(),
  fontWeight: z.enum(["normal", "bold"]).optional(),
  background: z.string().optional(),
});
export type TextOverlayStyle = z.infer<typeof TextOverlayStyleSchema>;

export const TextOverlaySchema = z
  .object({
    id: z.string().min(1),
    text: z.string().min(1),
    start: z.number().nonnegative(),
    end: z.number(),
    position: OverlayPositionSchema,
    style: TextOverlayStyleSchema.optional(),
    animation: OverlayAnimationSchema.optional(),
  })
  .refine((overlay) => overlay.end > overlay.start, {
    message: "end deve ser maior que start",
    path: ["end"],
  });
export type TextOverlay = z.infer<typeof TextOverlaySchema>;

// ---------------------------------------------------------------------------
// CAPTIONS
// ---------------------------------------------------------------------------

export const CaptionSegmentSchema = z
  .object({
    start: z.number().nonnegative(),
    end: z.number(),
    text: z.string().min(1),
  })
  .refine((segment) => segment.end > segment.start, {
    message: "end deve ser maior que start",
    path: ["end"],
  });
export type CaptionSegment = z.infer<typeof CaptionSegmentSchema>;

export const CaptionsSchema = z.object({
  enabled: z.boolean(),
  segments: z.array(CaptionSegmentSchema),
});
export type Captions = z.infer<typeof CaptionsSchema>;

// ---------------------------------------------------------------------------
// AUDIO / MUSIC
// ---------------------------------------------------------------------------

export const MusicTrackSchema = z
  .object({
    assetId: z.string().min(1),
    /** 0–1. */
    volume: z.number().min(0).max(1),
    start: z.number().nonnegative(),
    end: z.number(),
    fadeIn: z.number().nonnegative().optional(),
    fadeOut: z.number().nonnegative().optional(),
  })
  .refine((track) => track.end > track.start, {
    message: "end deve ser maior que start",
    path: ["end"],
  });
export type MusicTrack = z.infer<typeof MusicTrackSchema>;

// ---------------------------------------------------------------------------
// CTA
// ---------------------------------------------------------------------------

export const CallToActionSchema = z
  .object({
    text: z.string().min(1),
    start: z.number().nonnegative(),
    end: z.number(),
  })
  .refine((cta) => cta.end > cta.start, {
    message: "end deve ser maior que start",
    path: ["end"],
  });
export type CallToAction = z.infer<typeof CallToActionSchema>;

// ---------------------------------------------------------------------------
// EXPORT
// ---------------------------------------------------------------------------

export const ExportSettingsSchema = z.object({
  width: z.number().positive(),
  height: z.number().positive(),
  fps: z.number().positive(),
  /**
   * ATENÇÃO — verificado nesta etapa: hoje este campo é METADATA PURA.
   * Nenhum código em `src/` ou em `remotion.config.ts` lê `export.codec`
   * para configurar o render (não há `Config.setCodec(...)`, nem nada
   * passando `--codec` para o CLI). O h264 do primeiro render veio do
   * default do próprio `remotion render`, não deste campo. Wiring real fica
   * para quando o render for disparado programaticamente (Tool do Agno).
   */
  codec: ExportCodecSchema.optional(),
});
export type ExportSettings = z.infer<typeof ExportSettingsSchema>;

// ---------------------------------------------------------------------------
// VideoEditSpec
// ---------------------------------------------------------------------------

export const VideoEditSpecSchema = z
  .object({
    project: ProjectMetaSchema,
    assets: ProjectAssetsSchema,
    timeline: z.array(TimelineSegmentSchema),
    overlays: z.array(TextOverlaySchema),
    captions: CaptionsSchema,
    music: z.array(MusicTrackSchema),
    cta: CallToActionSchema,
    export: ExportSettingsSchema,
  })
  .superRefine((spec, ctx) => {
    const visualAssetIds = new Set([
      ...spec.assets.videos.map((asset) => asset.id),
      ...spec.assets.images.map((asset) => asset.id),
    ]);
    const audioAssetIds = new Set(spec.assets.audio.map((asset) => asset.id));

    const requireStartBeforeDuration = (start: number, path: (string | number)[]) => {
      if (start >= spec.project.duration) {
        ctx.addIssue({
          code: "custom",
          message: `start (${start}s) nao pode ser >= duration do projeto (${spec.project.duration}s)`,
          path,
        });
      }
    };

    spec.timeline.forEach((segment, index) => {
      if (!visualAssetIds.has(segment.assetId)) {
        ctx.addIssue({
          code: "custom",
          message: `assetId "${segment.assetId}" nao existe em assets.videos/images`,
          path: ["timeline", index, "assetId"],
        });
      }
      requireStartBeforeDuration(segment.start, ["timeline", index, "start"]);
    });

    spec.music.forEach((track, index) => {
      if (!audioAssetIds.has(track.assetId)) {
        ctx.addIssue({
          code: "custom",
          message: `assetId "${track.assetId}" nao existe em assets.audio`,
          path: ["music", index, "assetId"],
        });
      }
      requireStartBeforeDuration(track.start, ["music", index, "start"]);
    });

    spec.overlays.forEach((overlay, index) => {
      requireStartBeforeDuration(overlay.start, ["overlays", index, "start"]);
    });

    spec.captions.segments.forEach((segment, index) => {
      requireStartBeforeDuration(segment.start, ["captions", "segments", index, "start"]);
    });

    requireStartBeforeDuration(spec.cta.start, ["cta", "start"]);
  });

export type VideoEditSpec = z.infer<typeof VideoEditSpecSchema>;

// ---------------------------------------------------------------------------
// parseVideoEditSpec — ponto único de validação (fail fast)
// ---------------------------------------------------------------------------

export interface VideoEditSpecIssue {
  path: PropertyKey[];
  message: string;
}

export class VideoEditSpecValidationError extends Error {
  issues: VideoEditSpecIssue[];

  constructor(issues: VideoEditSpecIssue[]) {
    const details = issues
      .map((issue) => `  - ${issue.path.join(".") || "(root)"}: ${issue.message}`)
      .join("\n");
    super(`VideoEditSpec invalido:\n${details}`);
    this.name = "VideoEditSpecValidationError";
    this.issues = issues;
  }
}

/**
 * Única porta de entrada para validar um VideoEditSpec vindo de fora (arquivo
 * JSON, --props do CLI, ou futuramente o Video Editor Agent). JSON válido ->
 * objeto tipado e validado. JSON inválido -> lança erro claro com o(s)
 * campo(s) problemático(s). Nenhum componente React deve reimplementar esta
 * checagem — eles recebem sempre um VideoEditSpec já validado.
 */
export function parseVideoEditSpec(data: unknown): VideoEditSpec {
  const result = VideoEditSpecSchema.safeParse(data);
  if (!result.success) {
    throw new VideoEditSpecValidationError(result.error.issues);
  }
  return result.data;
}
