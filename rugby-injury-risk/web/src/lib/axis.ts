/** Borne haute « ronde » et graduations régulières pour un axe partant de 0. */
export function niceAxis(max: number, steps = 5): { domain: [number, number]; ticks: number[] } {
  if (!(max > 0)) return { domain: [0, 1], ticks: [0, 1] };
  const raw = max / steps;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
  return { domain: [0, top], ticks };
}
