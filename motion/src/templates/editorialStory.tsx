// Original Form 4 editorial storyboard: dense geometric animation rather than
// the same icon/headline card in every scene. All artwork is SVG/canvas geometry.
import {Circle, Node, Rect, Txt, type View2D} from '@motion-canvas/2d';
import {all, easeOutBack, easeOutCubic, easeOutExpo, linear, spawn} from '@motion-canvas/core';
import type {Beat, RenderData} from '../lib/data';
import {makeFigure, figureIn, setPose, type DotFigure} from '../lib/figure';
import {stage, punch, flashHit, whipIn, whipOut} from '../lib/cinema';
import {until} from '../lib/timing';
import {F} from '../lib/fonts';

const WHITE = '#e9e4da';
const BLACK = '#0c0c0b';
const MUTED = '#807d77';

function word(text: string, x: number, y: number, size = 68, fill = WHITE, width = 830) {
  return (<Txt x={x} y={y} text={text} fontFamily={F.head} fontWeight={800}
    fontSize={size} letterSpacing={-1.8} fill={fill} width={width} textWrap
    textAlign="center" lineHeight={size * 1.07} />) as Txt;
}

function page(x: number, y: number, scale = 1) {
  const p = (
    <Node x={x} y={y} scale={scale}>
      <Rect width={540} height={660} radius={14} fill={WHITE}
        shadowColor="#000000" shadowBlur={45} shadowOffsetY={24} />
      <Txt text="FORM 4" fontFamily={F.head} fontSize={72} fontWeight={800}
        fill={BLACK} y={-220} />
      <Rect width={390} height={7} y={-125} fill="#84817b" />
      <Rect width={330} height={7} x={-30} y={-95} fill="#b4afa6" />
      <Rect width={390} height={3} y={-35} fill="#84817b" />
      <Rect width={390} height={3} y={45} fill="#84817b" />
      <Rect width={390} height={3} y={125} fill="#84817b" />
      <Rect width={390} height={3} y={205} fill="#84817b" />
      <Rect x={0} y={45} width={360} height={64} radius={8}
        fill="rgba(12,12,11,0.05)" stroke={BLACK} lineWidth={4} />
      <Circle x={-156} y={45} size={19} fill={BLACK} />
    </Node>
  ) as Node;
  return p;
}
function pills(n: number, x: number, y: number, radius = 17) {
  const p = (<Node x={x} y={y}/>) as Node;
  for (let i = 0; i < n; i++) {
    p.add(<Circle x={(i % 4) * 70 - 105} y={Math.floor(i / 4) * 70 - 105}
      size={radius * 2} fill={WHITE} />);
  }
  return p;
}
function boxLabel(text: string, x: number, y: number, w = 320) {
  return (<Node x={x} y={y}>
    <Rect width={w} height={146} stroke={WHITE} lineWidth={5}
      fill="rgba(233,228,218,0.06)" radius={12} />
    <Txt text={text} fontFamily={F.head} fontSize={59} fontWeight={800} fill={WHITE} />
  </Node>) as Node;
}
function frameTitle(b: Beat, index: number) {
  return (<Node>
    <Txt text={String(index + 1).padStart(2, '0') + ' / 10'} fontFamily={F.cap}
      fontSize={34} fontWeight={600} fill={MUTED} x={-350} y={-740}/>
    {word(b.headline, 0, -570, b.headline.length > 19 ? 93 : 109, WHITE, 920)}
  </Node>) as Node;
}
function composition(i: number, b: Beat): {node: Node; fig: DotFigure | null} {
  const root = (<Node>
    {frameTitle(b, i)}
  </Node>) as Node;
  let fig: DotFigure | null = null;
  const dotPerson = (x: number, y: number, unit = 6) => {
    const [node, f] = makeFigure(WHITE, unit, x, y);
    root.add(node);
    fig = f;
  };
  switch (i % 10) {
    case 0: // headlines obscure the person who wants primary evidence
      dotPerson(-265, 235, 8);
      root.add(page(228, -10, 0.55));
      root.add(<Rect x={0} y={15} width={250} height={6} fill={WHITE} />);
      root.add(<Circle x={108} y={15} size={26} fill={WHITE} />);
      break;
    case 1: // a real illustrated magnifier, not just an icon
      root.add(page(-160, 15, 0.76));
      root.add(<Circle x={230} y={-25} size={340} stroke={WHITE} lineWidth={24}
        fill="rgba(233,228,218,0.07)" />);
      root.add(<Rect x={352} y={155} width={240} height={23} rotation={43} fill={WHITE}
        radius={12} />);
      root.add(<Circle x={220} y={-24} size={60} stroke={WHITE} lineWidth={6} />);
      break;
    case 2: // the primary filing itself
      root.add(page(0, 28, 0.95));
      root.add(<Rect x={290} y={150} width={165} height={74}
        stroke={WHITE} lineWidth={4} radius={8} rotation={-8}/>);
      root.add(word('PUBLIC', 290, 148, 34, WHITE, 154));
      break;
    case 3: // buyers and other reporting events
      root.add(boxLabel('PURCHASE', -240, -40, 440));
      root.add(boxLabel('OTHER', 250, -40, 390));
      root.add(<Circle x={-240} y={168} size={46} fill={WHITE}/>);
      root.add(<Circle x={250} y={168} size={46} stroke={WHITE} lineWidth={7}/>);
      root.add(<Rect x={0} y={170} width={250} height={5} fill={MUTED}/>);
      break;
    case 4: // sales tracked as movements, not a static percentage
      root.add(word('SALE', 0, -80, 206, WHITE, 840));
      root.add(pills(12, 0, 185, 13));
      root.add(<Rect x={0} y={294} width={620} height={4} fill={WHITE}/>);
      break;
    case 5: // award and options: two distinct document types
      root.add(boxLabel('AWARD', -235, -110, 400));
      root.add(boxLabel('OPTION', 235, 95, 400));
      root.add(<Circle x={-195} y={130} size={90} stroke={WHITE} lineWidth={6}/>);
      root.add(<Circle x={0} y={20} size={20} fill={WHITE}/>);
      root.add(<Circle x={76} y={20} size={20} fill={WHITE}/>);
      root.add(<Rect x={36} y={20} width={60} height={4} fill={WHITE}/>);
      break;
    case 6: // common transaction codes; letters are real SEC codes
      for (const [j, code] of ['P','S','A','M'].entries()) {
        const x = -345 + j * 230;
        root.add(<Rect x={x} y={-35} width={190} height={230} radius={12}
          stroke={WHITE} fill={j === 1 ? WHITE : 'rgba(233,228,218,0.035)'} lineWidth={5}/>);
        root.add(word(code, x, -35, 128, j === 1 ? BLACK : WHITE, 180));
        root.add(<Circle x={x} y={152} size={20} fill={WHITE}/>);
      }
      root.add(word('EACH CODE HAS A MEANING', 0, 265, 38, WHITE, 900));
      break;
    case 7: // follow the document all the way to the SEC
      root.add(page(-220, 0, 0.71));
      root.add(<Rect x={70} y={30} width={200} height={5} fill={WHITE}/>);
      root.add(<Circle x={168} y={30} size={23} fill={WHITE}/>);
      root.add(boxLabel('SEC', 350, 30, 215));
      break;
    case 8: // linked records in a transparent information graph
      dotPerson(-290, 200, 7);
      root.add(page(115, -95, 0.57));
      root.add(<Rect x={-68} y={-10} width={170} height={4} fill={WHITE}/>);
      root.add(<Rect x={130} y={290} width={200} height={4} fill={WHITE}/>);
      root.add(<Circle x={230} y={290} size={34} stroke={WHITE} lineWidth={6}/>);
      break;
    default: // clarity instead of an endless headline
      root.add(page(180, 65, 0.66));
      dotPerson(-245, 230, 7.5);
      root.add(<Circle x={-70} y={20} size={190} stroke={WHITE} lineWidth={5}/>);
      root.add(word('READ THE SOURCE', 0, 295, 46, WHITE, 890));
  }
  return {node: root, fig};
}

export function* editorialStory(view: View2D, data: RenderData) {
  const s = stage(view, data);
  let previous: Node | null = null;
  for (const [i, b] of data.beats.entries()) {
    if (data.end_card_start !== null && b.start >= data.end_card_start) break;
    yield* until(b.start);
    if (previous) {
      yield* whipOut(s);
      previous.remove();
      s.content().x(0);
    }
    const {node, fig} = composition(i, b);
    const content = (<Node opacity={0} scale={0.8} y={55}>{node}</Node>) as Node;
    s.content().add(content);
    if (i > 0) spawn(whipIn(s));
    spawn(punch(s, Math.max(0.7, b.end - b.start), 1.07));
    if (i === 0 || i === 2 || i === 6) spawn(flashHit(s, 0.17));
    if (fig) {
      spawn(figureIn(fig, 0.55));
      spawn(setPose(fig, b.pose || 'explain', 0.38));
    }
    yield* all(
      content.opacity(1, 0.32),
      content.scale(1, 0.57, easeOutBack),
      content.y(0, 0.54, easeOutExpo),
    );
    spawn(content.scale(1.04, Math.max(0.5, b.end - b.start - 0.65), linear));
    previous = content;
  }
  if (data.end_card_start !== null) {
    yield* until(data.end_card_start);
    if (previous) {
      yield* previous.opacity(0, 0.24);
      previous.remove();
    }
    const [node, fig] = makeFigure(WHITE, 10, 0, -360);
    s.content().add(node);
    yield* figureIn(fig, 0.6);
    yield* setPose(fig, 'cheer', 0.28);
  }
  yield* until(data.total);
}
