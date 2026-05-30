export type MapPlace = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  address?: string;
  type: "attraction" | "restaurant";
};

export type MapPlaceInput = Omit<MapPlace, "id">;
