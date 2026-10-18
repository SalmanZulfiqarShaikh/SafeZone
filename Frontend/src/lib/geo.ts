/**
 * A flat projection of Karachi into 0–100 space.
 *
 * Over a city thirty kilometres across, treating latitude and longitude as
 * linear is well inside the error of the area centres in Backend/data/areas.py,
 * which are rough neighbourhood midpoints rather than survey data. The map is
 * a schematic for choosing and reading cases, never a navigation surface — the
 * responder page hands off to a real maps app for that.
 *
 * Geography in MapBase is drawn in this same space, so a pin at a given
 * lat/lng lands where that place actually is relative to the coastline.
 */

export const BOUNDS = {
  west: 66.94,
  east: 67.24,
  south: 24.76,
  north: 25.06,
} as const;

const SPAN_LNG = BOUNDS.east - BOUNDS.west;
const SPAN_LAT = BOUNDS.north - BOUNDS.south;

const clamp = (value: number) => Math.min(99.2, Math.max(0.8, value));

export interface Point {
  x: number;
  y: number;
}

export function project(
  lat: number | null | undefined,
  lng: number | null | undefined,
): Point | null {
  if (typeof lat !== "number" || typeof lng !== "number") return null;
  if (Number.isNaN(lat) || Number.isNaN(lng)) return null;
  return {
    x: clamp(((lng - BOUNDS.west) / SPAN_LNG) * 100),
    y: clamp(((BOUNDS.north - lat) / SPAN_LAT) * 100),
  };
}

/** Straight-line distance in kilometres. Matches the backend's nearest-first
 *  matching, which is also straight-line rather than routed travel time — a
 *  trade-off named in the README. */
export function distanceKm(a: Point | null, b: Point | null): number | null {
  if (!a || !b) return null;
  const dx = ((a.x - b.x) / 100) * SPAN_LNG * 101.3; // km per degree lng at 24.9°N
  const dy = ((a.y - b.y) / 100) * SPAN_LAT * 110.9; // km per degree lat
  return Math.sqrt(dx * dx + dy * dy);
}
