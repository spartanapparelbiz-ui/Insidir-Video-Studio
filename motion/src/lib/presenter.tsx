// Cartoon presenters for the avatar template. Flat vector characters built from Motion
// Canvas shapes, so they need no GPU and no model: the mouth follows the narration frame by
// frame (an openness track the studio measures from the voice), the eyes blink, the head
// nods with the speech and the arms gesture on each beat.
import {Circle, Node, Rect, Txt} from '@motion-canvas/2d';
import {all, createRef, easeInOutCubic, easeInOutSine, type Reference, spawn, type ThreadGenerator, useTime} from '@motion-canvas/core';
import {until} from './timing';

export interface Look {
  name: string;
  skin: string;
  shade: string;
  hair: string | null;
  hairStyle: 'none' | 'bob' | 'short' | 'curls';
  shirt: string;
  trim: string;
  eye: string;
  glasses?: boolean;
  badge?: boolean;
  blush?: string;
}

export const CHARACTERS: Record<string, Look> = {
  // the Insidir "i" dot as a character: a paper-white round head on a dark hoodie
  dot: {name: 'Dot', skin: '#e9e4da', shade: '#cfc8bb', hair: null, hairStyle: 'none', shirt: '#1c1e21', trim: '#e9e4da', eye: '#0c0c0b', badge: true, blush: 'rgba(214,120,110,0.28)'},
  maya: {name: 'Maya', skin: '#b97c5b', shade: '#9a5f43', hair: '#1a1210', hairStyle: 'bob', shirt: '#2c4a63', trim: '#e9e4da', eye: '#140d0b', blush: 'rgba(200,90,80,0.25)'},
  leo: {name: 'Leo', skin: '#e2b593', shade: '#c79574', hair: '#3a2a20', hairStyle: 'short', shirt: '#2a2b2e', trim: '#e9e4da', eye: '#1a1310', glasses: true, blush: 'rgba(210,110,95,0.22)'},
  sam: {name: 'Sam', skin: '#8a5a3c', shade: '#6f452c', hair: '#120c0a', hairStyle: 'curls', shirt: '#3d2f4f', trim: '#e9e4da', eye: '#0e0907', blush: 'rgba(190,80,70,0.22)'},
};

type ArmPose = [number, number]; // upper-arm and forearm rotation (degrees) for the RIGHT arm; the left mirrors
export const GESTURES: Record<string, {r: ArmPose; l: ArmPose; tilt: number; look: [number, number]}> = {
  rest: {r: [-10, -6], l: [-10, -6], tilt: 0, look: [0, 0]},
  explain: {r: [-28, 150], l: [-12, -4], tilt: -3, look: [0, 0]},
  both: {r: [-30, 140], l: [-30, 140], tilt: 2, look: [0, 0]},
  pointup: {r: [-150, -12], l: [-10, -6], tilt: -6, look: [6, -8]},
  pointleft: {r: [-10, -6], l: [-150, -12], tilt: 6, look: [-6, -8]},
  wave: {r: [-125, 35], l: [-10, -6], tilt: 4, look: [0, 0]},
  cheer: {r: [-118, -28], l: [-118, -28], tilt: 0, look: [0, -4]},
  shrug: {r: [-48, -78], l: [-48, -78], tilt: 5, look: [0, 0]},
  think: {r: [-20, 160], l: [-10, -6], tilt: 7, look: [7, -9]},
};

// the forearm needs a moment to arrive; poses ease over this many seconds
const MOVE = 0.42;
const UPPER = 250;
const FORE = 230;

interface Arm {
  shoulder: Reference<Node>;
  fore: Reference<Node>;
}

export interface Presenter {
  root: Reference<Node>;
  head: Reference<Node>;
  arms: {r: Arm; l: Arm};
  eyes: Reference<Node>;
  pupils: Reference<Node>;
  brows: Reference<Node>;
  look: Look;
}

function arm(look: Look, side: 1 | -1): [Node, Arm] {
  const shoulder = createRef<Node>();
  const fore = createRef<Node>();
  const node = (
    <Node ref={shoulder} x={side * 236} y={70} scaleX={side} rotation={-10}>
      <Rect width={118} height={UPPER + 50} radius={59} y={UPPER / 2} fill={look.shirt} />
      <Node ref={fore} y={UPPER} rotation={-6}>
        <Rect width={104} height={FORE + 40} radius={52} y={FORE / 2} fill={look.shirt} />
        <Rect width={104} height={26} y={FORE - 8} fill={look.trim} opacity={0.9} />
        <Circle size={104} y={FORE + 40} fill={look.skin} />
        <Rect width={30} height={70} radius={15} x={44} y={FORE + 12} rotation={-30} fill={look.skin} />
      </Node>
    </Node>
  ) as Node;
  return [node, {shoulder, fore}];
}

function hair(look: Look, front: boolean): Node | null {
  if (!look.hair) return null;
  if (look.hairStyle === 'bob') {
    return front ? (
      <Node>
        <Rect width={356} height={150} radius={[178, 178, 30, 90]} y={-128} fill={look.hair} />
        <Rect width={120} height={90} radius={45} x={110} y={-80} rotation={-28} fill={look.hair} />
      </Node>
    ) as Node : (<Rect width={420} height={430} radius={[200, 200, 70, 70]} y={20} fill={look.hair} />) as Rect;
  }
  if (look.hairStyle === 'curls') {
    const curls: [number, number, number][] = [[-130, -110, 120], [-60, -160, 130], [20, -175, 135], [100, -150, 125], [150, -90, 105], [-165, -40, 95], [170, -20, 85]];
    return front ? (
      <Node>{curls.map(([x, y, s]) => <Circle x={x} y={y} size={s} fill={look.hair} />)}</Node>
    ) as Node : null;
  }
  if (look.hairStyle === 'short') {
    return front ? (
      <Node>
        <Rect width={350} height={124} radius={[175, 175, 24, 24]} y={-140} fill={look.hair} />
        <Rect width={150} height={70} radius={35} x={-60} y={-178} rotation={-12} fill={look.hair} />
      </Node>
    ) as Node : null;
  }
  return null;
}

export function makePresenter(key: string, x = 0, y = 0, scale = 1): [Node, Presenter] {
  const look = CHARACTERS[key] ?? CHARACTERS.dot;
  const root = createRef<Node>();
  const head = createRef<Node>();
  const eyes = createRef<Node>();
  const pupils = createRef<Node>();
  const brows = createRef<Node>();
  const [armR, r] = arm(look, 1);
  const [armL, l] = arm(look, -1);
  const isDot = look.hairStyle === 'none';
  const node = (
    <Node ref={root} x={x} y={y} scale={scale}>
      {/* body */}
      <Rect width={560} height={760} radius={[230, 230, 60, 60]} y={390} fill={look.shirt} />
      <Rect width={170} height={86} radius={[0, 0, 85, 85]} y={22} fill={look.trim} opacity={0.95} />
      {look.badge ? (
        <Node x={150} y={230}>
          <Circle size={34} y={-46} fill={look.trim} />
          <Rect width={26} height={58} radius={13} y={4} fill={look.trim} />
        </Node>
      ) : null}
      {armL}
      {armR}
      {/* neck */}
      <Rect width={isDot ? 0 : 104} height={90} y={-6} fill={look.shade} />
      <Node ref={head} y={-200}>
        {hair(look, false)}
        {isDot ? null : <Circle x={-176} y={10} size={74} fill={look.skin} />}
        {isDot ? null : <Circle x={176} y={10} size={74} fill={look.skin} />}
        {isDot ? (
          <Circle size={400} fill={look.skin} />
        ) : (
          <Rect width={348} height={392} radius={170} fill={look.skin} />
        )}
        {hair(look, true)}
        <Circle x={-104} y={70} size={70} fill={look.blush ?? 'rgba(0,0,0,0)'} />
        <Circle x={104} y={70} size={70} fill={look.blush ?? 'rgba(0,0,0,0)'} />
        <Node ref={brows}>
          <Rect x={-70} y={-62} width={72} height={15} radius={8} rotation={-4} fill={look.hair ?? look.eye} />
          <Rect x={70} y={-62} width={72} height={15} radius={8} rotation={4} fill={look.hair ?? look.eye} />
        </Node>
        <Node ref={eyes} y={-8}>
          <Node ref={pupils}>
            <Rect x={-70} width={34} height={48} radius={17} fill={look.eye} />
            <Rect x={70} width={34} height={48} radius={17} fill={look.eye} />
            <Circle x={-63} y={-10} size={11} fill="#ffffff" />
            <Circle x={77} y={-10} size={11} fill="#ffffff" />
          </Node>
        </Node>
        {look.glasses ? (
          <Node y={-8}>
            <Rect x={-72} width={112} height={92} radius={30} stroke={look.eye} lineWidth={8} />
            <Rect x={72} width={112} height={92} radius={30} stroke={look.eye} lineWidth={8} />
            <Rect width={36} height={8} y={-6} fill={look.eye} />
          </Node>
        ) : null}
        {isDot ? null : <Rect y={40} width={30} height={46} radius={15} fill={look.shade} />}
      </Node>
    </Node>
  ) as Node;
  return [node, {root, head, arms: {r, l}, eyes, pupils, brows, look}];
}

// Mouth: added after the face so it draws on top. Openness (0-1) and width (0-1) per frame.
export function makeMouth(p: Presenter, mouth: number[], width: number[], fps: number): Node {
  const lips = createRef<Rect>();
  const teeth = createRef<Rect>();
  const tongue = createRef<Circle>();
  const node = (
    <Rect ref={lips} y={98} width={92} height={14} radius={7} fill="#3a1717" clip>
      <Rect ref={teeth} width={140} height={22} y={-30} fill="#f4f1ea" />
      <Circle ref={tongue} size={70} y={40} fill="#c4615c" />
    </Rect>
  ) as Rect;
  p.head().add(node);
  const at = (arr: number[], t: number) => {
    if (!arr.length) return 0;
    const f = t * fps;
    const i = Math.max(0, Math.min(arr.length - 1, Math.floor(f)));
    const j = Math.min(arr.length - 1, i + 1);
    return arr[i] + (arr[j] - arr[i]) * (f - Math.floor(f));
  };
  spawn(function* (): ThreadGenerator {
    while (true) {
      const t = useTime();
      const o = at(mouth, t);
      const w = at(width, t);
      const h = 12 + 84 * o;
      lips().height(h);
      lips().width(70 + 46 * w + 20 * o);
      lips().radius(Math.min(h, 70 + 46 * w) / 2);
      teeth().y(-h / 2 + 4);
      tongue().y(h / 2 + 18 - 10 * o);
      // talk with the whole head: a little nod and lift on loud syllables
      p.head().y(-200 - 10 * o);
      yield;
    }
  });
  return node;
}

function rng(seed: number) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

export function* blinkLoop(p: Presenter, total: number): ThreadGenerator {
  const rand = rng(7);
  let t = 0.8 + rand() * 1.5;
  while (t < total) {
    yield* until(t);
    yield* p.eyes().scale.y(0.08, 0.06).to(1, 0.09);
    if (rand() < 0.18) yield* p.eyes().scale.y(0.08, 0.05).to(1, 0.08);
    t += 2.2 + rand() * 2.6;
  }
}

export function* idle(p: Presenter, total: number): ThreadGenerator {
  // slow sway and breathing
  while (useTime() < total) {
    yield* all(
      p.root().rotation(1.2, 1.8, easeInOutSine).to(-1.2, 1.8, easeInOutSine),
      p.root().scale.y(p.root().scale.x() * 1.008, 1.8, easeInOutSine).to(p.root().scale.x(), 1.8, easeInOutSine),
    );
  }
}

export function* gesture(p: Presenter, name: string, seconds = MOVE): ThreadGenerator {
  const g = GESTURES[name] ?? GESTURES.rest;
  yield* all(
    p.arms.r.shoulder().rotation(g.r[0], seconds, easeInOutCubic),
    p.arms.r.fore().rotation(g.r[1], seconds, easeInOutCubic),
    p.arms.l.shoulder().rotation(g.l[0], seconds, easeInOutCubic),
    p.arms.l.fore().rotation(g.l[1], seconds, easeInOutCubic),
    p.head().rotation(g.tilt, seconds, easeInOutCubic),
    p.pupils().position(g.look, seconds, easeInOutCubic),
    p.brows().y(name === 'think' || name === 'shrug' ? -10 : name === 'cheer' ? -14 : 0, seconds, easeInOutCubic),
  );
  if (name === 'wave') {
    for (let k = 0; k < 3; k++) yield* p.arms.r.fore().rotation(10, 0.18, easeInOutSine).to(45, 0.18, easeInOutSine);
  }
}

export function nameTag(p: Presenter, y: number): Node {
  return (
    <Rect y={y} padding={[12, 26]} radius={40} fill="rgba(12,12,11,0.72)" stroke="rgba(233,228,218,0.25)" lineWidth={2} layout>
      <Txt text={p.look.name.toUpperCase()} fontFamily="Inter" fontWeight={800} fontSize={34} letterSpacing={4} fill="#e9e4da" />
    </Rect>
  ) as Rect;
}
