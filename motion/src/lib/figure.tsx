// The Insidir dot figure: the "i" of the Insidir favicon (web/assets/icons/favicon.svg)
// read as a little person. Head dot, a row of three (shoulders and arms), a dotted body
// and a row of three feet. Poses move the dots; every pose keeps the same 12 dots.
import {Circle, Node} from '@motion-canvas/2d';
import {all, createRef, easeInOutCubic, easeOutBack, loop, type Reference, type ThreadGenerator, waitFor} from '@motion-canvas/core';
import type {Word} from './data';
import {until} from './timing';

type XY = [number, number];
// Order: head, neck, armL1, armL2, armR1, armR2, body1, body2, body3, footL, footC, footR
// Units are favicon pixels, origin at the middle foot, y up is negative.
const STAND: XY[] = [[0, -36], [0, -24], [-6, -24], [-6, -24], [6, -24], [6, -24], [0, -18], [0, -12], [0, -6], [-6, 0], [0, 0], [6, 0]];

function pose(changes: Partial<Record<number, XY>>): XY[] {
  return STAND.map((p, i) => changes[i] ?? p);
}

export const POSES: Record<string, XY[]> = {
  stand: STAND,
  wave: pose({4: [6.5, -28], 5: [11.5, -33]}),
  point: pose({4: [6.5, -26], 5: [13, -28]}),
  pointleft: pose({2: [-6.5, -26], 3: [-13, -28]}),
  pointup: pose({4: [5, -30], 5: [8, -36.5]}),
  think: pose({0: [1, -36], 4: [5, -20], 5: [3, -29.5]}),
  shrug: pose({0: [0, -35], 2: [-6, -27], 3: [-10.5, -31], 4: [6, -27], 5: [10.5, -31]}),
  cheer: pose({2: [-6.5, -28], 3: [-12, -32.5], 4: [6.5, -28], 5: [12, -32.5], 9: [-7, 0], 11: [7, 0]}),
  explain: pose({2: [-6, -22], 3: [-11.5, -19], 4: [6, -22], 5: [11.5, -19]}),
  walk: pose({9: [-4.5, -1], 11: [7.5, 0], 3: [-8, -21], 5: [8, -27]}),
  sad: pose({0: [0, -34.5], 2: [-5.5, -21], 3: [-7, -16], 4: [5.5, -21], 5: [7, -16]}),
};

export const POSE_NAMES = Object.keys(POSES);

export interface DotFigure {
  root: Reference<Node>;
  dots: Reference<Circle>[];
  unit: number;
}

export function makeFigure(color: string, unit = 11, x = 0, y = 0): [Node, DotFigure] {
  const root = createRef<Node>();
  const dots = STAND.map(() => createRef<Circle>());
  const node = (
    <Node ref={root} x={x} y={y}>
      {STAND.map((p, i) => (
        <Circle
          ref={dots[i]}
          x={p[0] * unit}
          y={p[1] * unit}
          size={(i === 0 ? 8.4 : 6.2) * unit}
          fill={color}
        />
      ))}
    </Node>
  ) as Node;
  return [node, {root, dots, unit}];
}

export function* setPose(fig: DotFigure, name: string, seconds = 0.35): ThreadGenerator {
  const target = POSES[name] ?? STAND;
  yield* all(
    ...fig.dots.map((d, i) =>
      d().position([target[i][0] * fig.unit, target[i][1] * fig.unit], seconds, easeInOutCubic),
    ),
  );
}

// Pop in: dots appear bottom to top, like the favicon being printed.
export function* figureIn(fig: DotFigure, seconds = 0.6): ThreadGenerator {
  const order = [10, 9, 11, 8, 7, 6, 1, 2, 4, 3, 5, 0];
  for (const i of order) fig.dots[i]().scale(0);
  const step = seconds / order.length;
  yield* all(...order.map((i, k) => (function* () {
    yield* waitFor(k * step);
    yield* fig.dots[i]().scale(1, 0.25, easeOutBack);
  })()));
}

// The head nods on each spoken word of the given beat (runs in the background).
export function* talk(fig: DotFigure, words: Word[]): ThreadGenerator {
  for (const w of words) {
    yield* until(w.start);
    const head = fig.dots[0]();
    yield* head.scale(1.14, 0.07).to(1, 0.12);
  }
}

// Small idle bounce for cheer / wave.
export function* bounce(fig: DotFigure, times = 2): ThreadGenerator {
  const root = fig.root();
  const y = root.y();
  for (let i = 0; i < times; i++) {
    yield* root.y(y - fig.unit * 3, 0.16).to(y, 0.18);
  }
}

export function* wave(fig: DotFigure, seconds = 1.2): ThreadGenerator {
  const hand = fig.dots[5]();
  const base = hand.position();
  const n = Math.max(1, Math.floor(seconds / 0.36));
  for (let i = 0; i < n; i++) {
    yield* hand.position([base.x + fig.unit * 2.2, base.y + fig.unit * 0.6], 0.18).to(base, 0.18);
  }
}

export {loop};
