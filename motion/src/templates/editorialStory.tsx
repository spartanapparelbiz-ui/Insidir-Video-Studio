// Insidir — the difference between an insider purchase and an award.
// Editorial motion graphic: multiple characters made of the same twelve-dot
// geometry as the Insidir "i" icon, meaningful scenes, purposeful illustrations.
// No decorative grids, scene counters, stock tickers, or persistent watermark.
import {Circle, Node, Rect, Txt, type View2D} from '@motion-canvas/2d';
import {all, easeInOutCubic, easeOutCubic, spawn, type ThreadGenerator} from '@motion-canvas/core';
import type {RenderData} from '../lib/data';
import {makeFigure, setPose, figureIn, type DotFigure} from '../lib/figure';
import {until} from '../lib/timing';
import {F} from '../lib/fonts';

const BG = '#0c0c0b';
const IVORY = '#e9e4da';
const SOFT = '#99958e';
const LINE = '#44423e';
const FIELD = '#181817';

function txt(t:string, x:number,y:number,size:number=53,fill=IVORY,width=900):Txt {
  return (<Txt x={x} y={y} width={width} text={t} textWrap textAlign="center"
     fontFamily={F.head} fontWeight={750} fontSize={size} fill={fill}
     letterSpacing={-1.5} lineHeight={size*1.14}/>) as Txt;
}
function mono(t:string,x:number,y:number,size:number=27,fill=SOFT,width=900):Txt {
  return (<Txt x={x} y={y} width={width} text={t} textAlign="center" textWrap
    fontFamily="monospace" fontSize={size} fontWeight={500} letterSpacing={1.3} fill={fill}/>) as Txt;
}
function bar(x:number,y:number,w:number,h:number=3,color=LINE):Rect {
  return (<Rect x={x} y={y} width={w} height={h} fill={color}/>) as Rect;
}
function particles(x:number,y:number,n:number=7,r:number=15):Node {
  const nroot = (<Node x={x} y={y}/>) as Node;
  for(let i=0;i<n;i++) nroot.add(<Circle x={i*48-(n-1)*24} size={r} fill={IVORY} />);
  return nroot;
}
function panel(x:number,y:number,w:number,h:number):Node {
  return (<Node x={x} y={y}>
    <Rect width={w} height={h} radius={8} fill={FIELD} stroke={LINE} lineWidth={3}/>
  </Node>) as Node;
}
function character(role:'viewer'|'executive'|'researcher',x:number,y:number,unit:number=6):{node:Node,figure:DotFigure} {
  const [body,figure] = makeFigure(IVORY,unit,0,0);
  const root = (<Node x={x} y={y}/>) as Node;
  root.add(body);
  // Accessories are geometry built from the same circular dot vocabulary.
  // Roles are distinguishable even without their short labels.
  if (role==='executive') {
    root.add(<Node>
      <Circle x={-unit*2.5} y={-unit*16} size={unit*2.5} fill={SOFT}/>
      <Circle x={unit*2.5} y={-unit*16} size={unit*2.5} fill={SOFT}/>
      <Circle x={0} y={-unit*14} size={unit*2.4} fill={SOFT}/>
      <Rect x={unit*24} y={-unit*5} width={unit*15} height={unit*11}
        radius={unit*1.4} stroke={IVORY} lineWidth={unit*0.7} fill={BG}/>
      <Rect x={unit*24} y={-unit*11.5} width={unit*6} height={unit*2}
        radius={unit} stroke={IVORY} lineWidth={unit*0.5}/>
    </Node>);
  }
  if (role==='researcher') {
    root.add(<Node>
      <Circle x={-unit*5} y={-unit*36} size={unit*7} stroke={IVORY} lineWidth={unit*1.2}/>
      <Circle x={unit*5} y={-unit*36} size={unit*7} stroke={IVORY} lineWidth={unit*1.2}/>
      <Circle x={0} y={-unit*36} size={unit*2.2} fill={IVORY}/>
    </Node>);
  }
  return {node:root,figure};
}
function addPerson(scene:Node,role:'viewer'|'executive'|'researcher',x:number,y:number,unit:number,label?:string):DotFigure {
  const p = character(role,x,y,unit); scene.add(p.node);
  if(label) scene.add(mono(label,x,y+78,26,SOFT,290));
  return p.figure;
}
function document(x:number,y:number,s:number=1):Node {
  return (<Node x={x} y={y} scale={s}>
    <Rect width={540} height={625} radius={9} fill={IVORY}/>
    {txt('FORM 4',0,-226,90,BG,480)}
    {bar(0,-164,410,3,'#a9a59d')}
    {mono('PUBLIC OWNERSHIP RECORD',0,-125,21,'#514d46',490)}
    {bar(0,-68,418,4,'#b4afa6')}
    {bar(0,-7,418,4,'#b4afa6')}
    {bar(0,54,418,4,'#b4afa6')}
    {bar(0,115,418,4,'#b4afa6')}
    {bar(0,176,418,4,'#b4afa6')}
    <Rect y={54} width={408} height={52} radius={3}
      stroke={BG} lineWidth={3} fill="rgba(12,12,11,0.03)" />
  </Node>) as Node;
}
function headline(scene:Node,headline:string) {
  scene.add(txt(headline,0,-655,headline.length>27?75:91,IVORY,940));
}

// Return the important figures so their poses are part of the STORY,
// not a watermark bouncing in the corner through every clip.
function makeScene(i:number,heading:string):{content:Node,people:DotFigure[]} {
  const root=(<Node/>) as Node;
  const people:DotFigure[]=[];
  headline(root,heading);
  switch(i){
    case 0: {
      // Viewer encounters a provocative headline, shown explicitly as an example.
      people.push(addPerson(root,'viewer',-285,220,7.5,'YOU'));
      const h=panel(140,-110,650,280);root.add(h);
      h.add(txt('INSIDER ACTIVITY',0,-43,69,IVORY,590));
      h.add(mono('HEADLINE ≠ COMPLETE RECORD',0,66,22,SOFT,580));
      root.add(bar(55,175,300,4,LINE));root.add(particles(165,258,5,15));
      break;
    }
    case 1: {
      // Two real roles appear rather than a single generic mascot.
      people.push(addPerson(root,'viewer',-330,202,5.8,'YOU'));
      people.push(addPerson(root,'executive',300,202,5.4,'EXECUTIVE'));
      root.add(document(0,-185,0.68));
      root.add(bar(0,100,280,3,SOFT));
      root.add(mono('ORIGINAL SEC DISCLOSURE',0,338,26,SOFT,600));
      break;
    }
    case 2: {
      // Visually compare cash purchase against issued award:
      // both concern shares, but their meaning is different.
      const left=panel(-220,-35,420,320), right=panel(225,-35,420,320);
      root.add(left);root.add(right);
      left.add(txt('P',0,-48,154,IVORY,380));left.add(mono('PURCHASE',0,106,27,SOFT,360));
      right.add(txt('A',0,-48,154,IVORY,380));right.add(mono('AWARD',0,106,27,SOFT,360));
      root.add(mono('THE SAME THING?',0,254,31,SOFT,780));
      root.add(txt('NO.',0,352,79,IVORY,780));
      break;
    }
    case 3: {
      // An independent analyst checks the transaction code, not a price chart.
      people.push(addPerson(root,'researcher',-300,170,6.5,'RESEARCHER'));
      root.add(document(163,-100,0.68));
      root.add(<Circle x={242} y={-45} size={180} stroke={BG}
        lineWidth={13} fill="rgba(233,228,218,0.14)"/>);
      root.add(<Circle x={242} y={-45} size={188} stroke={IVORY}
        lineWidth={8} fill="rgba(0,0,0,0)"/>);
      root.add(<Rect x={319} y={34} width={130} height={15}
        rotation={43} radius={7} fill={IVORY}/>);
      root.add(mono('LOOK AT THE CODE',153,334,29,SOFT,570));
      break;
    }
    case 4: {
      // Option exercises are a separate category, illustrated by a route.
      root.add(txt('M',-230,-80,206,IVORY,280));
      root.add(mono('OPTION EXERCISE',-215,114,27,SOFT,400));
      root.add(bar(125,-68,335,5,SOFT));
      root.add(<Circle x={294} y={-68} size={30} fill={IVORY}/>);
      root.add(<Rect x={292} y={92} width={280} height={234}
        stroke={LINE} fill={FIELD} lineWidth={3} radius={10}/>);
      root.add(particles(292,92,4,30));
      root.add(mono('A DIFFERENT EVENT',175,329,26,SOFT,610));
      break;
    }
    case 5: {
      // Three different characters, one shared public source. Distinct roles
      // and clear composition make this a little story instead of a card reel.
      people.push(addPerson(root,'viewer',-322,208,4.7,'YOU'));
      people.push(addPerson(root,'executive',0,208,4.7,'EXECUTIVE'));
      people.push(addPerson(root,'researcher',321,208,4.7,'ANALYST'));
      root.add(bar(0,-70,695,3,SOFT));
      root.add(document(0,-233,0.48));
      root.add(mono('A PUBLIC RECORD. NOT A SIGNAL TO TRADE.',0,358,25,SOFT,880));
      break;
    }
    default: {
      // Ending shot: one very simple chain from information to its source.
      root.add(mono('INSIDIR',0,-352,44,IVORY,720));
      root.add(txt('Transaction context',0,-190,66,IVORY,900));
      root.add(bar(0,-72,540,3,SOFT));
      root.add(txt('Original SEC filing',0,32,66,IVORY,900));
      root.add(particles(0,203,7,20));
      root.add(mono('START WITH THE SOURCE',0,358,29,SOFT,870));
      break;
    }
  }
  return {content:root,people};
}

export function* editorialStory(view:View2D,data:RenderData):ThreadGenerator {
  view.fill(BG);
  view.add(<Rect width={1080} height={1920} fill={BG}/>);
  let previous:Node|null=null;
  for(const [i,b] of data.beats.entries()) {
    if(data.end_card_start!==null && b.start>=data.end_card_start) break;
    const incoming=makeScene(i,b.headline);
    const scene=incoming.content;
    scene.opacity(0);scene.y(20);scene.scale(0.97);
    view.add(scene);
    // Calm handoff; no white flash, no fake film grain, no arbitrary scanlines.
    yield* until(Math.max(0,b.start-0.16));
    if(previous) {
      spawn(previous.opacity(0,0.52,easeInOutCubic));
    }
    yield* until(b.start);
    for(const figure of incoming.people) {
      spawn(setPose(figure,['think','explain','point','point','explain','shrug','cheer'][i%7],0.65));
    }
    yield* all(scene.opacity(1,0.8,easeOutCubic),
      scene.y(0,0.82,easeOutCubic),
      scene.scale(1,0.9,easeOutCubic));
    if(previous)previous.remove();
    previous=scene;
    // A quiet living composition instead of rapid wobbling animations.
    spawn(scene.scale(1.015,Math.max(1.1,b.end-b.start-1),easeInOutCubic));
  }
  if(data.end_card_start!==null) {
    yield* until(data.end_card_start);
    if(previous){yield* previous.opacity(0,0.45);previous.remove();}
    // Real Insidir end branding is added downstream by captions/end-card.
    const [mark,fig]=makeFigure(IVORY,10,0,-360);
    view.add(mark);
    yield* figureIn(fig,0.7);
    yield* setPose(fig,'stand',0.45);
  }
  yield* until(data.total);
}
