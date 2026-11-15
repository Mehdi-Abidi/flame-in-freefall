import { describe, expect, it } from "vitest";
import { fallbackReply, isAboutTheRecord, localReply, suggestionsFor } from "./guide";
import { loadGuideData } from "./guideData";

const data = loadGuideData();

describe("the guide's own answers", () => {
  it("checks a habitat's cabin from the flight record", () => {
    const reply = localReply("Has a lunar base cabin been tested?", "/", data);
    expect(reply?.habitat?.id).toBe("lunar_base");
    expect(reply?.habitat?.rows.find((r) => r.phase === "solid")).toMatchObject({ verdict: "never", close: 0 });
    expect(reply?.link?.href).toBe("/lab/?habitat=lunar_base");
    expect(reply?.habitat?.rows.find((r) => r.phase === "gas")?.close).toBe(data.stats.lunarTests);
    expect(reply?.text).not.toContain("assumption");
    expect(localReply("has a Mars cabin been tested?", "/lab/", data)?.text).toContain("our assumption");
    expect(localReply("is the ISS safe?", "/", data)?.habitat?.rows.find((r) => r.phase === "solid")?.verdict).toBe("flown");
  });

  it("explains the page the visitor is on and points to the next one", () => {
    expect(localReply("What can I do on this page?", "/rank/", data)?.text).toContain("sliders");
    expect(localReply("help", "/lab/", data)?.link?.href).toBe("/evidence/");
    expect(localReply("help", "/", data)?.link?.href).toBe("/lab/");
  });

  it("takes the visitor to a page they name", () => {
    expect(localReply("take me to the cabin lab", "/", data)?.link?.href).toBe("/lab/");
    expect(localReply("open the ranking", "/", data)?.link?.href).toBe("/rank/");
  });

  it("states the size of the record from the data", () => {
    const text = localReply("How many tests are there?", "/", data)?.text ?? "";
    expect(text).toContain(`${data.stats.investigations} investigations`);
    expect(text).toContain("22.2%");
  });

  it("answers a greeting, however short, and small talk", () => {
    expect(localReply("hi", "/", data)?.text).toContain("Wisp");
    expect(localReply("hello hello hello hello", "/", data)?.text).toContain("Wisp");
    expect(localReply("Hi, how are you?", "/", data)?.text).toContain("floating");
    expect(localReply("who are you", "/", data)?.text).toContain("flame");
  });

  it("explains the words on the screen and adds what the screen shows", () => {
    const live = "The cabin lab is set to 35% oxygen at 50 kPa, solid fuels. It reads Never flown: 0 solid tests near this cabin.";
    const reply = localReply("why does it say never flown?", "/lab/", data, { live })?.text ?? "";
    expect(reply.startsWith(live)).toBe(true);
    expect(reply).toContain("10 or more tests");
    expect(localReply("what does to breathe mean", "/lab/", data)?.text).toContain("lungs");
    expect(localReply("sliders", "/lab/", data)?.text).toContain("box on the map");
  });

  it("answers a question that only says 'this' from the part of the page in view", () => {
    const section = "This is the gap, the main finding.";
    for (const question of ["What does this mean? Explain in simple terms:", "Yeah what is this about?", "I'm confused, explain that", "what am I looking at"]) {
      expect(localReply(question, "/", data, { section })?.text, question).toBe(section);
    }
    const live = "The cabin lab is set to 30% oxygen.";
    expect(localReply("what is this?", "/lab/", data, { section, live })?.text).toBe(`${section} ${live}`);
    expect(localReply("what is this?", "/rank/", data)?.text).toContain("sliders");
  });

  it("never sends a vague question to the record search, and jokes its way back when off topic", () => {
    expect(isAboutTheRecord("What does this mean? Explain in simple terms:")).toBe(false);
    expect(isAboutTheRecord("what is the capital of France?")).toBe(false);
    expect(isAboutTheRecord("CO2 or helium: which put out flames at lower oxygen?")).toBe(true);
    expect(isAboutTheRecord("what did BASS find?")).toBe(true);
    expect(localReply("what is the capital of France?", "/", data)).toBeNull();
    expect(fallbackReply("what is the capital of France?", "/", {})).toMatch(/flame|fire|orbit/);
    expect(fallbackReply("explain it simply", "/", { section: "This is the gap." })).toBe("This is the gap.");
    for (const question of ["what's the weather like today?", "what is it like outside", "help me with my homework", "how do I bake a cake"]) {
      expect(localReply(question, "/", data, { section: "This is the gap." }), question).toBeNull();
      expect(fallbackReply(question, "/", { section: "This is the gap." }), question).not.toContain("gap");
    }
  });

  it("leaves science questions to NASA's records", () => {
    expect(localReply("What did gravity change in SAFFIRE-II?", "/", data)).toBeNull();
    expect(localReply("What oxygen levels did BASS-II test?", "/", data)).toBeNull();
    expect(localReply("CO2 or helium: which put out flames at lower oxygen?", "/", data)).toBeNull();
    expect(localReply("Which investigations matter for a lunar base?", "/", data)).toBeNull();
    for (const path of ["/", "/lab/", "/rank/"]) for (const s of suggestionsFor(path).slice(0, 2)) expect(localReply(s, path, data)).not.toBeNull();
  });
});
