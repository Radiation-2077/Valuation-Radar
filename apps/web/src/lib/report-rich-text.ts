export type RichTextSegmentType = "text" | "strong" | "code" | "inline_math";

export interface RichTextSegment {
  type: RichTextSegmentType;
  value: string;
}

const INLINE_TOKEN = /(\*\*[^*]+\*\*|`[^`]+`|\\\(.+?\\\))/g;

export function parseInlineRichText(text: string): RichTextSegment[] {
  const segments: RichTextSegment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(INLINE_TOKEN)) {
    const index = match.index ?? 0;
    if (index > cursor) {
      segments.push({ type: "text", value: text.slice(cursor, index) });
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
    segments.push({ type: "text", value: text.slice(cursor) });
  }
  return segments;
}
