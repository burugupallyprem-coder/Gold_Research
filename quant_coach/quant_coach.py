"""
quant_coach.py
==============
Your personal Quant Project Coach. Teaches you the Gold Quant Lab project you
built — ONE detailed concept per day, explained step by step, with a worked
example, a self-check, and the exact words to say in an interview.

Cadence (not hourly — by design):
  • Morning (~8 AM): the full, detailed lesson for the day.
  • Evening (~8 PM): the matching interview drill for the SAME concept, then it
    advances to the next day's topic.

State in memory/coach_state.json. Posts to one Slack channel. Teaches only —
no trades, no money.

Setup:
  1. Copy .env.example to .env, set SLACK_BOT_TOKEN and QUANT_COACH_CHANNEL_ID.
  2. pip install -r requirements.txt
  3. register_quant_coach.ps1 (Run as Administrator) — schedules 8 AM + 8 PM.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "memory" / "coach_state.json"
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)
(BASE / "memory").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "quant_coach.log", encoding="utf-8"),
              logging.StreamHandler()])
log = logging.getLogger("quant_coach")

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN", "").strip()
SLACK_CHANNEL = os.getenv("QUANT_COACH_CHANNEL_ID", "C0B8C1XBWGP").strip()

# =============================================================================
# DAILY CURRICULUM — one deep concept per day. Each lesson is fully detailed.
# =============================================================================

DAILY = [
{"title": "The Story — your 60-second pitch",
 "lesson": """*Today's goal:* be able to tell the whole project as one clean story.

*The arc (memorize the shape):*
1️⃣ You took a popular retail strategy (Smart-Money-Concepts on intraday gold).
2️⃣ You tested it honestly and *proved it had no edge* after costs.
3️⃣ Instead of curve-fitting it, you *replaced* it with a strategy backed by real academic evidence (daily trend-following + a real-yield filter + volatility targeting).
4️⃣ That one *survived* out-of-sample testing — a modest, real edge.
5️⃣ You then *automated* the research so it improves itself, and added a safety-railed paper-trading layer.

*Why this story wins:* most candidates show a project that "worked." You show one where you *killed your own idea with evidence* — that signals scientific maturity, which is rare and exactly what trading firms want.

*Worked example — say this out loud, time yourself (target 60s):*
_"I built a cloud-native quant research system for spot gold. I ported an intraday SMC strategy to Python, ran it through walk-forward and cost-stress testing, and proved it had no edge after costs. Rather than over-fit it, I switched to a daily time-series-momentum strategy with a real-yield filter and volatility targeting, which held up out-of-sample. Then I wrapped it in an autonomous champion/challenger loop with a permanent holdout, plus a paper-execution module with hard risk controls. It all runs unattended on GitHub Actions and reports to Slack."_

*Self-check:* What's the single most impressive sentence here? → _"I proved my own strategy had no edge and walked away from it."_

📌 *Tomorrow:* what a backtest actually is, and the three ways they lie.""",
 "drill": """*Interviewer:* "Walk me through a project you're proud of."

*What they're testing:* can you tell a clear story with judgment, not just a feature list.
*Common mistake:* listing tools, or overclaiming profits.

*Your answer (read aloud, then say your own version):*
_"I built a cloud-native quant research system for spot gold. I ported an intraday Smart-Money-Concepts strategy, tested it with realistic costs and out-of-sample data, and proved it had no edge. Instead of curve-fitting, I replaced it with a daily time-series-momentum strategy with a real-yield filter and volatility targeting — which survived out-of-sample. I then built an autonomous champion/challenger loop with a permanent holdout so it self-improves without overfitting, and a safety-railed paper executor. Everything runs unattended on GitHub Actions."_

🎯 Record yourself once. Listen back. Cut any sentence that sounds like a buzzword."""},

{"title": "What a backtest is — and the 3 ways it lies",
 "lesson": """*What it is:* a backtest replays historical prices through your strategy's rules to estimate how it *would* have performed. It's the core tool of systematic trading — and the easiest thing in finance to fake.

*Why it matters:* a good-looking backtest is nearly worthless on its own, because three subtle errors make almost any strategy look profitable:

*The 3 lies (learn these cold):*
• *Look-ahead bias* — using information you couldn't have had at decision time (e.g., today's close to decide today's trade).
• *Ignoring costs* — assuming zero spread, zero slippage, perfect fills. Real trading bleeds money on every transaction.
• *Overfitting* — tuning parameters until they perfectly fit *past noise*, which never repeats.

*How you built around all three:*
• No look-ahead → signal on a *closed* bar, fill on the *next* bar's open.
• Costs → half-spread + slippage on every fill, plus a 5× cost-stress test.
• Overfitting → walk-forward + a permanent holdout the optimizer can't touch.

*Picture it:* a backtest is like grading your own exam with the answer key visible. The three lies are three ways the answer key leaks in. Your job as a quant is to seal every leak.

*Self-check:* If a backtest shows a 90% win rate, what's your first reaction? → _Suspicion. Look for look-ahead, missing costs, or overfitting before believing it._

📌 *Tomorrow:* look-ahead bias in depth — the most dangerous of the three.""",
 "drill": """*Interviewer:* "Why don't you trust most backtests?"

*What they're testing:* do you understand the failure modes, not just the mechanics.
*Common mistake:* saying "you should use more data" (misses the real issues).

*Your answer:*
_"Because three errors make almost any strategy look good: look-ahead bias, ignoring transaction costs, and overfitting to past noise. A backtest is only meaningful if it's free of all three — computed on closed bars, charged realistic costs, and validated out-of-sample. In my project, the strategy that looked best in-sample actually had no edge once I sealed those three leaks."_

🎯 Practice naming the three lies in under 10 seconds."""},

{"title": "Look-ahead bias — and how you killed it",
 "lesson": """*What it is:* using future information to make a past decision. It's the #1 reason backtests look amazing and live trading disappoints.

*The classic trap:* you decide to buy *using a bar's closing price*, then assume you *bought at that same close*. But in reality, the moment you know the close, the bar is over — you can only act on the *next* bar. Tiny mistake, huge effect.

*How you built around it (step by step):*
1. The strategy computes its signal only on a bar that has *already closed*.
2. If a signal fires, the *fill* is simulated at the *next* bar's *open* — a price you genuinely could have traded at.
3. You proved this is airtight with a *parity test*: a fast vectorized version of the logic matches the careful reference version *bar-for-bar*, so there's no hidden leak.

*Why it matters:* even a 1-bar leak can turn a losing strategy into a "winner" on paper. Eliminating it is the difference between research and self-deception.

*Picture it:* it's like betting on a horse race after seeing the first horse cross the line. Of course you'd "win." No-look-ahead forces you to bet *before* the gate opens.

*Self-check:* Your signal triggers on Monday's close. When do you fill? → _Tuesday's open, with costs._ Never Monday's close.

📌 *Tomorrow:* transaction costs — why they quietly kill most strategies.""",
 "drill": """*Interviewer:* "What is look-ahead bias and how do you prevent it?"

*What they're testing:* core competence — this is a screening question.
*Common mistake:* a vague definition with no concrete safeguard.

*Your answer:*
_"Look-ahead bias is using information you wouldn't have had in real time. The classic version is deciding on a bar's close and pretending you filled at that close. In my engine, signals are computed only on closed bars and filled at the next bar's open, so no bar can use its own future. I verified it with a parity test — a vectorized fast path matches the reference implementation bar-for-bar."_

🎯 If you can answer this crisply, you pass most first-round quant screens."""},

{"title": "Transaction costs — the silent strategy killer",
 "lesson": """*What it is:* the money you lose just by trading — mainly the *spread* (the gap between the price to buy and the price to sell) and *slippage* (price moving against you between your decision and your fill).

*Why it matters:* many strategies are profitable *before* costs and losers *after*. The more often you trade, the more costs eat you — which is why intraday strategies are so fragile and daily strategies are robust.

*How you built it (step by step):*
1. On *every* entry and exit, charge half the spread plus a slippage amount — both make your fill slightly worse, like in real life.
2. Resolve intrabar conflicts *pessimistically*: if a single bar's range touches *both* your stop-loss and your target, assume the *stop* hit first. Never give yourself the benefit of the doubt.
3. Run a *cost-stress test*: re-run with 5× the costs. If the edge survives, it's robust; if it vanishes, it was never real.

*The punchline from your own project:* the intraday SMC strategy made money with cheap fills but, under the 5× cost-stress, its profit factor fell *below 1.0* — it lost. That single test exposed it as fake.

*Picture it:* costs are friction. A strategy that only wins on a frictionless ice rink will fall over on real pavement.

*Self-check:* Two strategies have the same gross return; one trades 5×/day, one 5×/quarter. Which keeps more? → _The low-frequency one — far less cost drag._

📌 *Tomorrow:* in-sample vs out-of-sample, and walk-forward testing.""",
 "drill": """*Interviewer:* "How do you model transaction costs, and why does it matter?"

*What they're testing:* realism — do you know costs make or break a strategy.
*Common mistake:* hand-waving costs or leaving them out.

*Your answer:*
_"Half-spread plus adverse slippage on every fill, and pessimistic intrabar resolution — if a bar touches both stop and target, I assume the stop filled first. I also run a 5× cost-stress test. It matters enormously: my intraday strategy was positive before costs and a net loser after. Most retail backtests only look good because they assume free, perfect fills."_

🎯 Always volunteer the cost-stress idea — it shows discipline."""},

{"title": "In-sample vs out-of-sample & walk-forward",
 "lesson": """*The key distinction:*
• *In-sample* = the data you used to build and tune the strategy. Results here are almost always flattering and mostly meaningless.
• *Out-of-sample (OOS)* = data the strategy has *never seen*. This is the only result that tells you anything real.

*Walk-forward (the gold standard):*
1. Optimize the parameters on a chunk of history (the "train" window).
2. Test them on the *next, unseen* chunk (the "test" window).
3. Slide both windows forward and repeat.
4. Stitch all the test windows together — that's your honest out-of-sample track record.

*Why it matters:* if a strategy looks brilliant in-sample but falls apart out-of-sample, you were *curve-fitting* — fitting noise, not signal. Walk-forward catches this automatically.

*How you used it:* your SMC verdict came from *534 out-of-sample trades* — a big enough sample to trust. The result: expectancy slightly negative. That's a trustworthy "no."

*Picture it:* studying last year's exam answers (in-sample) feels like mastery. The real test is *this year's* exam (out-of-sample). Only the new exam measures learning.

*Self-check:* A strategy shows profit factor 3.0 in-sample and 0.9 out-of-sample. Verdict? → _No edge. The in-sample number is curve-fit; only the OOS 0.9 (a loser) matters._

📌 *Tomorrow:* overfitting and the multiple-testing trap.""",
 "drill": """*Interviewer:* "How do you know a backtest result is real and not luck?"

*What they're testing:* out-of-sample discipline.
*Common mistake:* citing a great in-sample number.

*Your answer:*
_"I only trust out-of-sample, walk-forward results. I optimize on one window, test on the next unseen one, roll forward, and judge the strategy on the stitched-together test periods. If in-sample is strong but out-of-sample collapses, that's curve-fitting. My first strategy failed exactly that test across 534 out-of-sample trades."_

🎯 The phrase "out-of-sample, walk-forward" should be reflexive for you."""},

{"title": "Overfitting & the multiple-testing trap",
 "lesson": """*What it is:* overfitting is tuning a strategy until it fits the *random noise* of past data instead of a real, repeatable pattern. An overfit strategy looks perfect on history and fails live.

*The multiple-testing trap (subtle but crucial):* if you try 1,000 strategy variations, a few will look amazing *purely by chance* — like flipping 1,000 coins and celebrating the ones that landed heads 10 times in a row. The more things you test, the more "winners" are just luck.

*How you defended against it (your guardrails):*
1. *Permanent holdout* — a slice of recent data the optimizer is *never* allowed to look at, used only for a final check.
2. *Separate selection from confirmation* — you search for ideas on one slice; the holdout only confirms the *single* chosen idea, so it isn't "used up" by the search.
3. *Small, pre-registered idea set* — you test a *handful* of sensible variations, not thousands.
4. *Confirmation streak* — a new idea must beat the current one *3 weeks in a row* before it's adopted.

*Picture it:* overfitting is tailoring a suit to fit you *holding your breath*. It looks perfect in the mirror and splits the moment you move.

*Self-check:* You tested 50 variants and the best has a great holdout score. Trust it? → _Be cautious — with 50 tries, some look good by chance. Demand repeated confirmation._

📌 *Tomorrow:* alpha vs beta — telling skill from a lucky market.""",
 "drill": """*Interviewer:* "How do you avoid overfitting?"

*What they're testing:* the single most important quant skill.
*Common mistake:* "I use cross-validation" with no specifics.

*Your answer:*
_"I never trust in-sample results. I use walk-forward, keep a permanent holdout the optimizer can't see, and separate selection from confirmation so the holdout only judges the final pick. I limit how many ideas I test to control multiple-testing, and I require a challenger to beat the champion several weeks in a row before adopting it."_

🎯 Name at least three concrete guardrails — vagueness fails here."""},

{"title": "Alpha vs beta — skill vs a lucky market",
 "lesson": """*The distinction that separates pros from amateurs:*
• *Beta* = return you get just from *being exposed to the market*. If gold goes up and you're long gold, you make money with zero skill.
• *Alpha* = return from *skill* — being right when the market isn't simply trending your way.

*Why it matters:* a "gold strategy" that only makes money on the long side during a gold bull market has *no alpha* — it's just beta wearing a costume. The moment the trend stops, it stops working.

*How you tested for it:* you split every strategy's performance into its *long* trades and its *short* trades separately. A real edge should show up on *both* sides. If all the profit comes from longs during an uptrend, that's a red flag for beta.

*What it caught:* it helped reveal that the first strategy's apparent profit was mostly long-side gold beta — riding the 2023–2026 bull run — not genuine skill.

*Picture it:* a surfer riding a big wave looks skilled, but a cork floating on the same wave also goes up. Alpha is whether you can also do well in flat or choppy water.

*Self-check:* Your gold strategy made +20%, but gold itself rose +25% and all your trades were long. Alpha or beta? → _Beta — you actually underperformed just holding gold._

📌 *Tomorrow:* the falsification — exactly why the SMC strategy failed.""",
 "drill": """*Interviewer:* "What's the difference between alpha and beta?"

*What they're testing:* conceptual clarity plus application.
*Common mistake:* a textbook definition with no example.

*Your answer:*
_"Beta is return from market exposure; alpha is return from skill. In my project, a gold strategy that only profits on longs during a gold bull market has no alpha — it's just beta. I attribute returns to long versus short legs to tell them apart, and that's how I caught that my first strategy's profit was mostly long-side gold beta, not edge."_

🎯 Always pair the definition with the gold example — it lands."""},

{"title": "The falsification — why SMC had no edge",
 "lesson": """*The setup:* "Smart-Money-Concepts" (SMC) trading uses patterns like *displacement candles* (big momentum bars) and *fair-value gaps* (price gaps) to predict continuation. It's hugely popular on YouTube. You implemented it faithfully.

*The honest test (what you ran):*
• Walk-forward, out-of-sample: *534 trades*.
• Realistic costs + a 5× cost-stress.
• Long/short attribution.

*The verdict (memorize the numbers):*
• Out-of-sample *expectancy ≈ −0.016R* — the average trade lost a sliver.
• *Cost-stress profit factor 0.98* — below 1.0, i.e. it loses under realistic costs.
• Profit was mostly long-side beta, not skill.

*Why it failed (the deeper reason):* after a big intraday candle, price is about as likely to *reverse* as to *continue* — it's close to a coin flip. The strategy's win/payoff math sat right at break-even *before* costs, so costs tipped it negative. The patterns simply aren't predictive once you pay to trade them.

*The lesson you can sell in an interview:* a beautiful chart with cherry-picked examples is *the absence of evidence dressed up as evidence*. You proved that rigorously and walked away — that's the whole value.

*Self-check:* What single number best proves SMC had no edge? → _The 5× cost-stress profit factor of 0.98 — it loses once costs are realistic._

📌 *Tomorrow:* the strategy that DID work — time-series momentum.""",
 "drill": """*Interviewer:* "Tell me about a time you were wrong."

*What they're testing:* intellectual honesty and updating on evidence.
*Common mistake:* a fake weakness, or refusing to admit error.

*Your answer:*
_"I was convinced an intraday Smart-Money-Concepts strategy had an edge — it looked great on a chart. But when I tested it honestly with realistic costs and out-of-sample data, expectancy was slightly negative and it lost under cost-stress. So I killed it. That was the most valuable result in the project: my system is built to falsify my own ideas cheaply, before they cost real money."_

🎯 This answer turns a 'failure' into your strongest selling point."""},

{"title": "Time-series momentum — the real premium",
 "lesson": """*What it is:* *time-series momentum* (TSMOM) is the well-documented tendency for an asset that has been trending to *keep* trending over the medium term (weeks to months). It's one of the most robust effects in finance — shown across centuries and dozens of markets (Moskowitz, Ooi & Pedersen, 2012).

*How you implemented it (step by step):*
1. Compute two moving averages of gold's daily price: a fast 50-day EMA and a slow 200-day EMA.
2. Also compute 12-month momentum (is price higher than a year ago?).
3. *Go long* when the 50-day is above the 200-day *and* 12-month momentum is positive.
4. *Go short* when both point down. Otherwise, stand aside.

*Why it beats intraday SMC:*
• It rests on a *documented premium*, not chart folklore.
• It trades on *daily* bars — only a handful of trades a quarter — so transaction costs barely matter (remember Day 4!).
• It's simple and hard to overfit.

*The honest caveat (always say this):* TSMOM has *long flat stretches* and real drawdowns, and it whipsaws at turning points. It's a *modest* edge (~0.5 Sharpe), not a money machine.

*Picture it:* it's like sailing — you don't predict the wind, you just set your sail to whichever way it's already blowing, and adjust when it clearly shifts.

*Self-check:* Why does TSMOM tolerate costs so well? → _Low turnover — few trades, so little cost drag._

📌 *Tomorrow:* the macro filter — real yields and gold.""",
 "drill": """*Interviewer:* "Why time-series momentum, and what are its weaknesses?"

*What they're testing:* you know the premium AND its failure modes.
*Common mistake:* selling it as a sure thing.

*Your answer:*
_"TSMOM is a documented premium — trends persist medium-term — and it's cheap to trade on daily bars. Its weaknesses: it suffers in choppy, range-bound markets, whipsaws at turning points, and has long flat stretches and real drawdowns. On a single asset like gold, much of recent performance can be regime-driven beta. That's why I volatility-target, validate out-of-sample, and quote a modest ~0.5 Sharpe."_

🎯 Leading with the weaknesses makes the strength more believable."""},

{"title": "Real yields & gold — the macro filter",
 "lesson": """*The economic intuition:* gold pays no interest and no dividend. So its biggest competitor is "safe" assets that *do* pay interest. The key driver is the *real yield* — the interest rate *after* subtracting inflation — best proxied by the 10-year TIPS yield (FRED series *DFII10*).

*The relationship:*
• When real yields *fall*, holding cash/bonds pays less → gold becomes more attractive → gold tends to *rise*.
• When real yields *rise*, gold faces a headwind.

*How you used it as a filter (step by step):*
1. Pull the daily real-yield series from FRED.
2. Measure its recent momentum (is it rising or falling?).
3. Allow *long* gold trades only when real yields are flat or falling.
4. Allow *short* gold trades only when real yields are rising.

*Why it matters:* this is the *real* version of a macro signal — tied to an actual economic driver, not a chart shape. It stops the trend strategy from buying gold straight into a rising-rate headwind.

*Picture it:* real yields are gravity for gold. When gravity weakens (yields fall), gold floats up more easily; when it strengthens, gold struggles.

*Self-check:* The Fed is hiking and real yields are climbing fast. What does your filter allow? → _Shorts, not longs — gold has a headwind._

📌 *Tomorrow:* volatility targeting — sizing positions intelligently.""",
 "drill": """*Interviewer:* "What fundamental driver did you use for gold, and why?"

*What they're testing:* do you understand the asset, not just the math.
*Common mistake:* "gold is a safe haven" with nothing deeper.

*Your answer:*
_"Gold's strongest fundamental driver is the real interest rate — the 10-year TIPS yield from FRED. Gold pays no yield, so when real yields fall it becomes more attractive and tends to rise; when they rise, it faces a headwind. I used real-yield momentum as a filter: longs only when real yields are flat or falling, shorts only when they're rising. It's a macro signal tied to a real economic driver."_

🎯 Naming the FRED series (DFII10) signals you actually built it."""},

{"title": "Volatility targeting — constant risk by design",
 "lesson": """*What it is:* instead of always trading the same position size, you size so that your position's *expected volatility* hits a fixed target — say 10% annualized. Calm market → bigger position; wild market → smaller position.

*How it works (step by step):*
1. Estimate the asset's recent volatility (e.g., standard deviation of daily returns).
2. Set a target volatility (e.g., 10% per year).
3. Position size = target volatility ÷ recent volatility, capped at a maximum leverage.
4. Re-size as volatility changes.

*Why it matters:* it keeps your risk *constant and intentional* instead of *accidental*. Without it, one volatile week can dominate your whole track record. Volatility targeting is one of the few techniques shown to *reliably* improve risk-adjusted returns across many assets (Moreira & Muir, 2017).

*Where it fits your strategy:* the trend signal decides *direction*; volatility targeting decides *how much*. Together: "lean the way the trend is blowing, but only as hard as the seas allow."

*Picture it:* it's cruise control for risk. On a clear highway you can speed up; in a storm you ease off — so your "felt risk" stays steady.

*Self-check:* Gold's volatility doubles overnight. What happens to your position? → _It roughly halves — same risk, smaller size._

📌 *Tomorrow:* the four metrics that judge any strategy.""",
 "drill": """*Interviewer:* "What is volatility targeting and why use it?"

*What they're testing:* risk management maturity.
*Common mistake:* confusing it with a trade signal.

*Your answer:*
_"It's sizing the position so its expected volatility hits a fixed target — smaller in choppy markets, larger in calm ones, capped at a max leverage. It keeps risk constant and intentional rather than accidental, and it reliably improves risk-adjusted returns across assets. In my system, the trend decides direction and volatility targeting decides size."_

🎯 The line "direction vs size" shows you understand the architecture."""},

{"title": "The four metrics that judge a strategy",
 "lesson": """*You must be fluent in these four — they come up constantly:*

1️⃣ *Sharpe ratio* = return ÷ volatility (return per unit of risk). It rewards smooth, steady gains and punishes wild swings. Rough scale: ~0.5 is realistic for a single-asset trend strategy; ~1.0 is good; *>2 is suspicious* (probably overfit or a lucky regime).

2️⃣ *Profit factor (PF)* = gross profit ÷ gross loss. >1 means net positive. PF 1.2 is modest; the cost-stress version is what you trust.

3️⃣ *Maximum drawdown* = the worst peak-to-trough fall in your equity. This is the *pain* number. Your macro strategy's was *~36%* — meaning at the worst point you'd be down over a third. Respect it; it's what makes people quit.

4️⃣ *Expectancy (R)* = average profit per trade measured in units of *risk*. +0.1R means each trade nets a tenth of what it risked, on average. Your SMC strategy's was slightly *negative*.

*How to talk about them honestly:* _"My validated strategy is roughly a 0.5 Sharpe with a 36% max drawdown — a modest, real edge, not a money machine."_ Saying this *unprompted* signals you're a realist, not a hype-merchant.

*Picture it:* Sharpe is smoothness, PF is the win/loss ratio, drawdown is the worst pain, expectancy is the per-bet edge.

*Self-check:* Someone shows you an OOS Sharpe of 3.0 on one asset. Reaction? → _Suspicion — that's too high; look for overfitting or a kind regime._

📌 *Tomorrow:* the autonomous research lab.""",
 "drill": """*Interviewer:* "Which metrics do you use to evaluate a strategy, and what's a healthy range?"

*What they're testing:* fluency and realism.
*Common mistake:* quoting an unrealistically high Sharpe as if it's good.

*Your answer:*
_"Sharpe for risk-adjusted return — around 0.5 is realistic for a single-asset trend strategy, and anything above 2 makes me suspicious. Profit factor for gross win/loss, judged under cost-stress. Maximum drawdown for worst-case pain — mine was about 36%. And expectancy in R for per-trade edge. I always quote the drawdown alongside the return, because that's the number that makes people quit."_

🎯 Volunteering the drawdown is a maturity signal."""},

{"title": "The autonomous research lab (champion/challenger)",
 "lesson": """*What it is:* a loop that runs every week with *no human input* and can upgrade the strategy on the *paper* track on its own — without fooling itself.

*How it works (step by step):*
1. The current best strategy is the *champion*.
2. A small, fixed set of *challengers* (parameter variations) is tested.
3. Each is scored on a *selection* slice of data.
4. The best challenger is then checked against a *permanent holdout* — recent data the loop is *forbidden* to optimize on.
5. A challenger must beat the champion on that holdout for *3 weeks in a row* before it's *promoted*.
6. The new champion is saved to a file (its memory) and the cycle repeats.

*Why the guardrails matter:* an optimizer left unchecked will always "find" something — usually noise. The permanent holdout, the selection/confirmation split, and the 3-week streak are what make this *self-improving* rather than *self-deceiving*. (This is Day 6's lesson made into a living system.)

*The honest framing:* it improves the *research*, on paper. A human still stands between it and any real money — by design.

*Picture it:* it's a sports team with a starter (champion) and bench players (challengers). A sub only takes the starting spot after *repeatedly* outplaying them in real games — not one lucky practice.

*Self-check:* Why a 3-week streak instead of promoting the first time a challenger wins? → _One win can be luck; repeated wins on unseen data are much harder to fake._

📌 *Tomorrow:* paper execution, safety rails, and why it stays on paper.""",
 "drill": """*Interviewer:* "How does your self-improving system avoid overfitting itself?"

*What they're testing:* whether 'automation' means 'data-mining disaster' to you.
*Common mistake:* describing auto-tuning with no safeguards.

*Your answer:*
_"A permanent holdout the optimizer never tunes on; selection and confirmation are separated so the holdout only judges the final pick; a challenger must beat the champion three consecutive weeks before promotion; and I only test a small, pre-registered set of ideas. It changes the paper strategy only — a human stays between it and real capital."_

🎯 Stress 'permanent holdout' and 'three-week streak' — those are the credible details."""},

{"title": "Paper execution, safety rails & why not real money",
 "lesson": """*What it is:* the one component that actually places orders — but only on an OANDA *practice* (paper) account. Each session it computes the validated champion's *target* position and submits an order to move toward it.

*The safety rails (every one matters):*
• *STOP kill-switch* — a file that, if present, halts all trading instantly.
• *Stale-data guard* — if the latest price bar is too old, it stands down (never trade on bad data).
• *Notional cap* — position size capped at 1× account value (no leverage on paper).
• *Dry-run mode* — can simulate and log without placing anything.
• *Error handling* — any broker/API error → stand down, do nothing.
• *Locked to the champion* — it will *never* trade the lab's unconfirmed challengers.

*Why it stays on paper (two real reasons):*
1. *Discipline* — a ~0.5 Sharpe with a 36% drawdown needs *months* of live paper forward-testing before anyone risks capital.
2. *Visa* — on an F-1 student visa, running a trading bot for your own profit can count as *unauthorized self-employment*. So this is a *portfolio and learning* system — which is exactly where its value is.

*Picture it:* it's a flight simulator with every warning light wired up. You log real "flight hours" and prove competence — with zero chance of a real crash.

*Self-check:* Name two rails that prevent a bad trade. → _Stale-data guard and the notional cap (plus the STOP switch)._

📌 *Tomorrow:* the cloud architecture — how it all runs unattended.""",
 "drill": """*Interviewer:* "How would you deploy a strategy to production safely?"

*What they're testing:* risk controls and staged rollout.
*Common mistake:* jumping straight to live capital.

*Your answer:*
_"Stage it. First, paper-trade the validated strategy on a practice account as a forward-test, with hard rails: a kill-switch, a stale-data guard, a notional cap with no leverage, dry-run mode, and error handling that stands down on bad data. Monitor live results against the backtest for months. Only then consider real capital, small — and never the experimental challenger, only the validated champion."_

🎯 "Stage it" + naming specific rails = a senior-sounding answer."""},

{"title": "The architecture & the honest-quant mindset",
 "lesson": """*The architecture (draw this on a whiteboard in an interview):*
Data (OANDA prices + FRED real yields) → *strategies* (intraday SMC, daily Macro-Trend) → *backtesters* (event-driven + a vectorized fast path) → *validation gauntlet* (walk-forward, out-of-sample, cost-stress, long/short) → *research lab* (champion/challenger + holdout) → *paper executor*.

*The infrastructure (one sentence):* it's *serverless* — *GitHub Actions* runs the compute on a schedule, the *Git repo* is the database (state, logs, results all version-controlled), and *Slack* is the observability layer. No machine is ever left running.

*The mindset that ties it together (the real takeaway):* a quant's job isn't to *believe* in a strategy — it's to *try to destroy* it cheaply, and only trust what survives. Every part of this system is built to *falsify ideas fast*: no look-ahead, realistic costs, out-of-sample, permanent holdouts, cost-stress. The one strategy that survived, you treat with *measured* confidence and honest caveats.

*Your closing line for any interview:* _"I built a system that's biased toward truth over hope. It killed my first idea, validated a second with honest caveats, and improves itself without fooling itself. That discipline is what I'd bring to your desk."_

*Self-check:* In one sentence, what makes this project credible? → _It rejects ideas that don't survive honest testing — including my own._

📌 *Tomorrow:* the cycle repeats from Day 1 — each pass makes it more automatic.""",
 "drill": """*Interviewer:* "Why should we trust your judgment as a quant?"

*What they're testing:* scientific temperament.
*Common mistake:* claiming confidence in a strategy instead of in a process.

*Your answer:*
_"Because I trust process over hope. I build systems to destroy ideas cheaply and only keep what survives honest testing — no look-ahead, realistic costs, out-of-sample, permanent holdouts. In my project that meant killing my own first strategy and validating a second one with explicit caveats about its limits. I'd bring that same discipline — and the humility to quote the drawdown, not just the return — to your team."_

🎯 This is your closer. Deliver it calmly and you'll be remembered."""},
]

# =============================================================================
# STATE
# =============================================================================

def load_state() -> dict:
    defaults = {"day_index": 0, "total_sessions": 0, "streak_days": [],
                "created": datetime.now().isoformat()}
    if STATE_FILE.exists():
        try:
            defaults.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return defaults


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


# =============================================================================
# SLACK
# =============================================================================

def post_to_slack(header: str, text: str) -> bool:
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        log.warning("Slack not configured — set SLACK_BOT_TOKEN and QUANT_COACH_CHANNEL_ID in .env")
        print(f"\n{'='*60}\n{header}\n{'='*60}\n{text}\n")
        return False
    full = f"*{header}*\n\n{text}"
    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_TOKEN}",
                     "Content-Type": "application/json; charset=utf-8"},
            json={"channel": SLACK_CHANNEL, "text": full, "mrkdwn": True},
            timeout=15)
        data = resp.json()
        if data.get("ok"):
            log.info("Posted day %s to Slack.", text[:1])
            return True
        log.error("Slack error: %s", data.get("error"))
        return False
    except Exception as exc:
        log.exception("Slack post failed: %s", exc)
        return False


# =============================================================================
# MAIN  — morning: deep lesson; evening: matching drill, then advance a day.
# =============================================================================

def main() -> int:
    hour = datetime.now().hour
    today = date.today().isoformat()

    state = load_state()
    if today not in state.get("streak_days", []):
        state.setdefault("streak_days", []).append(today)
        state["streak_days"] = state["streak_days"][-365:]
    state["total_sessions"] = state.get("total_sessions", 0) + 1

    day = state.get("day_index", 0) % len(DAILY)
    entry = DAILY[day]
    streak = len(set(state.get("streak_days", [])))
    log.info("Quant Coach | Hour=%d | Day topic #%d | Session=%d", hour, day + 1, state["total_sessions"])

    if hour < 14:
        header = f"📘 Day {day + 1} of {len(DAILY)} — {entry['title']}"
        text = entry["lesson"] + f"\n\n_(Daily streak: {streak} days. Evening: the matching interview drill.)_"
    else:
        header = f"🎙️ Day {day + 1} Drill — {entry['title']}"
        text = entry["drill"]
        state["day_index"] = day + 1     # advance to next topic after the evening drill

    save_state(state)
    return 0 if post_to_slack(header, text) else 1


if __name__ == "__main__":
    sys.exit(main())
