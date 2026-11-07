// Insidir terminal promos. Each scene is pure data + markup; terminal.html animates it.
// data-in="kind,start,duration": fade | type (scramble-in) | count (money, data-to) |
// pct | ratio | bar (data-w %) | draw (svg path) | pop (svg circle, data-to = radius)
// All figures are ILLUSTRATIVE placeholders: swap in a real, approved filing before posting.

const SCENES = {
  tsla: {
    duration: 10,
    badge: "WHALE TELEMETRY • $10M+ INSIDIR ALERT",
    sub: "FORM 4 TELEMETRY • <b>SEC EDGAR VERIFIED</b>",
    tagline: "Stop trading on 3-day lag.",
    logTop: 1440, logStart: 3.6,
    log: [
      "> GET  edgar/form4 --stream ............ OK",
      "> PARSE transactionCode == P ........ MATCH",
      "> CHECK value >= 10,000,000 .......... PASS",
      "> PUSH alert $TSLA -> terminal ........ OK",
    ],
    body: `
      <div class="card" data-in="fade,0.7,0.6">
        <div class="lbl" data-in="type,0.9,0.5">TICKER · NASDAQ</div>
        <div class="tick" data-in="type,1.0,0.8">$TSLA</div>
        <div class="chip" data-in="fade,1.6,0.4">$TSLA | CODE P (BUY)</div>
        <div class="hr"></div>
        <div class="lbl" data-in="type,1.8,0.5">TRANSACTION VALUE</div>
        <div class="val glow" data-in="count,1.9,1.6" data-to="12450000">$12,450,000</div>
        <div class="desc" data-in="fade,2.6,0.6"><b>Chief Executive Officer</b> • Code P<br>(Open Market Purchase)</div>
      </div>
      <div class="grid" data-in="fade,3.0,0.6">
        <div class="cell"><div class="k">FILING</div><div class="v">FORM 4</div></div>
        <div class="cell"><div class="k">CODE</div><div class="v g">P · OPEN MKT</div></div>
        <div class="cell"><div class="k">THRESHOLD</div><div class="v">≥ $10,000,000</div></div>
        <div class="cell"><div class="k">SIGNAL</div><div class="v g">WHALE ALERT</div></div>
      </div>`,
  },

  nvda: {
    duration: 10,
    badge: "CLUSTER ACCUMULATION DETECTED • 3 INSIDERS BUYING",
    badgeSize: 22,
    sub: "FORM 4 · 3 FILINGS · SAME ISSUER · <b>CODE P</b>",
    tagline: "Institutional Form 4 telemetry.",
    logTop: 1390, logStart: 4.2,
    log: [
      "> GROUP filings BY issuer=NVDA ....... OK",
      "> COUNT insiders(code=P) == 3 ...... MATCH",
      "> FLAG  cluster_accumulation ........ ALERT",
    ],
    body: `
      <div class="card" data-in="fade,0.7,0.6" style="padding:36px 48px">
        <div class="lbl" data-in="type,0.9,0.5">ISSUER · NASDAQ</div>
        <div class="tick md" data-in="type,1.0,0.8">$NVDA</div>
        <div class="chip" data-in="fade,1.6,0.4">CLUSTER · 3 × CODE P (BUY)</div>
      </div>
      <div class="row" data-in="fade,1.9,0.5">
        <div><div class="who">CEO</div><div class="meta2">CODE P · OPEN MARKET</div></div>
        <div class="amt glow" data-in="count,2.0,1.4" data-to="8900000">$8,900,000</div>
        <div class="bar" data-in="bar,2.0,1.4" data-w="100"></div>
      </div>
      <div class="row" data-in="fade,2.3,0.5">
        <div><div class="who">CFO</div><div class="meta2">CODE P · OPEN MARKET</div></div>
        <div class="amt glow" data-in="count,2.4,1.4" data-to="2100000">$2,100,000</div>
        <div class="bar" data-in="bar,2.4,1.4" data-w="23.6"></div>
      </div>
      <div class="row" data-in="fade,2.7,0.5">
        <div><div class="who">DIRECTOR</div><div class="meta2">CODE P · OPEN MARKET</div></div>
        <div class="amt glow" data-in="count,2.8,1.4" data-to="1400000">$1,400,000</div>
        <div class="bar" data-in="bar,2.8,1.4" data-w="15.7"></div>
      </div>
      <div data-in="fade,3.4,0.6" style="display:flex;justify-content:space-between;align-items:baseline;margin-top:30px;padding:0 34px">
        <div class="lbl">CLUSTER TOTAL</div>
        <div class="glow" style="font-size:60px;font-weight:800;color:var(--em)" data-in="count,3.4,1.2" data-to="12400000">$12,400,000</div>
      </div>`,
  },

  pltr: {
    duration: 10,
    badge: "INSIDER DIP SWEEP • POST-EARNINGS ACCUMULATION",
    badgeSize: 23,
    sub: "FORM 4 · <b>CODE P</b> · OPEN MARKET PURCHASE",
    tagline: "Institutional Form 4 Telemetry",
    logTop: 1475, logStart: 4.0,
    log: [
      "> CALC  vwap_30d(PLTR) ............... OK",
      "> DELTA fill_vs_vwap = -4.2% ....... MATCH",
      "> TAG   dip_sweep · post_earnings ... ALERT",
    ],
    body: `
      <div class="card" data-in="fade,0.7,0.6" style="padding:38px 48px">
        <div class="lbl" data-in="type,0.9,0.5">TICKER · NASDAQ</div>
        <div class="tick" data-in="type,1.0,0.8">$PLTR</div>
        <div class="chip" data-in="fade,1.6,0.4">$PLTR | CODE P (BUY)</div>
        <div class="hr" style="margin:28px 0"></div>
        <div class="lbl" data-in="type,1.8,0.5">TRANSACTION VALUE</div>
        <div class="val glow" data-in="count,1.9,1.6" data-to="3400000">$3,400,000</div>
        <div class="desc" data-in="fade,2.6,0.6">Purchased <b style="color:var(--em)">-4.2%</b> below 30-day VWAP</div>
      </div>
      <div class="card" data-in="fade,2.9,0.5" style="margin-top:22px;padding:22px 28px">
        <svg width="904" height="250" viewBox="0 0 904 250">
          <line x1="0" y1="96" x2="904" y2="96" stroke="#7c817f" stroke-width="2" stroke-dasharray="8 8" data-in="draw,3.0,0.8"/>
          <text x="904" y="126" text-anchor="end" fill="#7c817f" font-size="18" letter-spacing="2" data-in="fade,3.2,0.4">VWAP · 30D</text>
          <path d="M0 70 L60 62 L120 80 L180 74 L240 92 L300 86 L360 120 L410 168 L450 196 L490 184 L540 200 L590 176 L650 150 L710 128 L770 110 L830 104 L904 88"
                fill="none" stroke="#f4f4f2" stroke-width="3" stroke-linejoin="round" data-in="draw,3.1,1.4"/>
          <line x1="540" y1="96" x2="540" y2="200" stroke="#34d399" stroke-width="2" data-in="fade,4.2,0.4"/>
          <circle cx="540" cy="200" r="0" fill="#34d399" style="filter:drop-shadow(0 0 10px #34d399)" data-in="pop,4.2,0.4" data-to="11"/>
          <text x="540" y="238" text-anchor="middle" fill="#34d399" font-size="22" font-weight="700" data-in="fade,4.3,0.4">INSIDER BUY · -4.2% vs VWAP</text>
          <text x="0" y="236" fill="#4c514f" font-size="18" letter-spacing="2" data-in="fade,3.2,0.4">EARNINGS ▸</text>
        </svg>
      </div>`,
  },

  semi: {
    duration: 10,
    badge: "FORM 4 SECTOR TELEMETRY • BUY/SELL RATIO",
    badgeSize: 25,
    sub: "SECTOR: SEMICONDUCTORS · WINDOW: <b>TRAILING 30D</b>",
    tagline: "Unlock Full Terminal",
    logTop: 1380, logStart: 4.2,
    log: [
      "> SCAN  sector=SEMIS form=4 ......... OK",
      "> SUM   code=P vs code=S ............ OK",
      "> RATIO buy/sell = 2.44 ........... ALERT",
    ],
    body: `
      <div class="lbl" data-in="type,0.8,0.5" style="margin-top:6px">SECTOR FLOW · CODE P vs CODE S</div>
      <div data-in="type,0.9,0.9" style="font-size:88px;font-weight:800;line-height:1.05;margin:14px 0 26px -4px">SEMICONDUCTOR</div>
      <div data-in="type,1.1,0.9" style="font-size:88px;font-weight:800;line-height:1.05;margin:-26px 0 30px -4px;color:#c9ccca">INSIDER FLOW</div>
      <div class="card" data-in="fade,1.4,0.6" style="padding:36px 44px">
        <div class="flow" style="margin-top:0">
          <div class="top"><div class="name">INSIDER BUYS · P</div><div class="sum glow" style="color:var(--em)" data-in="count,1.8,1.6" data-to="48260000">$48,260,000</div></div>
          <div class="track"><div class="fill buy" data-in="bar,1.8,1.6" data-w="100"></div></div>
        </div>
        <div class="flow" style="margin-top:38px">
          <div class="top"><div class="name">INSIDER SELLS · S</div><div class="sum" style="color:#e8e8e6" data-in="count,2.2,1.6" data-to="19740000">$19,740,000</div></div>
          <div class="track"><div class="fill sell" data-in="bar,2.2,1.6" data-w="40.9"></div></div>
          <div class="ticks"><span>$0</span><span>$12M</span><span>$24M</span><span>$36M</span><span>$48M</span></div>
        </div>
      </div>
      <div class="grid" data-in="fade,3.2,0.6" style="margin-top:22px">
        <div class="cell"><div class="k">BUY/SELL RATIO</div><div class="v g glow" style="font-size:44px" data-in="ratio,3.3,1.2" data-to="2.44">2.44x</div></div>
        <div class="cell"><div class="k">NET INSIDER FLOW</div><div class="v g" style="font-size:44px">+$28,520,000</div></div>
      </div>`,
  },
};
