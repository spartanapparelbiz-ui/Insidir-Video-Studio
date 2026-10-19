// Aspect ratios. Templates are designed in a 1080x1920 space; for other frames the whole view
// is scaled so the important middle of that design fits, and backgrounds/overlays size
// themselves to the visible area (VW x VH in design units) so nothing is letterboxed.
import {getData} from './data';

export const DESIGN_W = 1080;
export const DESIGN_H = 1920;
// the band of the design every template keeps its content inside
const SAFE_H = 1700;

export function frame() {
  const d = getData();
  const scale = Math.min(d.width / DESIGN_W, d.height / SAFE_H, 1);
  return {scale, vw: d.width / scale, vh: d.height / scale, wide: d.width > d.height};
}
