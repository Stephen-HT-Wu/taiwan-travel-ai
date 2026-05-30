import type { MapPlace } from "./mapTypes";
import { getMatchingKeyInContent } from "./mapTypes";

function isInsideMarkdownLink(content: string, index: number): boolean {
  let pos = 0;
  while (pos < content.length) {
    const start = content.indexOf("[", pos);
    if (start === -1) break;

    const textEnd = content.indexOf("]", start + 1);
    if (textEnd === -1) break;

    if (textEnd + 1 >= content.length || content[textEnd + 1] !== "(") {
      pos = start + 1;
      continue;
    }

    const urlEnd = content.indexOf(")", textEnd + 2);
    if (urlEnd === -1) {
      pos = start + 1;
      continue;
    }

    if (index >= start && index <= urlEnd) {
      return true;
    }

    pos = urlEnd + 1;
  }

  return false;
}

export function linkPlaceNames(content: string, places: MapPlace[]): string {
  if (!places.length || !content.trim()) return content;

  let linked = content;
  const sorted = [...places].sort((a, b) => b.name.length - a.name.length);

  for (const place of sorted) {
    const matchKey = getMatchingKeyInContent(place.name, content);
    if (!matchKey || matchKey.length < 2) continue;

    const escaped = matchKey.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    linked = linked.replace(new RegExp(escaped, "g"), (match, offset, string) => {
      if (isInsideMarkdownLink(string, offset)) return match;
      return `[${match}](#map-${encodeURIComponent(place.id)})`;
    });
  }

  return linked;
}
