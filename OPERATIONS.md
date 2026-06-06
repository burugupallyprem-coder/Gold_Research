# OPERATIONS — runbook

## 0. One-time secret hygiene
Your OANDA key was shared in chat, so treat it as exposed. After setup, rotate
it in the OANDA dashboard and put the fresh value only in `.env` (local) and
GitHub Secrets (cloud). Never commit it — `.env` is gitignored.

## 1. Local setup
```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env: OANDA_API_KEY=...  OANDA_ACCOUNT_ID=...  (OANDA_ENV=practice)
```
Find your account id in the OANDA dashboard (format `xxx-xxx-xxxxxxxx-xxx`).

## 2. Fetch data (must run where there is real network — your machine or CI)
```bash
python data/fetch_oanda.py --days 730
# -> data/candles/XAU_USD_M15.csv, XAU_USD_H4.csv
```
The Claude build sandbox has no network to OANDA, which is why this step is
yours. The CSVs are gitignored (regenerable, large).

## 3. Run backtests
```bash
python backtest/run2.py                      # base run
python backtest/run2.py --disp 1.4 --tag d14 # parameter sensitivity
python backtest/run2.py --spread 0.6 --slippage 0.3 --tag stress  # cost stress
python backtest/wf.py --folds 5 --train 4000 --test 1000          # walk-forward
```
Outputs land in `reports/`. Read `reports/summary_*.json` and
`reports/walkforward.json`.

## 4. Orchestrator routines
```bash
python main.py --routine backtest        # full run + memory/results.json + Slack
python main.py --routine weekly_review    # appends memory/lessons.md + Slack
python main.py --routine all --commit     # everything, then git push memory+reports
```

## 5. Cloud (GitHub Actions)
Push this repo to https://github.com/burugupallyprem-coder/OANDA_Backtesting_bot
then set repo **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| OANDA_API_KEY | your (rotated) practice token |
| OANDA_ACCOUNT_ID | your practice account id |
| SLACK_BOT_TOKEN | `xoxb-...` (bot with `chat:write`, invited to the channel) |
| SLACK_CHANNEL_ID | `C0B88CUAZPD` |

Also: **Settings → Actions → General → Workflow permissions → Read and write**
(so the bot can commit results). The workflow (`.github/workflows/backtest.yml`)
then runs Mon–Fri 22:00 UTC (data refresh + backtest) and Fri 22:30 UTC (weekly
review), committing updated `memory/` and `reports/` and posting to Slack.

## 6. First push
```bash
cd <this folder>
git init && git add . && git commit -m "OANDA backtesting bot"
git branch -M main
git remote add origin https://github.com/burugupallyprem-coder/OANDA_Backtesting_bot.git
git push -u origin main
```
Confirm `.env` is NOT in the commit (`git status` should show it ignored).

## 7. Kill switch
Create a file named `STOP` at repo root to halt every routine. Delete it to
resume. (Gitignored, so local STOP won't affect the cloud unless committed.)

## Slack bot token — how to get one
1. api.slack.com/apps → Create New App → From scratch.
2. OAuth & Permissions → Bot Token Scopes → add `chat:write`.
3. Install to workspace → copy the `xoxb-...` token.
4. In Slack, invite the bot to the channel: `/invite @your-bot`.
