// 8. Text chat: the script plays out as a phone conversation. Typing dots, then each message
// pops in and its words light up as they are spoken; real Insidir screens arrive as photos.
import {Circle, Img, Node, Rect, Txt, Video, type View2D} from '@motion-canvas/2d';
import {all, cancel, createRef, easeInOutSine, easeOutBack, easeOutCubic, linear, loop, spawn} from '@motion-canvas/core';
import type {Beat, RenderData, Word} from '../lib/data';
import {figureIn, makeFigure, setPose, wave} from '../lib/figure';
import {until} from '../lib/timing';
import {flashHit, stage, whipIn, whipOut} from '../lib/cinema';
import {F} from '../lib/fonts';

const BOTTOM = 700; // y of the newest message's bottom edge
const MAX_W = 760;
const ME_BG = '#f4f1ea';
const ME_INK = '#0c0c0b';
const THEM_BG = '#26282c';
const THEM_INK = '#f4f1ea';

function isMe(b: Beat, i: number) {
  const l = (b.label || '').toUpperCase();
  if (l === 'ME') return true;
  if (l === 'THEM') return false;
  return i % 2 === 1;
}

function header(data: RenderData) {
  const them = data.chat?.them || 'Alex';
  return (
    <Node y={-800}>
      <Rect width={1200} height={380} y={-80} fill="#0e0f10" />
      <Rect width={1080} height={2} y={110} fill="rgba(233,228,218,0.12)" />
      <Txt text="‹" fontFamily="Inter" fontWeight={500} fontSize={96} fill="#e9e4da" x={-470} y={-6} />
      <Circle size={124} y={-20} fill="#3a3d43">
        <Txt text={them.slice(0, 1).toUpperCase()} fontFamily="Inter" fontWeight={800} fontSize={60} fill="#e9e4da" />
      </Circle>
      <Txt text={them} fontFamily="Inter" fontWeight={700} fontSize={40} fill="#e9e4da" y={74} />
    </Node>
  ) as Node;
}

function inputBar() {
  return (
    <Node y={850}>
      <Rect width={1200} height={300} y={70} fill="#0e0f10" />
      <Rect width={860} height={92} radius={46} x={-40} y={-6} stroke="rgba(233,228,218,0.22)" lineWidth={3}>
        <Txt text="Message" fontFamily="Inter" fontSize={38} fill="#77736c" x={-330} />
      </Rect>
      <Circle size={84} x={455} y={-6} fill="#e9e4da">
        <Txt text="↑" fontFamily="Inter" fontWeight={800} fontSize={48} fill="#0c0c0b" />
      </Circle>
    </Node>
  ) as Node;
}

function typing(me: boolean) {
  const dots = [0, 1, 2].map(() => createRef<Circle>());
  const node = (
    <Rect x={me ? 380 : -380} width={180} height={96} radius={48} fill={me ? ME_BG : THEM_BG} opacity={0} scale={0.6}>
      {dots.map((d, k) => <Circle ref={d} x={(k - 1) * 40} size={22} fill={me ? '#77736c' : '#a9a59d'} />)}
    </Rect>
  ) as Rect;
  const bounce = loop(Infinity, function* () {
    for (const d of dots) yield* d().y(-10, 0.12, easeInOutSine).to(0, 0.12, easeInOutSine);
  });
  return {node, dots, bounce};
}

// a text bubble whose words brighten as they are spoken
function bubble(b: Beat, words: Word[], me: boolean) {
  const refs = words.map(() => createRef<Txt>());
  const list = words.length ? words.map(w => w.text) : b.text.split(/\s+/);
  const node = (
    <Rect
      layout
      wrap="wrap"
      direction="row"
      columnGap={14}
      rowGap={4}
      maxWidth={MAX_W}
      padding={[26, 36]}
      radius={48}
      fill={me ? ME_BG : THEM_BG}
      offset={[me ? 1 : -1, 1]}
      x={me ? 500 : -500}
    >
      {list.map((t, i) => (
        <Txt ref={refs[i]} text={t} fontFamily={F.cap} fontWeight={600} fontSize={50} lineHeight={66} fill={me ? ME_INK : THEM_INK} opacity={words.length ? 0.38 : 1} />
      ))}
    </Rect>
  ) as Rect;
  return {node, refs};
}

function photo(b: Beat, me: boolean) {
  const a = b.asset!;
  const k = Math.min(620 / a.width, 760 / a.height);
  const w = Math.round(a.width * k);
  const h = Math.round(a.height * k);
  const media = createRef<Img | Video>();
  const props = {ref: media as any, src: a.src, width: w, height: h};
  const node = (
    <Rect width={w} height={h} radius={40} clip offset={[me ? 1 : -1, 1]} x={me ? 500 : -500} stroke="rgba(233,228,218,0.18)" lineWidth={3}>
      {a.type === 'video' ? <Video {...props} /> : <Img {...props} />}
    </Rect>
  ) as Rect;
  return {node, media, h};
}

function stat(b: Beat, me: boolean) {
  const node = (
    <Rect layout direction="column" alignItems="center" padding={[30, 48]} radius={48} fill={me ? ME_BG : THEM_BG}
          offset={[me ? 1 : -1, 1]} x={me ? 500 : -500}>
      <Txt text={b.emphasis.toUpperCase()} fontFamily={F.head} fontWeight={800} fontSize={104} letterSpacing={-3} fill={me ? ME_INK : THEM_INK} />
      {b.headline ? <Txt text={b.headline.toUpperCase()} fontFamily={F.head} fontWeight={700} fontSize={34} letterSpacing={3} fill={me ? '#55524c' : '#a9a59d'} /> : null}
    </Rect>
  ) as Rect;
  return {node};
}

export function* chat(view: View2D, data: RenderData) {
  const s = stage(view, data);
  const list = createRef<Node>();
  s.content().add(<Node ref={list} />);
  s.content().add(header(data));
  s.content().add(inputBar());
  const end = data.end_card_start ?? data.total;
  let stackTop = BOTTOM; // y where the next message's bottom goes, before scrolling

  const push = function* (node: Rect, height: number, me: boolean) {
    // scroll everything up by the new message's height, then pop it in at the bottom
    const shift = height + 26;
    node.y(stackTop + shift);
    node.scale(0.7);
    node.opacity(0);
    list().add(node);
    stackTop += shift;
    yield* all(
      list().y(BOTTOM - stackTop, 0.26, easeOutCubic),
      node.scale(1, 0.32, easeOutBack),
      node.opacity(1, 0.1),
    );
  };

  for (const [i, b] of data.beats.entries()) {
    if (b.start >= end) break;
    const me = isMe(b, i);
    const ws = data.words.filter(w => w.beat === b.id);
    // typing dots just before the message lands
    const ty = typing(me);
    ty.node.y(stackTop + 70);
    list().add(ty.node);
    const tStart = Math.max(useTypingStart(b), 0);
    yield* until(tStart);
    const bounce = spawn(ty.bounce);
    yield* all(ty.node.opacity(1, 0.08), ty.node.scale(1, 0.16, easeOutBack));
    yield* until(Math.max(tStart + 0.18, b.speech_start - 0.12));
    cancel(bounce);
    ty.node.remove();

    if (b.emphasis) {
      const st = stat(b, me);
      list().add(st.node);
      const h = st.node.height();
      st.node.remove();
      yield* push(st.node, h, me);
      spawn(flashHit(s, 0.14));
    }
    const bb = bubble(b, ws, me);
    list().add(bb.node);
    const h = bb.node.height();
    bb.node.remove();
    yield* push(bb.node, h, me);
    s.cam().scale(1.03);
    spawn(s.cam().scale(1, 0.4, easeOutCubic));
    // karaoke: each word brightens as it is said
    spawn(function* () {
      for (let k = 0; k < ws.length; k++) {
        yield* until(ws[k].start);
        bb.refs[k]().opacity(1);
      }
    });
    if (b.asset) {
      yield* until(Math.min(b.end - 0.35, b.speech_start + 0.6));
      const ph = photo(b, me);
      yield* push(ph.node, ph.h, me);
      if (b.asset.type === 'video') (ph.media() as Video).play();
      spawn(ph.media().scale(1.12, Math.max(0.5, b.end - b.start), linear));
    }
  }

  yield* until(end - 0.13);
  if (data.end_card_start !== null) {
    yield* whipOut(s);
    s.content().removeChildren();
    const [node, fig] = makeFigure('#e9e4da', 10, 0, -380);
    s.content().add(node);
    spawn(whipIn(s));
    spawn(flashHit(s, 0.16));
    yield* figureIn(fig, 0.5);
    yield* setPose(fig, 'cheer', 0.25);
    yield* wave(fig, 0.6);
  }
  yield* until(data.total);
}

function useTypingStart(b: Beat) {
  return Math.max(b.start, b.speech_start - 0.45);
}
