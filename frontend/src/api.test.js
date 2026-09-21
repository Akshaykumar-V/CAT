import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api.js";

afterEach(() => vi.restoreAllMocks());

describe("API client", () => {
  it("requests the performance dashboard from the FastAPI backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ overall: { accuracy: 72.5 } }),
      }),
    );

    await expect(api.performanceDashboard()).resolves.toEqual({
      overall: { accuracy: 72.5 },
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/performance/dashboard",
      expect.objectContaining({ headers: { "Content-Type": "application/json" } }),
    );
  });

  it("turns backend failures into a readable error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Practice session not found" }),
      }),
    );

    await expect(api.getSession(99)).rejects.toThrow("Practice session not found");
  });
});
