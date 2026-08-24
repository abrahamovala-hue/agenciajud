/** Converte segundos (unidade do VideoEditSpec) para frames (unidade do Remotion). */
export const secondsToFrames = (seconds: number, fps: number): number => {
  return Math.round(seconds * fps);
};
