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

export async function ask(question: string, fetcher: typeof fetch = fetch): Promise<AskAnswer> {
  let res: Response;
  try {
    res = await fetcher(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new Error("Could not reach the API. Check your connection and try again.");
  }
  if (res.ok) return res.json();
  const body = await res.json().catch(() => null);
  const detail = typeof body?.detail === "string" ? body.detail : null;
  throw new Error(detail ?? (res.status === 422 ? "Questions must be 3 to 500 characters." : `The API answered ${res.status}. Try again.`));
}
