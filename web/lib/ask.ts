export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://flame-in-freefall-api.onrender.com";

export interface AskSource {
  accession: string;
  acronym: string;
  field: string;
  text: string;
  score: number;
}

export interface AskAnswer {
  answer: string;
  covered: boolean;
  citations: string[];
  sources: AskSource[];
}

export function splitCitations(text: string): string[] {
  return text.replace(/\*\*/g, "").replace(/^\* /gm, "• ").split(/(PSI-\d+)/);
}

const TIMEOUT_MS = 90_000;

export async function ask(question: string, fetcher: typeof fetch = fetch): Promise<AskAnswer> {
  let res: Response;
  try {
    res = await fetcher(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    if ((error as Error)?.name === "TimeoutError") throw new Error("The API took too long to answer. Try again in a minute.");
    throw new Error("Could not reach the API. Check your connection and try again.");
  }
  if (res.ok) {
    try {
      return await res.json();
    } catch {
      throw new Error("The API sent an answer that could not be read. Try again.");
    }
  }
  const body = await res.json().catch(() => null);
  const detail = typeof body?.detail === "string" ? body.detail : null;
  throw new Error(detail ?? (res.status === 422 ? "Questions must be 3 to 500 characters." : `The API answered ${res.status}. Try again.`));
}

export interface GuideAnswer {
  answer: string;
  citations: string[];
}

/** Asks Wisp's own endpoint, sending the page and what it shows. Returns null when the API in use is older and has no
 * /guide yet, so the caller can fall back to /ask. */
export async function askGuide(question: string, page: string, screenText: string, fetcher: typeof fetch = fetch): Promise<GuideAnswer | null> {
  let res: Response;
  try {
    res = await fetcher(`${API_URL}/guide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question.slice(0, 500), page: page.slice(0, 80), screen: screenText.slice(0, 2000) }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    if ((error as Error)?.name === "TimeoutError") throw new Error("The API took too long to answer. Try again in a minute.");
    throw new Error("Could not reach the API. Check your connection and try again.");
  }
  if (res.status === 404 || res.status === 405) return null;
  if (res.ok) {
    const body = (await res.json().catch(() => null)) as GuideAnswer | null;
    if (body && typeof body.answer === "string") return { answer: body.answer, citations: Array.isArray(body.citations) ? body.citations : [] };
    throw new Error("The API sent an answer that could not be read. Try again.");
  }
  const body = await res.json().catch(() => null);
  throw new Error(typeof body?.detail === "string" ? body.detail : `The API answered ${res.status}. Try again.`);
}
