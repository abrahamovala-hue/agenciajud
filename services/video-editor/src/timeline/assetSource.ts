import { staticFile } from "remotion";

export type ResolvedAssetSource =
  | { kind: "color"; value: string }
  | { kind: "url"; value: string };

/**
 * Convenção V1 para `Asset.source`:
 *
 * - começa com "#"          -> cor sólida (placeholder de imagem, sem mídia
 *                               real — usado hoje porque não temos assets
 *                               reais no projeto ainda);
 * - começa com "http(s)://" -> URL remota (CDN/storage), usada como está;
 * - qualquer outro valor    -> caminho relativo dentro de `public/`,
 *                               resolvido via `staticFile()` (convenção
 *                               padrão do Remotion para assets locais).
 *
 * Essa indireção existe de propósito: trocar "arquivo local" por "URL de
 * CDN/storage" no futuro é só trocar o valor de `source` — nenhum campo novo
 * no VideoEditSpec, nenhuma mudança no schema, nenhuma mudança nos
 * componentes que consomem o resultado.
 */
export function resolveAssetSource(source: string): ResolvedAssetSource {
  if (source.startsWith("#")) {
    return { kind: "color", value: source };
  }

  if (/^https?:\/\//.test(source)) {
    return { kind: "url", value: source };
  }

  return { kind: "url", value: staticFile(source) };
}
