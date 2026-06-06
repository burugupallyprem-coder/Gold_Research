"""
tools/make_report.py
---------------------
Generates Strategy_Assessment.pdf — the honest status + teardown report.
"""

from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, HRFlowable)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Strategy_Assessment.pdf"

NAVY = colors.HexColor("#1f3a5f")
GOLD = colors.HexColor("#b8860b")
RED = colors.HexColor("#a11")
GREEN = colors.HexColor("#1a7f37")
GREY = colors.HexColor("#555555")
LIGHT = colors.HexColor("#f2f2f2")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=NAVY, fontSize=16, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=NAVY, fontSize=12.5, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=9.7, leading=14, spaceAfter=6)
SMALL = ParagraphStyle("SMALL", parent=styles["Normal"], fontSize=8.3, leading=11, textColor=GREY)
TITLE = ParagraphStyle("TITLE", parent=styles["Title"], textColor=NAVY, fontSize=22, spaceAfter=2)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontSize=10.5, textColor=GOLD, spaceAfter=2)
BULLET = ParagraphStyle("BULLET", parent=BODY, leftIndent=14, bulletIndent=2, spaceAfter=3)

story = []


def p(t, s=BODY): story.append(Paragraph(t, s))
def sp(h=8): story.append(Spacer(1, h))
def rule(): story.append(HRFlowable(width="100%", thickness=0.8, color=GOLD, spaceBefore=4, spaceAfter=8))


def tbl(data, widths, header_bg=NAVY, font=8.6):
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    t.setStyle(TableStyle(st))
    story.append(t)


# ───────────────────── Cover ─────────────────────
p("Gold SMC v8 — XAU/USD Backtesting Bot", TITLE)
p("Honest Status &amp; Strategy Assessment", SUB)
p(f"Generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC &nbsp;•&nbsp; "
  f"repo: OANDA_Backtesting_bot &nbsp;•&nbsp; prepared for Prem", SMALL)
rule()
p("<b>Bottom line up front.</b> The software is built and unit-tested, but "
  "<b>no real-market verdict exists yet</b> because the only data run through it "
  "so far is synthetic (random-walk) data used to test the plumbing. I also "
  "<b>cannot verify the live OANDA / Slack / GitHub connections from my build "
  "environment</b> (it has no internet to those services), and I cannot push to "
  "GitHub for you from here. This report states exactly what is proven, what is "
  "not, and a ruthless list of where the strategy and the engine are weak.", BODY)
p("Read this as a skeptic would. The honest expectation for a discretionary-style "
  "SMC strategy, after realistic costs, is little-to-no edge. Building the machine "
  "that can prove that cheaply is the real win.", SMALL)
sp(6)

# ───────────────────── 1. Connection status ─────────────────────
p("1 &nbsp; Connection &amp; verification status", H1)
p("You asked whether OANDA, Slack, and GitHub are all wired and working. Here is "
  "the truthful state of each. &#x201C;Verified&#x201D; means I actually tested it; "
  "I will not call something working that I could not test.", BODY)
tbl([
    ["Connection", "Status", "What is true", "What you must do"],
    ["Slack channel\nC0B88CUAZPD", "Reachable (smoke-tested)",
     "I posted a test message to the channel via a connector; the channel ID is valid and postable.",
     "Create the bot's own xoxb token (chat:write), invite it to the channel, put it in GitHub Secrets."],
    ["OANDA API\n(practice)", "NOT verified",
     "My sandbox is blocked from OANDA's API, so I could not confirm the key is valid or pull any candles.",
     "Run data/fetch_oanda.py locally/CI; rotate the key (it was shared in chat)."],
    ["GitHub repo", "NOT pushed",
     "My sandbox cannot reach GitHub; the code lives only in your local OANDA folder right now.",
     "Run the git push commands (Section 7) once from your machine."],
    ["End-to-end\ncloud loop", "NOT live yet",
     "Code + workflow are ready, but the loop has never executed against real services.",
     "After push + secrets, trigger the Actions workflow once manually to confirm."],
], [1.15*inch, 1.15*inch, 2.5*inch, 2.1*inch])
sp(4)
p("So: <b>one of three connections is confirmed (Slack channel reachable); the "
  "OANDA key and the GitHub push are unverified and require you.</b> I will not "
  "pretend the loop is running when it is not.", SMALL)

story.append(PageBreak())

# ───────────────────── 2. What results exist ─────────────────────
p("2 &nbsp; What results actually exist", H1)
p("<b>None on real data.</b> Every number below comes from <b>synthetic "
  "random-walk candles</b> generated only to exercise the code paths. They say "
  "nothing about whether the strategy makes money. Treat them as a smoke test of "
  "the machine, not a backtest.", BODY)
p("2.1 &nbsp; What IS proven (engineering)", H2)
tbl([
    ["Check", "Result", "Meaning"],
    ["Engine mechanics unit tests", "9 / 9 pass",
     "No look-ahead, correct cost direction, pessimistic stop-before-target, break-even logic, flat-only."],
    ["Signal parity (fast vs reference)", "0 mismatches",
     "The fast vectorized signal path reproduces the ported strategy bar-for-bar."],
    ["End-to-end pipeline", "Runs in ~3.4 s on 8,256 bars",
     "Fetch → backtest → metrics → reports → memory → Slack summary all execute."],
], [2.1*inch, 1.25*inch, 3.55*inch])
sp(4)
p("During testing the engine actually caught a real bug — break-even was arming "
  "off a bar's high and then stopping out off the same bar's low, which would have "
  "flattered results. That was fixed and is covered by a test.", SMALL)

p("2.2 &nbsp; Synthetic plumbing numbers (MEANINGLESS for edge)", H2)
tbl([
    ["Metric", "Synthetic value", "Note"],
    ["Trades", "72", "On fake data"],
    ["Win rate", "30.6%", "Noise"],
    ["Profit factor", "1.16", "Noise; ~1.0 = no edge"],
    ["Expectancy", "0.09 R", "Noise"],
    ["Walk-forward OOS PF", "1.18", "In-sample folds hit PF 3.8–4.6 then decayed to 0.0–1.5 out-of-sample"],
], [1.7*inch, 1.3*inch, 3.9*inch])
sp(3)
p("The walk-forward already demonstrates the single most important lesson: "
  "<b>in-sample profit factors of 3.8–4.6 collapsed to 0.0–1.5 out-of-sample.</b> "
  "On random data that is expected — but it is exactly the pattern that exposes "
  "curve-fitting, and it is why you must judge the strategy on out-of-sample "
  "numbers only.", BODY)

story.append(PageBreak())

# ───────────────────── 3. Is the strategy working ─────────────────────
p("3 &nbsp; Is your strategy working?", H1)
p("<b>Unknown — and that is the honest answer.</b> No real XAU/USD data has been "
  "run, so anyone who tells you it works (or doesn't) right now is guessing. What "
  "I can give you is the prior, and it is not flattering:", BODY)
p("• The strategy is built on Smart-Money-Concepts ideas (displacement, fair-value "
  "gaps, NY-opening). These have a large retail following but <b>no published, "
  "cost-adjusted statistical edge.</b> The burden of proof is on the strategy, and "
  "nothing has met it yet.", BULLET)
p("• Your original edge claim came from a TradingView backtest, which almost "
  "certainly overstates real performance (bar-close fills, no slippage, no failed "
  "orders, parameter optimization bias). Expect live/honest results materially "
  "worse.", BULLET)
p("• The most probable outcome of an honest backtest is <b>profit factor near 1.0 "
  "and expectancy near 0 after costs.</b> If the numbers come back strongly "
  "positive, be <i>more</i> suspicious, not less — check for look-ahead and data "
  "quirks first.", BULLET)
sp(2)
p("This is not me being negative — it is the same standard real quant desks apply. "
  "A project that can cheaply <i>disprove</i> a bad idea is worth more than one "
  "that cheerleads a curve.", SMALL)

# ───────────────────── 4. Strategy loopholes ─────────────────────
p("4 &nbsp; Where the strategy is weak (the bad list)", H1)
items = [
    ("No demonstrated edge", "Displacement/FVG/NY-opening are pattern folklore; "
     "without out-of-sample, cost-adjusted proof, assume zero alpha."),
    ("Optimization / backtest bias", "Parameters were chosen on TradingView history; "
     "they fit the past, not the future."),
    ("Confidence gate adds no alpha", "Blending several signals that individually "
     "have no proven edge into a 0–100 score does not create edge. It is good "
     "engineering, not a money-maker."),
    ("Macro layer is inert in backtest", "The daily-ETF macro bias is set to NEUTRAL "
     "for the backtest (it is too slow to matter intraday and is more noise than "
     "signal), so the &#x2018;intelligence layer&#x2019; contributes nothing here."),
    ("News sentiment is keyword-based", "Negation breaks it (&#x2018;rate cut "
     "delayed&#x2019; scores bullish). Only the FOMC/CPI stand-down is robust, and "
     "it is not even modelled in the backtest."),
    ("Low trade frequency", "Max 3 trades/day + flat-only means few trades; you need "
     "many months of data before any win rate is statistically meaningful."),
    ("Single instrument / single regime", "XAU/USD only. If gold enters a long "
     "choppy range, the strategy has nowhere to hide."),
    ("Tick-volume proxy", "OANDA &#x2018;volume&#x2019; is tick count, not traded "
     "contracts, so the volume filter is approximate."),
]
data = [["#", "Weakness", "Why it matters"]]
for i, (a, b) in enumerate(items, 1):
    data.append([str(i), Paragraph(f"<b>{a}</b>", SMALL), Paragraph(b, SMALL)])
tbl(data, [0.3*inch, 1.7*inch, 4.9*inch])

story.append(PageBreak())

# ───────────────────── 5. Engine loopholes ─────────────────────
p("5 &nbsp; Where the engine is limited (honest gaps)", H1)
p("The engine is unit-tested and faithful, but every backtester makes assumptions. "
  "Here are mine, so you know exactly what the numbers will and will not capture:", BODY)
eng = [
    ("Constant costs", "Spread &amp; slippage are fixed. Real spreads widen at "
     "session opens, rollover, and around news — not modelled per-bar. Results may "
     "be optimistic in those windows."),
    ("Intrabar path unknown", "Within a 15-min bar I assume stop-before-target "
     "(pessimistic). True ordering is invisible; a different assumption shifts "
     "marginal trades."),
    ("Assumed fills", "No partial fills, no liquidity/gap modelling — the model "
     "always fills at the next bar's open plus costs."),
    ("Swing-stop lag", "Pivots are confirmed 5 bars later (faithful to the Pine "
     "script), so swing-based stops use information that lags the entry by 5 bars."),
    ("HTF warmup hack", "Before ~50 four-hour bars exist, the trend filter falls "
     "back to an M15 moving average — a weaker proxy for the first ~8 days of any "
     "data window."),
    ("No sizing constraints", "OANDA minimum trade size, margin, and financing/"
     "carry are not enforced in the backtest."),
    ("Small optimization grid", "Walk-forward sweeps only displacement × threshold; "
     "and optimizing at all invites overfitting if the grid grows."),
    ("Short history & no significance test", "Default 730 days = one macro regime; "
     "there is no Monte-Carlo or p-value on the equity curve yet."),
]
data = [["#", "Limitation", "Impact / what it does not capture"]]
for i, (a, b) in enumerate(eng, 1):
    data.append([str(i), Paragraph(f"<b>{a}</b>", SMALL), Paragraph(b, SMALL)])
tbl(data, [0.3*inch, 1.6*inch, 5.0*inch])
sp(4)
p("None of these are bugs — they are disclosed assumptions. The cost-stress run "
  "(<font face='Courier'>--spread 0.6 --slippage 0.3</font>) is built in precisely "
  "so you can see how fragile any &#x2018;edge&#x2019; is to them.", SMALL)

# ───────────────────── 6. What to fix ─────────────────────
p("6 &nbsp; What to fix / the path to a real verdict", H1)
p("1. <b>Get real data.</b> Run <font face='Courier'>python data/fetch_oanda.py</font> "
  "(needs your account id + network). Nothing is real until this runs.", BULLET)
p("2. <b>Run the backtest &amp; walk-forward</b> and read the out-of-sample numbers "
  "in <font face='Courier'>reports/</font>, not the in-sample ones.", BULLET)
p("3. <b>Run the cost-stress variant.</b> If a wider spread kills the edge, the "
  "edge was never real.", BULLET)
p("4. <b>Fill in VERDICT.md</b> with which of the three branches the numbers land "
  "in (no edge / marginal / robust). Branch 1 is the likely and acceptable outcome.", BULLET)
p("5. <b>Only if out-of-sample survives costs</b>, consider a small live OANDA "
  "paper loop — with continued skepticism.", BULLET)
sp(4)

# ───────────────────── 7. Deployment ─────────────────────
p("7 &nbsp; Deploying to the cloud (you must run these)", H1)
p("I cannot push from my environment. From your machine, in the OANDA folder:", BODY)
code = ("git init &amp;&amp; git add . &amp;&amp; git commit -m \"OANDA backtesting bot\"<br/>"
        "git branch -M main<br/>"
        "git remote add origin https://github.com/burugupallyprem-coder/OANDA_Backtesting_bot.git<br/>"
        "git push -u origin main")
story.append(Paragraph(code, ParagraphStyle("code", parent=SMALL, fontName="Courier",
              backColor=LIGHT, borderPadding=6, leading=13)))
sp(6)
p("Then in GitHub → Settings → Secrets and variables → Actions, add: "
  "<b>OANDA_API_KEY</b>, <b>OANDA_ACCOUNT_ID</b>, <b>SLACK_BOT_TOKEN</b>, "
  "<b>SLACK_CHANNEL_ID</b> (C0B88CUAZPD). Set Actions → Workflow permissions to "
  "&#x201C;Read and write&#x201D;. The workflow then runs Mon–Fri 22:00 UTC "
  "(refresh + backtest) and Fri 22:30 UTC (weekly review), commits results, and "
  "posts to Slack — no laptop required. Confirm <font face='Courier'>.env</font> "
  "is NOT in the commit (it is gitignored).", BODY)
sp(6)
p("Prepared honestly. If a number ever looks too good, suspect the backtest before "
  "believing the strategy.", SMALL)

doc = SimpleDocTemplate(str(OUT), pagesize=LETTER,
                        topMargin=0.7*inch, bottomMargin=0.7*inch,
                        leftMargin=0.7*inch, rightMargin=0.7*inch,
                        title="Gold SMC v8 — Strategy Assessment")
doc.build(story)
print(f"WROTE {OUT}")
