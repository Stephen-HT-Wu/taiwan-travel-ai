"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import type { MapPlace } from "./mapTypes";
import styles from "./MapPanel.module.css";

type MapPanelProps = {
  places: MapPlace[];
};

const TYPE_COLORS: Record<MapPlace["type"], string> = {
  attraction: "#3b82f6",
  restaurant: "#f59e0b",
};

const TYPE_LABELS: Record<MapPlace["type"], string> = {
  attraction: "景點",
  restaurant: "餐廳",
};

export default function MapPanel({ places }: MapPanelProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<import("leaflet").Map | null>(null);
  const markersLayerRef = useRef<import("leaflet").LayerGroup | null>(null);

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
    }

    initMap();

    return () => {
      cancelled = true;
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

      if (places.length === 0) return;

      const bounds = L.latLngBounds([]);

      for (const place of places) {
        const color = TYPE_COLORS[place.type];
        const marker = L.circleMarker([place.lat, place.lng], {
          radius: 9,
          color,
          weight: 2,
          fillColor: color,
          fillOpacity: 0.85,
        });

        marker.bindPopup(
          `<strong>${place.name}</strong><br/>` +
            `<span style="opacity:0.8">${TYPE_LABELS[place.type]}</span>` +
            (place.address ? `<br/>${place.address}` : "")
        );
        marker.addTo(layer);
        bounds.extend([place.lat, place.lng]);
      }

      if (places.length === 1) {
        map.setView([places[0].lat, places[0].lng], 13);
      } else {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
      }
    }

    updateMarkers();
  }, [places]);

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
      </div>

      <div ref={mapRef} className={styles.map} />
    </div>
  );
}
