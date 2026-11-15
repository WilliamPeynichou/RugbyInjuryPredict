import { describe, expect, it } from "vitest";

import { niceAxis } from "./axis";

describe("niceAxis", () => {
  it("arrondit à un pas régulier et part de 0", () => {
    const { domain, ticks } = niceAxis(41.3);
    expect(domain[0]).toBe(0);
    expect(domain[1]).toBeGreaterThanOrEqual(41.3);
    const steps = ticks.slice(1).map((v, i) => Number((v - ticks[i]).toFixed(6)));
    expect(new Set(steps).size).toBe(1);
  });

  it("reste valide pour une borne nulle", () => {
    expect(niceAxis(0).ticks).toEqual([0, 1]);
  });
});
