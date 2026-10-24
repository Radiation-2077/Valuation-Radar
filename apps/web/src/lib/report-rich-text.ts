export type RichTextSegmentType = "text" | "strong" | "code" | "inline_math";

export interface RichTextSegment {
  type: RichTextSegmentType;
  value: string;
}

const INLINE_TOKEN = /(\*\*[^*]+\*\*|`[^`]+`|\\\(.+?\\\))/g;
const BRACED_LATEX = String.raw`\{(?:[^{}]|\{[^{}]*\})*\}`;
const LATEX_SCRIPT = String.raw`[_^]${BRACED_LATEX}`;
const BARE_LATEX = new RegExp(
  String.raw`(?<![A-Za-z0-9_])(?:\\[A-Za-z]+(?:${BRACED_LATEX})?|[A-Za-zΑ-ω][A-Za-z0-9]*?)${LATEX_SCRIPT}+(?![A-Za-z0-9_])`,
  "g",
);

function appendTextSegments(segments: RichTextSegment[], text: string): void {
  let cursor = 0;
  for (const match of text.matchAll(BARE_LATEX)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      segments.push({ type: "text", value: text.slice(cursor, index) });
    }
    segments.push({ type: "inline_math", value: match[0] });
    cursor = index + match[0].length;
  }
  if (cursor < text.length) {
    segments.push({ type: "text", value: text.slice(cursor) });
  }
}

export function parseInlineRichText(text: string): RichTextSegment[] {
  const segments: RichTextSegment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(INLINE_TOKEN)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      appendTextSegments(segments, text.slice(cursor, index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      segments.push({ type: "strong", value: token.slice(2, -2) });
    } else if (token.startsWith("`")) {
      segments.push({ type: "code", value: token.slice(1, -1) });
    } else {
      segments.push({ type: "inline_math", value: token.slice(2, -2) });
    }
    cursor = index + token.length;
  }
  if (cursor < text.length) {
    appendTextSegments(segments, text.slice(cursor));
  }
  return segments;
}
