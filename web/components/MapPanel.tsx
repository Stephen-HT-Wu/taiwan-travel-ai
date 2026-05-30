"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import type { MapFocusTarget, MapPlace } from "./mapTypes";
import styles from "./MapPanel.module.css";

type MapPanelProps = {
  places: MapPlace[];
  selectedPlaceId?: string | null;
  focusTarget?: MapFocusTarget | null;
  onPlaceSelect?: (place: MapPlace) => void;
};

const TYPE_COLORS: Record<MapPlace["type"], string> = {
  attraction: "#3b82f6",
  restaurant: "#f59e0b",
};

const SELECTED_ZOOM = 16;

export default function MapPanel({
  places,
  selectedPlaceId = null,
  focusTarget = null,
  onPlaceSelect,
}: MapPanelProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<import("leaflet").Map | null>(null);
  const markersLayerRef = useRef<import("leaflet").LayerGroup | null>(null);
  const onPlaceSelectRef = useRef(onPlaceSelect);
  const lastPlacesKeyRef = useRef("");
  const mapReadyRef = useRef(false);

  onPlaceSelectRef.current = onPlaceSelect;

  useEffect(() => {
    let cancelled = false;

    async function initMap() {
      const L = (await import("leaflet")).default;

      if (cancelled || !mapRef.current || mapInstanceRef.current) return;

      const map = L.map(mapRef.current, {
        center: [23.7, 120.9],
        zoom: 7,
        zoomControl: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
        maxZoom: 19,
      }).addTo(map);

      mapInstanceRef.current = map;
      markersLayerRef.current = L.layerGroup().addTo(map);
      mapReadyRef.current = true;
      map.invalidateSize();
    }

    initMap();

    return () => {
      cancelled = true;
      mapReadyRef.current = false;
      mapInstanceRef.current?.remove();
      mapInstanceRef.current = null;
      markersLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    async function updateMarkers() {
      const map = mapInstanceRef.current;
      const layer = markersLayerRef.current;
      if (!map || !layer) return;

      const L = (await import("leaflet")).default;
      layer.clearLayers();

      if (places.length === 0) {
        lastPlacesKeyRef.current = "";
        return;
      }

      const placesKey = places.map((place) => place.id).join("|");
      const placesChanged = placesKey !== lastPlacesKeyRef.current;
      lastPlacesKeyRef.current = placesKey;

      const bounds = L.latLngBounds([]);

      for (const place of places) {
        const color = TYPE_COLORS[place.type];
        const isSelected = place.id === selectedPlaceId;
        const marker = L.circleMarker([place.lat, place.lng], {
          radius: isSelected ? 13 : 9,
          color: isSelected ? "#ffffff" : color,
          weight: isSelected ? 3 : 2,
          fillColor: color,
          fillOpacity: isSelected ? 1 : 0.85,
        });

        marker.bindTooltip(place.name, {
          permanent: true,
          direction: "top",
          offset: L.point(0, -12),
          className: styles.markerTooltip,
        });

        marker.on("click", () => {
          onPlaceSelectRef.current?.(place);
        });

        marker.addTo(layer);
        bounds.extend([place.lat, place.lng]);
      }

      if (!selectedPlaceId && placesChanged) {
        map.invalidateSize();
        if (places.length === 1) {
          map.setView([places[0].lat, places[0].lng], 13);
        } else {
          map.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });
        }
      }
    }

    updateMarkers();
  }, [places, selectedPlaceId]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !focusTarget || !mapReadyRef.current) return;

    map.invalidateSize();
    const frame = requestAnimationFrame(() => {
      map.flyTo([focusTarget.lat, focusTarget.lng], SELECTED_ZOOM, {
        animate: true,
        duration: 0.45,
      });
    });

    return () => cancelAnimationFrame(frame);
  }, [focusTarget?.nonce]);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>地圖</span>
        <span className={styles.count}>
          {places.length > 0 ? `${places.length} 個地點` : "查詢景點或餐廳後顯示"}
        </span>
      </div>

      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.dot} style={{ background: TYPE_COLORS.attraction }} />
          景點
        </span>
        <span className={styles.legendItem}>
          <span className={styles.dot} style={{ background: TYPE_COLORS.restaurant }} />
          餐廳
        </span>
        {places.length > 0 && (
          <span className={styles.legendHint}>點選標記或內文地名可互相對應</span>
        )}
      </div>

      <div ref={mapRef} className={styles.map} />
    </div>
  );
}
