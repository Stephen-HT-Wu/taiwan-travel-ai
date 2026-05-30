import type { MapPlace } from "./mapTypes";

function isInsideMarkdownLink(content: string, index: number): boolean {
  const before = content.slice(0, index);
  const openLink = before.lastIndexOf("[");
  const closeLink = before.lastIndexOf("]");
  const openDest = before.lastIndexOf("](");

  if (openDest === -1) return false;
  if (closeLink < openDest) return false;
  if (openLink === -1 || openLink > closeLink) return false;

  const after = content.slice(index);
  return after.includes(")");
}

export function linkPlaceNames(
  content: string,
  messagePlaces: MapPlace[],
  mapPlaces: MapPlace[] = []
): string {
  const linkSources = mapPlaces.length > 0 ? mapPlaces : messagePlaces;
  if (!linkSources.length) return content;

  let linked = content;
  const sorted = [...linkSources].sort((a, b) => b.name.length - a.name.length);

  for (const place of sorted) {
    const name = place.name.trim();
    if (name.length < 2) continue;

    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    linked = linked.replace(new RegExp(escaped, "g"), (match, offset, string) => {
      if (isInsideMarkdownLink(string, offset)) return match;
      return `[${name}](#map-${encodeURIComponent(place.id)})`;
    });
  }

  return linked;
}
