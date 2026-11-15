import { describe, expect, it } from "vitest";
import { localReply, offTopicReply, suggestionsFor } from "./guide";
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
    expect(localReply("Hi, how are you?", "/", data)?.text).toContain("steady");
    expect(localReply("who are you", "/", data)?.text).toContain("guide");
  });

  it("explains the words on the screen and adds what the screen shows", () => {
    const shown = "Cabin lab is set to 35% oxygen at 50 kPa, solid fuels. It reads Never flown: 0 solid tests near this cabin.";
    const reply = localReply("why does it say never flown?", "/lab/", data, shown)?.text ?? "";
    expect(reply.startsWith(shown)).toBe(true);
    expect(reply).toContain("10 or more tests");
    expect(localReply("what does to breathe mean", "/lab/", data)?.text).toContain("lungs");
    expect(localReply("sliders", "/lab/", data)?.text).toContain("box on the map");
    expect(localReply("What is this page showing?", "/lab/", data, shown)?.text).toContain(shown);
  });

  it("jokes its way back when a question is outside the record", () => {
    expect(offTopicReply("what is the capital of France?")).toMatch(/flame|gravity|record/);
    expect(localReply("what is the capital of France?", "/", data)).toBeNull();
  });

  it("leaves science questions to NASA's records", () => {
    expect(localReply("What did gravity change in SAFFIRE-II?", "/", data)).toBeNull();
    expect(localReply("What oxygen levels did BASS-II test?", "/", data)).toBeNull();
    expect(localReply("CO2 or helium: which put out flames at lower oxygen?", "/", data)).toBeNull();
    expect(localReply("Which investigations matter for a lunar base?", "/", data)).toBeNull();
    for (const path of ["/", "/lab/", "/rank/"]) for (const s of suggestionsFor(path).slice(0, 2)) expect(localReply(s, path, data)).not.toBeNull();
  });
});
