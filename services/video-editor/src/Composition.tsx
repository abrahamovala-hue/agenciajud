import React from "react";
import { AbsoluteFill, CalculateMetadataFunction, Composition } from "remotion";
import type { VideoEditSpec } from "./types/video-edit-spec";
import { parseVideoEditSpec } from "./schema/video-edit-spec.schema";
import sampleReelJson from "../examples/sample-reel.json";
import { Scene } from "./timeline/Scene";
import { TextLayer } from "./timeline/TextLayer";
import { CaptionLayer } from "./timeline/CaptionLayer";
import { MusicLayer } from "./timeline/MusicLayer";

/**
 * As props da Composition SÃO o VideoEditSpec diretamente (sem wrapper tipo
 * `{ spec: ... }`). Isso importa na prática: o `--props` do Remotion CLI faz
 * merge do JSON apontado direto nas props da Composition — se o tipo fosse
 * `{ spec: VideoEditSpec }` mas o JSON de exemplo fosse um VideoEditSpec "nu"
 * (sem chave `spec`), o CLI injetaria campos soltos que ninguém lê e
 * `props.spec` nunca mudaria. Mantendo Props = VideoEditSpec, o mesmo JSON
 * serve como defaultProps E como --props sem transformação nenhuma.
 */
type Props = VideoEditSpec;

/**
 * examples/sample-reel.json é a fonte única do spec de exemplo — usada tanto
 * pelo Studio (via defaultProps) quanto pelo CLI (`remotion render
 * VideoEditSpec out.mp4 --props=./examples/sample-reel.json`). Validado aqui
 * mesmo no carregamento do módulo: se o exemplo canônico ficar inválido, o
 * Studio já falha ao abrir em vez de renderizar algo quebrado.
 */
const sampleReel: VideoEditSpec = parseVideoEditSpec(sampleReelJson);

/**
 * Ponto único de validação para o que realmente chega à Composition — tanto
 * o defaultProps do Studio quanto qualquer `--props` do CLI passam por aqui.
 * calculateMetadata roda antes do componente React montar, então um spec
 * inválido nunca chega a renderizar: falha aqui, com erro claro de campo.
 */
const calculateMetadata: CalculateMetadataFunction<Props> = ({ props }) => {
  const spec = parseVideoEditSpec(props);
  return {
    props: spec,
    width: spec.project.width,
    height: spec.project.height,
    fps: spec.project.fps,
    durationInFrames: Math.max(Math.round(spec.project.duration * spec.project.fps), 1),
  };
};

/**
 * Registra a composição "VideoEditSpec". Nada de conteúdo editorial vive
 * aqui — tudo vem de `props.spec` (ver src/schema/video-edit-spec.schema.ts).
 */
export const VideoEditComposition = () => {
  return (
    <Composition
      id="VideoEditSpec"
      component={VideoEditSpecPlayer}
      durationInFrames={Math.round(sampleReel.project.duration * sampleReel.project.fps)}
      fps={sampleReel.project.fps}
      width={sampleReel.project.width}
      height={sampleReel.project.height}
      defaultProps={sampleReel}
      calculateMetadata={calculateMetadata}
    />
  );
};

/** Player puro: recebe um VideoEditSpec já validado (como props) e renderiza a timeline. */
export const VideoEditSpecPlayer: React.FC<Props> = (spec) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      {spec.timeline.map((segment) => (
        <Scene key={segment.id} segment={segment} spec={spec} />
      ))}

      {spec.overlays.map((overlay) => (
        <TextLayer key={overlay.id} overlay={overlay} fps={spec.project.fps} variant="overlay" />
      ))}

      {spec.captions.enabled &&
        spec.captions.segments.map((segment, index) => (
          <CaptionLayer key={`caption-${index}`} segment={segment} fps={spec.project.fps} />
        ))}

      {spec.music.map((track, index) => (
        <MusicLayer key={`music-${index}`} track={track} spec={spec} />
      ))}

      <TextLayer
        overlay={{
          id: "cta",
          text: spec.cta.text,
          start: spec.cta.start,
          end: spec.cta.end,
          position: "bottom",
          animation: "fade",
        }}
        fps={spec.project.fps}
        variant="cta"
      />
    </AbsoluteFill>
  );
};
