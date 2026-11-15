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
