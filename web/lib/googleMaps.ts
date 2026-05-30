import type { MapPlace } from "../components/mapTypes";

function googleMapsKeyword(place: Pick<MapPlace, "name" | "address">): string {
  const name = place.name.replace(/[（(][^）)]*[）)]/g, "").trim();
  if (place.address?.trim()) {
    return `${name} ${place.address}`.trim();
  }
  return name;
}

export function buildGoogleMapsUrl(
  place: Pick<MapPlace, "name" | "lat" | "lng" | "address">
): string {
  const lat = Number(place.lat);
  const lng = Number(place.lng);
  const keyword = googleMapsKeyword(place);
  // Search by keyword with map centered at coordinates (nearby fuzzy match).
  return `https://www.google.com/maps/search/${encodeURIComponent(keyword)}/@${lat},${lng},16z`;
}

export function openGoogleMaps(place: Pick<MapPlace, "name" | "lat" | "lng" | "address">): void {
  window.open(buildGoogleMapsUrl(place), "_blank", "noopener,noreferrer");
}
