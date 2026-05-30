export type MapPlace = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  address?: string;
  type: "attraction" | "restaurant";
};

export type MapPlaceInput = Omit<MapPlace, "id">;

export type MapFocusTarget = {
  lat: number;
  lng: number;
  nonce: number;
};

export function normalizeCoords(place: MapPlaceInput): MapPlaceInput {
  return {
    ...place,
    lat: Number(place.lat),
    lng: Number(place.lng),
  };
}

export function makePlaceId(place: Pick<MapPlace, "name" | "lat" | "lng">): string {
  const lat = Number(place.lat);
  const lng = Number(place.lng);
  return `${lat.toFixed(5)}-${lng.toFixed(5)}-${place.name}`;
}

export function toMapPlace(place: MapPlaceInput): MapPlace {
  const normalized = normalizeCoords(place);
  return {
    ...normalized,
    id: makePlaceId(normalized),
  };
}

export function mergeMapPlaces(existing: MapPlace[], incoming: MapPlaceInput[]): MapPlace[] {
  const merged = [...existing];

  for (const raw of incoming) {
    const place = normalizeCoords(raw);
    const id = makePlaceId(place);
    if (merged.some((item) => item.id === id)) continue;
    merged.push({ ...place, id });
  }

  return merged;
}

function addTaiwanScriptVariants(value: string, keys: Set<string>): void {
  if (value.includes("臺")) keys.add(value.replace(/臺/g, "台"));
  if (value.includes("台")) keys.add(value.replace(/台/g, "臺"));
}

function getPlaceMatchKeys(name: string): string[] {
  const trimmed = name.trim();
  const keys = new Set<string>();
  if (trimmed.length >= 2) keys.add(trimmed);

  const withoutParens = trimmed.replace(/[（(][^）)]*[）)]/g, "").trim();
  if (withoutParens.length >= 2) keys.add(withoutParens);

  const parenMatch = trimmed.match(/[（(]([^）)]+)[）)]/);
  if (parenMatch && parenMatch[1].trim().length >= 2) {
    keys.add(parenMatch[1].trim());
  }

  for (const key of [...keys]) {
    addTaiwanScriptVariants(key, keys);
  }

  return [...keys];
}

function contentIncludesKey(content: string, key: string): boolean {
  if (content.includes(key)) return true;
  if (key.includes("臺")) return content.includes(key.replace(/臺/g, "台"));
  if (key.includes("台")) return content.includes(key.replace(/台/g, "臺"));
  return false;
}

export function getMatchingKeyInContent(placeName: string, content: string): string | null {
  if (!content.trim()) return null;
  const keys = getPlaceMatchKeys(placeName).sort((a, b) => b.length - a.length);
  for (const key of keys) {
    if (contentIncludesKey(content, key)) return key;
  }

  const core = placeName.replace(/[（(][^）)]*[）)]/g, "").trim();
  for (let len = core.length; len >= 3; len--) {
    for (let i = 0; i <= core.length - len; i++) {
      const slice = core.slice(i, i + len);
      if (contentIncludesKey(content, slice)) return slice;
    }
  }

  return null;
}

export function resolveDisplayPlaces(content: string, pool: MapPlace[]): MapPlace[] {
  if (!pool.length) return [];
  const mentioned = filterPlacesMentionedInText(content, pool);
  return mentioned.length > 0 ? mentioned : pool;
}

export function isPlaceMentionedInText(placeName: string, content: string): boolean {
  return getMatchingKeyInContent(placeName, content) !== null;
}

function dedupePlacesByLocation(places: MapPlace[]): MapPlace[] {
  const byLocation = new Map<string, MapPlace>();

  for (const place of places) {
    const key = `${Number(place.lat).toFixed(4)},${Number(place.lng).toFixed(4)}`;
    const existing = byLocation.get(key);
    if (!existing || place.name.length < existing.name.length) {
      byLocation.set(key, place);
    }
  }

  return [...byLocation.values()];
}

export function filterPlacesMentionedInText(content: string, places: MapPlace[]): MapPlace[] {
  const mentioned = places.filter((place) => isPlaceMentionedInText(place.name, content));
  return dedupePlacesByLocation(mentioned);
}

export function resolvePlaceByLink(
  linkId: string,
  label: string,
  messagePlaces: MapPlace[],
  mapPlaces: MapPlace[]
): MapPlace | undefined {
  const decodedId = decodeURIComponent(linkId);
  const trimmedLabel = label.trim();

  return (
    mapPlaces.find((place) => place.id === decodedId) ??
    messagePlaces.find((place) => place.id === decodedId) ??
    mapPlaces.find((place) => place.name === trimmedLabel) ??
    messagePlaces.find((place) => place.name === trimmedLabel)
  );
}
