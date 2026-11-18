// Visual style of map clusters and heat layer (010, data-model: ClusterStyle).

export interface ClusterStyle {
  size: number;
  level: 1 | 2 | 3 | 4;
}

export function clusterStyle(count: number): ClusterStyle {
  if (count < 10) return { size: 34, level: 1 };
  if (count < 50) return { size: 44, level: 2 };
  if (count < 200) return { size: 54, level: 3 };
  return { size: 64, level: 4 };
}

export const HEAT_GRADIENT: Record<number, string> = {
  0.2: '#ffe066',
  0.4: '#ffb347',
  0.6: '#ff7a3d',
  0.8: '#e03b2e',
  1.0: '#8b0f1c',
};

export const HEAT_OPTIONS = {
  radius: 30,
  blur: 20,
  minOpacity: 0.45,
  maxZoom: 6,
} as const;

/** Radius of the halo drawn behind single events, from the marker radius. */
export function haloRadius(radius: number): number {
  return radius * 2;
}
