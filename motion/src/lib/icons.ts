// Hand-drawn doodle icons (Rough.js), drawn in a 240 x 240 box centred on 0,0.
import {R, arrow, type RoughStyle, type Stroke} from './rough';

type IconFn = (s: RoughStyle, accent: string) => Stroke[];

const dotsPerson = (x: number, y: number, s: RoughStyle, k = 1): Stroke[] => [
  ...R.circle(x, y - 46 * k, 26 * k, {...s, fill: s.stroke, fillStyle: 'solid', seed: 11}),
  ...R.arc(x, y + 6 * k, 70 * k, 80 * k, Math.PI, Math.PI * 2, {...s, seed: 12}),
];

export const ICONS: Record<string, IconFn> = {
  document: s => [
    ...R.poly([[-70, -100], [40, -100], [80, -60], [80, 100], [-70, 100]], s),
    ...R.lines([[40, -100], [40, -60], [80, -60]], {...s, seed: 21}),
    ...R.line(-40, -30, 45, -30, {...s, seed: 22}),
    ...R.line(-40, 10, 45, 10, {...s, seed: 23}),
    ...R.line(-40, 50, 15, 50, {...s, seed: 24}),
  ],
  form: (s, a) => [
    ...R.rect(-80, -105, 160, 210, s),
    ...R.rect(-55, -80, 50, 30, {...s, stroke: a, seed: 31}),
    ...R.line(10, -65, 55, -65, {...s, seed: 32}),
    ...R.line(-55, -20, 55, -20, {...s, seed: 33}),
    ...R.line(-55, 15, 55, 15, {...s, seed: 34}),
    ...R.line(-55, 50, 20, 50, {...s, seed: 35}),
    ...R.lines([[15, 80], [32, 95], [62, 62]], {...s, stroke: a, seed: 36}),
  ],
  magnifier: (s, a) => [
    ...R.circle(-25, -25, 140, s),
    ...R.circle(-25, -25, 100, {...s, stroke: a, width: 3, seed: 41, roughness: 2}),
    ...R.line(25, 25, 95, 95, {...s, width: (s.width ?? 6) * 2.2, seed: 42}),
  ],
  clock: (s, a) => [
    ...R.circle(0, 0, 200, s),
    ...R.line(0, 0, 0, -65, {...s, seed: 51}),
    ...R.line(0, 0, 50, 25, {...s, stroke: a, seed: 52}),
    ...R.circle(0, 0, 14, {...s, fill: s.stroke, fillStyle: 'solid', seed: 53}),
  ],
  calendar: (s, a) => [
    ...R.rect(-100, -85, 200, 180, s),
    ...R.line(-100, -40, 100, -40, {...s, seed: 61}),
    ...R.line(-55, -105, -55, -65, {...s, seed: 62}),
    ...R.line(55, -105, 55, -65, {...s, seed: 63}),
    ...[-55, 0, 55].flatMap((x, i) => R.rect(x - 15, -15, 30, 26, {...s, width: 3, seed: 64 + i})),
    ...[-55, 0].flatMap((x, i) => R.rect(x - 15, 35, 30, 26, {...s, width: 3, seed: 68 + i})),
    ...R.circle(55, 48, 46, {...s, stroke: a, seed: 70}),
  ],
  bell: (s, a) => [
    ...R.path('M -70 50 C -60 30 -60 -10 -55 -35 C -45 -80 45 -80 55 -35 C 60 -10 60 30 70 50 Z', s),
    ...R.line(-85, 52, 85, 52, {...s, seed: 81}),
    ...R.circle(0, 75, 34, {...s, seed: 82}),
    ...R.arc(0, -10, 230, 200, -2.5, -1.9, {...s, stroke: a, seed: 83}),
    ...R.arc(0, -10, 230, 200, -1.25, -0.65, {...s, stroke: a, seed: 84}),
  ],
  link: s => [
    ...R.path('M -20 -45 L 15 -80 C 40 -105 80 -65 55 -40 L 20 -5', s),
    ...R.path('M 20 45 L -15 80 C -40 105 -80 65 -55 40 L -20 5', {...s, seed: 91}),
    ...R.line(-30, 30, 30, -30, {...s, seed: 92}),
  ],
  check: (s, a) => [...R.lines([[-80, 0], [-25, 60], [85, -70]], {...s, stroke: a, width: (s.width ?? 6) * 2})],
  cross: (s, a) => [
    ...R.line(-75, -75, 75, 75, {...s, stroke: a, width: (s.width ?? 6) * 2}),
    ...R.line(75, -75, -75, 75, {...s, stroke: a, width: (s.width ?? 6) * 2, seed: 101}),
  ],
  building: s => [
    ...R.poly([[-110, -40], [0, -105], [110, -40]], s),
    ...R.line(-110, -40, 110, -40, {...s, seed: 111}),
    ...[-75, -25, 25, 75].flatMap((x, i) => R.line(x, -25, x, 70, {...s, seed: 112 + i})),
    ...R.rect(-115, 75, 230, 22, {...s, seed: 117}),
  ],
  chart: (s, a) => [
    ...R.lines([[-100, -100], [-100, 95], [105, 95]], s),
    ...R.rect(-75, 25, 34, 70, {...s, fill: s.stroke, seed: 121}),
    ...R.rect(-25, -15, 34, 110, {...s, fill: s.stroke, seed: 122}),
    ...R.rect(25, -55, 34, 150, {...s, fill: a, stroke: a, seed: 123}),
  ],
  phone: (s, a) => [
    ...R.rect(-62, -110, 124, 220, s),
    ...R.rect(-48, -85, 96, 160, {...s, stroke: a, width: 3, seed: 131}),
    ...R.circle(0, 92, 14, {...s, seed: 132}),
  ],
  laptop: (s, a) => [
    ...R.rect(-95, -85, 190, 125, s),
    ...R.rect(-78, -70, 156, 95, {...s, stroke: a, width: 3, seed: 141}),
    ...R.poly([[-115, 48], [115, 48], [135, 85], [-135, 85]], {...s, seed: 142}),
  ],
  eye: (s, a) => [
    ...R.path('M -115 0 C -60 -75 60 -75 115 0 C 60 75 -60 75 -115 0 Z', s),
    ...R.circle(0, 0, 80, {...s, stroke: a, seed: 151}),
    ...R.circle(0, 0, 30, {...s, fill: s.stroke, fillStyle: 'solid', seed: 152}),
  ],
  lock: (s, a) => [
    ...R.rect(-75, -15, 150, 115, s),
    ...R.arc(0, -15, 110, 150, Math.PI, Math.PI * 2, {...s, seed: 161}),
    ...R.circle(0, 35, 26, {...s, stroke: a, seed: 162}),
    ...R.line(0, 48, 0, 72, {...s, stroke: a, seed: 163}),
  ],
  people: s => [...dotsPerson(-70, 40, s, 0.8), ...dotsPerson(70, 40, {...s, seed: 171}, 0.8), ...dotsPerson(0, 10, {...s, seed: 172}, 1)],
  cabinet: (s, a) => [
    ...R.rect(-80, -110, 160, 220, s),
    ...[-75, -5, 65].flatMap((y, i) => [
      ...R.line(-80, y + 35, 80, y + 35, {...s, seed: 181 + i}),
      ...R.line(-20, y, 20, y, {...s, stroke: i === 1 ? a : s.stroke, seed: 185 + i}),
    ]),
  ],
  question: (s, a) => [
    ...R.path('M -55 -45 C -55 -115 60 -115 60 -50 C 60 -5 5 0 5 45', {...s, width: (s.width ?? 6) * 1.6}),
    ...R.circle(5, 95, 26, {...s, fill: a, stroke: a, fillStyle: 'solid', seed: 191}),
  ],
  bulb: (s, a) => [
    ...R.path('M -40 50 C -45 10 -85 -10 -80 -55 C -75 -115 75 -115 80 -55 C 85 -10 45 10 40 50 Z', s),
    ...R.line(-35, 75, 35, 75, {...s, seed: 201}),
    ...R.line(-25, 98, 25, 98, {...s, seed: 202}),
    ...R.line(0, -120, 0, -150, {...s, stroke: a, seed: 203}),
    ...R.line(-95, -95, -115, -115, {...s, stroke: a, seed: 204}),
    ...R.line(95, -95, 115, -115, {...s, stroke: a, seed: 205}),
  ],
  arrow: (s, a) => arrow(-110, 40, 110, -20, {...s, stroke: a}),
  tag: (s, a) => [
    ...R.poly([[-100, -45], [40, -45], [105, 0], [40, 45], [-100, 45]], s),
    ...R.circle(45, 0, 22, {...s, stroke: a, seed: 211}),
  ],
  list: (s, a) => [
    ...[-60, 0, 60].flatMap((y, i) => [
      ...R.lines([[-100, y], [-85, y + 15], [-60, y - 15]], {...s, stroke: a, seed: 221 + i}),
      ...R.line(-35, y, 100, y, {...s, seed: 225 + i}),
    ]),
  ],
  pen: (s, a) => [
    ...R.poly([[-90, 70], [50, -70], [80, -40], [-60, 100]], s),
    ...R.lines([[-90, 70], [-105, 115], [-60, 100]], {...s, stroke: a, seed: 231}),
  ],
};

export const ICON_NAMES = Object.keys(ICONS);

export function icon(name: string, style: RoughStyle, accent: string): Stroke[] {
  return (ICONS[name] ?? ICONS.document)(style, accent);
}
