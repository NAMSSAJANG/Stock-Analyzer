import { describe, expect, it } from "vitest";
// This file tests the build boundary, not future product UI.
import config from "./next.config.mjs";

describe("static scaffold", () => {
  it("exports static assets with the engine version", () => {
    expect(config.output).toBe("export");
    expect(config.env.NEXT_PUBLIC_APP_VERSION).toMatch(/^\d+\.\d+\.\d+-a\.\d+$/);
  });
});
