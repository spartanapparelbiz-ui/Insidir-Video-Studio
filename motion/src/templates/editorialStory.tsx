// Insidir editorial explainer: one original story, told through the dots of the
// authentic Insidir "i", real SEC Form 4 concepts, and clean financial information.
// No sequence counters, fake dashboards, persistent logos, or generic HUD/watermarks.
import {Circle, Node, Rect, Txt, type View2D} from '@motion-canvas/2d';
import {all, easeInOutCubic, easeOutCubic, spawn, type ThreadGenerator} from '@motion-canvas/core';
import type {Beat, RenderData} from '../lib/data';
import {makeFigure, figureIn, setPose} from '../lib/figure';
import {until} from '../lib/timing';
import {F} from '../lib/fonts';

const PAPER = '#e9e4da';
const INK = '#0c0c0b';
const MUTED = '#85817b';
const HAIRLINE = '#292824';
const DIM = '#b3aea6';
const COL = 1080, HEIGHT = 1920;

function text(value: string, x: number, y: number, size = 60, color = PAPER, width = 840, mono = false): Txt {
  return (<Txt text={value} x={x} y={y} fontFamily={mono ? 'monospace' : F.head}
    fontWeight={mono ? 500 : 760} fontSize={size} lineHeight={size * 1.12}
    fill={color} letterSpacing={mono ? 1.8 : -1.9}
    textWrap width={width} textAlign="center" />) as Txt;
}

function line(x: number, y: number, w: number, h = 3, color = HAIRLINE): Rect {
  return (<Rect x={x} y={y} width={w} height={h} fill={color} />) as Rect;
}

function dotPattern(x: number, y: number, cols = 5, rows = 4, spacing = 28, size = 8): Node {
  const root = (<Node x={x} y={y} />) as Node;
  for (let c = 0; c < cols; c++) for (let r = 0; r < rows; r++)
    root.add(<Circle x={(c - (cols - 1) / 2) * spacing}
      y={(r - (rows - 1) / 2) * spacing}
      size={size} fill={PAPER} opacity={0.22 + ((c + r) % 3) * 0.14} />);
  return root;
}

function card(title: string, detail: string, x: number, y: number, w = 420, h = 205): Node {
  return (<Node x={x} y={y}>
    <Rect width={w} height={h} radius={11} fill="#121211" stroke="#49463f" lineWidth={2.8}/>
    <Rect width={9} height={h - 62} x={-w / 2 + 25} fill={PAPER} radius={4}/>
    {text(title, 14, -32, 55, PAPER, w - 100)}
    {text(detail, 12, 43, 24, MUTED, w - 100, true)}
  </Node>) as Node;
}

// A designed illustration of a Form 4, never a forged real SEC document.
function form4(x: number, y: number, scale = 1): Node {
  const root = (<Node x={x} y={y} scale={scale}>
    <Rect width={590} height={750} fill={PAPER} radius={8}
      shadowColor="#000000" shadowBlur={52} shadowOffsetY={20}/>
    <Txt text="UNITED STATES SEC" x={0} y={-326} fontSize={24}
      fontFamily="Georgia" fill={INK} fontWeight={700}/>
    {line(0, -298, 480, 3, '#9b958b')}
    <Txt text="FORM 4" fontFamily={F.head} fontWeight={800}
      fontSize={94} y={-225} fill={INK}/>
    <Txt text="STATEMENT OF CHANGES IN BENEFICIAL OWNERSHIP"
      fontFamily={F.head} fontSize={22} fontWeight={600} textAlign="center"
      width={460} textWrap y={-154} fill="#4a4742"/>
    {line(0, -94, 480, 4, '#9b958b')}
    {text("REPORTING PERSON", 0, -33, 28, '#59554f', 430, true)}
    {line(0, 12, 460, 5, '#bfbab3')}
    {text("TRANSACTION DETAILS", 0, 65, 28, '#59554f', 430, true)}
    {line(0, 115, 460, 4, '#bfbab3')}
    {line(0, 172, 460, 4, '#bfbab3')}
    {line(0, 229, 460, 4, '#bfbab3')}
    <Rect width={408} height={59} y={171} radius={6}
      stroke={INK} lineWidth={4} fill="rgba(12,12,11,0.025)"/>
    <Circle x={-195} y={171} size={18} fill={INK}/>
    {line(0, 293, 460, 4, '#bfbab3')}
  </Node>) as Node;
  return root;
}

function scene(i: number, b: Beat): Node {
  const root = (<Node />) as Node;
  const title = b.headline || b.text;
  root.add(text(title, 0, -605, title.length > 27 ? 78 : 100, PAPER, 940));
  // A quiet technical rule, only inside the current scene—not a top-left watermark.
  root.add(line(0, -468, 840, 2, '#403e39'));
  switch (i % 8) {
    case 0: {
      root.add(card('INSIDER ACTIVITY', 'A HEADLINE', 155, -80, 545, 238));
      root.add(dotPattern(165, 238, 8, 3, 37, 12));
      root.add(text('One line rarely tells the whole story.', 110, 376, 31, DIM, 780));
      break;
    }
    case 1: {
      root.add(form4(170, -26, 0.81));
      root.add(<Circle x={242} y={100} size={205} stroke={PAPER} lineWidth={10}
        fill="rgba(233,228,218,0.09)"/>);
      root.add(<Rect x={322} y={193} width={156} height={15}
        fill={PAPER} radius={8} rotation={42}/>);
      root.add(text('PUBLIC SEC RECORD', -30, 374, 28, DIM, 580, true));
      break;
    }
    case 2: {
      root.add(card('PURCHASE', 'OPEN-MARKET', -164, -146, 350, 175));
      root.add(card('SALE', 'OPEN-MARKET', 238, -146, 350, 175));
      root.add(card('AWARD', 'SHARE GRANT', -164, 114, 350, 175));
      root.add(card('EXERCISE', 'OPTIONS', 238, 114, 350, 175));
      root.add(dotPattern(175, 340, 8, 2, 27, 10));
      break;
    }
    case 3: {
      const codes = [['P', 'PURCHASE'], ['S', 'SALE'], ['A', 'AWARD'], ['M', 'EXERCISE']];
      codes.forEach(([letter, label], j) => {
        const x = -264 + j * 178;
        root.add(<Rect x={x} y={-38} width={145} height={210} radius={11}
          stroke={j === 0 ? PAPER : '#514d46'}
          fill={j === 0 ? PAPER : '#151513'} lineWidth={3.5}/>);
        root.add(text(letter, x, -56, 117, j === 0 ? INK : PAPER, 130));
        root.add(text(label, x, 88, 17, DIM, 158, true));
      });
      root.add(text('SAME FILING. DIFFERENT MEANING.', 0, 280, 34, PAPER, 830));
      break;
    }
    case 4: {
      root.add(card('THE HEADLINE', 'SHORT VERSION', -150, -150, 430, 230));
      root.add(line(94, 60, 305, 3, '#57534e'));
      root.add(<Circle x={260} y={60} size={23} fill={PAPER}/>);
      root.add(card('THE FILING', 'TRANSACTION CONTEXT', 170, 225, 490, 225));
      break;
    }
    case 5: {
      root.add(card('SEC FILING', 'ORIGINAL RECORD', 170, -265, 500, 190));
      root.add(line(170, -100, 5, 122, PAPER));
      root.add(<Circle x={170} y=-32 size={23} fill={PAPER}/>);
      root.add(card('PLAIN LANGUAGE', 'TRANSACTION CODES', 170, 114, 500, 190));
      root.add(dotPattern(170, 316, 8, 2, 31, 9));
      break;
    }
    case 6: {
      root.add(form4(153, -85, 0.74));
      root.add(<Rect x={205} y={130} width={342} height={83} fill={INK}
        stroke={PAPER} lineWidth={5} radius={6}/>);
      root.add(text('OPEN SOURCE', 205, 132, 37, PAPER, 304, true));
      root.add(text('SEC / EDGAR', 205, 354, 33, DIM, 500, true));
      break;
    }
    default: {
      root.add(form4(173, -68, 0.67));
      root.add(dotPattern(172, 305, 10, 2, 28, 9));
      root.add(text('Facts before interpretations.', 145, 403, 36, PAPER, 720));
      break;
    }
  }
  return root;
}

function grid(view: View2D) {
  view.fill(INK);
  view.add(<Rect width={COL} height={HEIGHT} fill={INK}/>);
  const g = (<Node opacity={0.45} />) as Node;
  for (let x = -540; x <= 540; x += 108) g.add(line(x, 0, 1.2, HEIGHT, '#1c1c1b'));
  for (let y = -960; y <= 960; y += 108) g.add(line(0, y, COL, 1.2, '#1c1c1b'));
  view.add(g);
  view.add(line(0, -812, 888, 2, '#33312d'));
}

export function* editorialStory(view: View2D, data: RenderData): ThreadGenerator {
  grid(view);
  // One continuing protagonist, reused across the whole video, built by the
  // same twelve dot positions and sizes as the actual Insidir favicon figure.
  const [avatar, dot] = makeFigure(PAPER, 6.4, -336, 400);
  view.add(avatar);
  spawn(figureIn(dot, 0.9));
  let previous: Node | null = null;
  for (const [i, beat] of data.beats.entries()) {
    if (data.end_card_start !== null && beat.start >= data.end_card_start) break;
    yield* until(Math.max(0, beat.start - 0.40));
    if (previous) {
      yield* previous.opacity(0, 0.32, easeInOutCubic);
      previous.remove();
    }
    yield* until(beat.start);
    const panel = scene(i, beat);
    panel.opacity(0);
    panel.y(28);
    panel.scale(0.975);
    view.add(panel);
    // No jump-cuts or white flashes. The information quietly changes while Dot
    // follows the primary filing from headline to transaction code to source.
    spawn(setPose(dot, ['think','point','explain','point','shrug','explain','pointup','cheer'][i % 8], 0.7));
    spawn(dot.root().x([-336, -340, -360, -325, -350, -320, -335, -315][i % 8], 0.8, easeInOutCubic));
    yield* all(
      panel.opacity(1, 0.64, easeOutCubic),
      panel.y(0, 0.72, easeOutCubic),
      panel.scale(1, 0.88, easeOutCubic),
    );
    previous = panel;
  }
  if (data.end_card_start !== null) {
    yield* until(Math.max(0, data.end_card_start - 0.44));
    if (previous) {
      yield* previous.opacity(0, 0.4);
      previous.remove();
    }
    // Native end card (with insidir. + URL) is added by the existing FFmpeg
    // composer. The only persistent icon is Dot, not a watermark.
    yield* all(dot.root().position([0, -405], 0.75, easeInOutCubic), dot.root().scale(0.89, 0.75));
    yield* setPose(dot, 'stand', 0.55);
  }
  yield* until(data.total);
}
