// Insidir-specific finance icon vocabulary. Original vector geometry only.
// All icons share the off-white dotted ring language of the Insidir favicon.
// This is intended for meaningful visual storytelling, not generic HUD decoration.
import {Circle, Node, Path, Rect, Txt} from '@motion-canvas/2d';
import {F} from './fonts';

type GlyphName = 'news'|'question'|'filing'|'search'|'sec'|'cash'|'award'|'option'|
  'shares'|'code'|'link'|'check'|'alert'|'trade'|'chart'|'source'|'person'|'shield';
const IVORY = '#e9e4da';
const MUTED = '#99958e';
const BG = '#0c0c0b';

const line = (data:string, width=8, color=IVORY) =>
  (<Path data={data} stroke={color} lineWidth={width} lineCap="round"
    lineJoin="round" />) as Path;
const rect = (x:number,y:number,w:number,h:number,r=8,fill='rgba(0,0,0,0)',stroke=IVORY,thick=7) =>
  (<Rect x={x} y={y} width={w} height={h} radius={r} fill={fill}
    stroke={stroke} lineWidth={thick}/>) as Rect;
const label = (value:string,x:number,y:number,size=80,color=IVORY) =>
  (<Txt text={value} x={x} y={y} textAlign="center" fontWeight={800}
     fontFamily={F.head} fontSize={size} fill={color}/>) as Txt;

function picture(name:GlyphName):Node {
  const art=(<Node/>) as Node;
  switch(name) {
    case 'news':
      art.add(rect(0,0,148,136,10));
      art.add(rect(-36,-22,46,44,3,IVORY,IVORY,1));
      for (const y of [-42,-14,16,42]) art.add(line('M 2 '+y+' L 57 '+y,5));
      art.add(line('M -57 53 L 57 53',5));
      break;
    case 'question':
      art.add(line('M -32 -30 C -32 -73 41 -79 47 -34 C 50 -5 8 0 8 27',10));
      art.add(<Circle x={8} y={53} size={12} fill={IVORY}/>);
      break;
    case 'filing':
      art.add(line('M -57 -78 L 23 -78 L 59 -43 L 59 77 L -57 77 Z',7));
      art.add(line('M 23 -78 L 23 -43 L 59 -43',6));
      for (const y of [-18, 6, 30, 54]) art.add(line('M -32 '+y+' L 36 '+y,5));
      break;
    case 'search':
      art.add(<Circle x={-14} y={-17} size={105} stroke={IVORY} lineWidth={8}/>);
      art.add(line('M 25 24 L 71 70',11));
      break;
    case 'sec':
      art.add(line('M -69 -36 L 0 -72 L 69 -36 Z',7));
      for(const x of [-48,-16,16,48]) art.add(line('M '+x+' -25 L '+x+' 47',7));
      art.add(line('M -77 56 L 77 56 M -70 -26 L 70 -26',7));
      break;
    case 'cash':
      art.add(rect(0,0,138,98,9));
      art.add(<Circle size={63} stroke={IVORY} lineWidth={5}/>);
      art.add(label('$',0,0,52));
      break;
    case 'award':
      art.add(line('M 0 -67 L 17 -29 L 59 -21 L 28 9 L 37 55 L 0 35 L -37 55 L -28 9 L -59 -21 L -17 -29 Z',8));
      break;
    case 'option':
      art.add(<Circle x={-26} y={-27} size={78} stroke={IVORY} lineWidth={8}/>);
      art.add(line('M 2 3 L 65 66 L 65 42 L 45 42',9));
      break;
    case 'shares':
      for(const [i,dx] of [[0,-31],[1,0],[2,31]] as const){
        art.add(rect(dx,(i-1)*13,73,102,6,'rgba(0,0,0,0)',IVORY,5));
      }
      art.add(<Circle x={0} y={-11} size={21} fill={IVORY}/>);
      break;
    case 'code':
      art.add(line('M -19 -52 L -69 0 L -19 52 M 19 -52 L 69 0 L 19 52',8));
      art.add(line('M 19 -71 L -18 71',6,MUTED));
      break;
    case 'link':
      art.add(line('M -21 -40 L 5 -65 C 53 -109 102 -50 66 -16 L 26 22',9));
      art.add(line('M 21 40 L -5 65 C -53 109 -102 50 -66 16 L -26 -22',9));
      art.add(line('M -38 38 L 38 -38',8));
      break;
    case 'check':
      art.add(line('M -69 -1 L -22 47 L 72 -56',12));
      break;
    case 'alert':
      art.add(line('M 0 -76 L 77 62 L -77 62 Z',7));
      art.add(line('M 0 -29 L 0 21',9));
      art.add(<Circle x={0} y={43} size={10} fill={IVORY}/>);
      break;
    case 'trade':
      art.add(line('M -70 -30 L 65 -30 M 65 -30 L 43 -52 M 65 -30 L 43 -9',8));
      art.add(line('M 70 30 L -65 30 M -65 30 L -43 8 M -65 30 L -43 53',8));
      break;
    case 'chart':
      art.add(line('M -72 60 L -72 -59 M -72 60 L 72 60',6));
      art.add(line('M -50 22 L -13 1 L 15 18 L 66 -44',9));
      art.add(<Circle x={66} y={-44} size={13} fill={IVORY}/>);
      break;
    case 'source':
      art.add(<Circle size={134} stroke={IVORY} lineWidth={6}/>);
      art.add(<Circle size={88} stroke={MUTED} lineWidth={5}/>);
      art.add(<Circle size={26} fill={IVORY}/>);
      break;
    case 'person':
      art.add(<Circle x={0} y={-50} size={42} fill={IVORY}/>);
      art.add(line('M -56 66 L -56 33 C -56 -10 56 -10 56 33 L 56 66',9));
      break;
    case 'shield':
      art.add(line('M 0 -78 L 69 -48 L 63 17 C 59 52 31 72 0 82 C -31 72 -59 52 -63 17 L -69 -48 Z',8));
      art.add(line('M -27 3 L -2 30 L 36 -21',8));
      break;
  }
  return art;
}

// An icon stamp has a dotted rim. The outer Node may be animated 0→1 without
// altering the preset icon scale, making animation reliable in Motion Canvas.
export function financeGlyph(kind:GlyphName,x:number,y:number,size=140):Node {
  const root=(<Node x={x} y={y}/>) as Node;
  const art=(<Node scale={size/200}/>) as Node;
  for(let i=0;i<14;i++) {
    const angle=(Math.PI*2*i/14)-Math.PI/2;
    art.add(<Circle x={Math.cos(angle)*112} y={Math.sin(angle)*112}
      size={i%3===0?9:6.2} fill={IVORY} opacity={0.24+i%3*0.16}/>);
  }
  art.add(picture(kind));
  root.add(art);
  return root;
}
