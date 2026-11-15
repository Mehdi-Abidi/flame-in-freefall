/** What the page is showing right now, in one plain sentence, so the guide can talk about it. Pages that change as
 * the visitor works (the cabin lab) keep this up to date. Other pages leave it empty and the guide uses the page's own description. */
let current = "";

export const screen = {
  set(text: string) {
    current = text;
  },
  get() {
    return current;
  },
};
