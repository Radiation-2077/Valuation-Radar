import { describe, expect, it } from "vitest";

import { parseConicGradient } from "./report-detail";

describe("report detail helpers", () => {
  it("converts conic gradient ranges into donut segments", () => {
    const segments = parseConicGradient(
      "background:conic-gradient(#1d4ed8 0 21%,#3b82f6 21% 92%,#f59e0b 92% 99%,#dc2626 99% 100%)",
    );

    expect(segments).toEqual([
      { color: "#1d4ed8", value: 21 },
      { color: "#3b82f6", value: 71 },
      { color: "#f59e0b", value: 7 },
      { color: "#dc2626", value: 1 },
    ]);
  });

  it("returns no segments without a conic gradient", () => {
    expect(parseConicGradient("background:#57d6b1")).toEqual([]);
  });
});
