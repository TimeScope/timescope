import GeographicLib from "geographiclib-geodesic";
import { Cartesian3, Cartographic, Math as CesiumMath, PolylinePipeline } from "cesium";
import type { Point } from "./types";

export type TrackPoint = Pick<Point, "lat" | "lon" | "time" | "altitude">;

/** Follow the same shortest WGS84 geodesics used to draw Globe tracks. */
export class SpectateTrack {
  private index = -1;
  private arc?: ReturnType<typeof GeographicLib.Geodesic.WGS84.InverseLine>;
  private heading = 0;

  constructor(private readonly points: readonly TrackPoint[]) {}

  sample(time: number, projectedHeight?: (point: TrackPoint) => number) {
    const points = this.points;
    let lo = 0;
    let hi = points.length - 1;
    while (hi - lo > 1) {
      const middle = Math.floor((lo + hi) / 2);
      if (points[middle].time <= time) lo = middle;
      else hi = middle;
    }
    const a = points[lo];
    const b = points[hi];
    const fraction = (time - a.time) / (b.time - a.time);
    if (projectedHeight) {
      const leg = this.projectedLeg(a, b, fraction, projectedHeight);
      const east = leg.to.lon - leg.from.lon;
      const north = leg.to.lat - leg.from.lat;
      if (east || north) this.heading = CesiumMath.toDegrees(Math.atan2(east, north));
      return {
        a, b, time, fraction,
        lat: CesiumMath.lerp(leg.from.lat, leg.to.lat, leg.fraction),
        lon: CesiumMath.lerp(leg.from.lon, leg.to.lon, leg.fraction),
        heading: this.heading,
      };
    }
    if (lo !== this.index) {
      this.index = lo;
      this.arc = GeographicLib.Geodesic.WGS84.InverseLine(a.lat, a.lon, b.lat, b.lon);
    }
    const arc = this.arc!;
    const position = arc.Position(arc.s13 * fraction);
    if (arc.s13 > 0) this.heading = position.azi2!;
    return {
      a, b, time, fraction,
      lat: position.lat2!,
      lon: position.lon2!,
      heading: this.heading,
    };
  }

  private projectedLeg(
    a: TrackPoint,
    b: TrackPoint,
    fraction: number,
    height: (point: TrackPoint) => number,
  ) {
    if (Math.abs(b.lon - a.lon) <= 180) return { from: a, to: b, fraction };
    const from = Cartesian3.fromDegrees(a.lon, a.lat, height(a));
    const to = Cartesian3.fromDegrees(b.lon, b.lat, height(b));
    // PolylineCollection splits the ECEF chord before projecting each leg.
    const { positions } = PolylinePipeline.wrapLongitude([from, to]) as { positions: Cartesian3[] };
    const split = from.y / (from.y - to.y);
    if (positions.length !== 4 || !(split > 0 && split < 1))
      return { from: a, to: b, fraction };
    const firstLeg = fraction < split;
    const seam = Cartographic.fromCartesian(positions[firstLeg ? 1 : 2]);
    const point = {
      lat: CesiumMath.toDegrees(seam.latitude),
      lon: CesiumMath.toDegrees(seam.longitude),
    };
    return firstLeg
      ? { from: a, to: point, fraction: fraction / split }
      : { from: point, to: b, fraction: (fraction - split) / (1 - split) };
  }
}
