import { describe, expect, it } from "vitest";
import { ask, splitCitations } from "./ask";

describe("splitCitations", () => {
  it("links every accession in grouped and bare citations", () => {
    const parts = splitCitations("Up to **22 % O₂** [PSI-26, PSI-25].\n* PSI-62 spread");
    expect(parts.filter((_, i) => i % 2)).toEqual(["PSI-26", "PSI-25", "PSI-62"]);
    expect(parts.join("")).toBe("Up to 22 % O₂ [PSI-26, PSI-25].\n• PSI-62 spread");
  });
});

const reply = (status: number, body: unknown) => (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;

describe("ask", () => {
  it("returns the answer on success", async () => {
    const answer = { answer: "Helium [PSI-69]", covered: true, citations: ["PSI-69"], sources: [] };
    await expect(ask("q?", reply(200, answer))).resolves.toEqual(answer);
  });

  it("shows the server's message for rate limits and outages", async () => {
    await expect(ask("q?", reply(429, { detail: "Too many questions from you. Try again in 30 s." }))).rejects.toThrow("Try again in 30 s.");
  });

  it("explains validation errors instead of dumping them", async () => {
    await expect(ask("q", reply(422, { detail: [{ msg: "too short" }] }))).rejects.toThrow("3 to 500 characters");
  });

  it("explains an unreadable answer instead of showing a parser error", async () => {
    const garbled = (async () => new Response("<html>oops</html>", { status: 200 })) as unknown as typeof fetch;
    await expect(ask("q?", garbled)).rejects.toThrow("could not be read");
  });

  it("reports network failures", async () => {
    const down = (async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;
    await expect(ask("q?", down)).rejects.toThrow("Could not reach the API");
  });
});
