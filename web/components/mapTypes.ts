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
