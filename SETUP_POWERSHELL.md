# Cloud setup from PowerShell — make the bot run by itself

Goal: the bot lives in your **GitHub repo** and runs on **GitHub's servers**
(GitHub Actions). It fetches OANDA data, backtests your strategy, commits the
results back to the repo, and posts a summary to **Slack** — on a schedule and
on demand. **Your laptop is only a one-time launchpad.** After the push you can
delete the local folder; the bot keeps running in the cloud.

You will NOT run Python locally. The only local tools you need are `git` and
(recommended) the GitHub CLI `gh`.

> Run everything below in **Windows PowerShell**. Copy one block at a time.
> Lines starting with `#` are comments — safe to paste, they do nothing.

---

## Part 0 — What stays where

| Thing | Lives where | Touches your laptop? |
|---|---|---|
| The bot code | GitHub repo (cloud) | Only once, to push |
| Backtest execution | GitHub Actions (cloud) | Never |
| OANDA data fetch | GitHub Actions (cloud) | Never |
| Results (reports, lessons) | committed into the repo | View on github.com |
| Notifications | Slack channel `C0B88CUAZPD` | No |
| Secrets (keys/tokens) | GitHub Secrets (encrypted) | No |

---

## Part 1 — Install the two tools (once)

```powershell
winget install --id Git.Git -e --source winget
winget install --id GitHub.cli -e --source winget
```

Close PowerShell, open a **new** PowerShell window, then verify:

```powershell
git --version
gh --version
```

Both should print a version number. If `winget` is missing, install "Git for
Windows" and "GitHub CLI" from their websites, then reopen PowerShell.

---

## Part 2 — Log in to GitHub from PowerShell

```powershell
gh auth login
```

Answer the prompts: **GitHub.com** → **HTTPS** → **Yes** (authenticate Git) →
**Login with a web browser**. Copy the one-time code, press Enter, approve in
the browser. This also configures Git so `git push` works with no password.

Verify:

```powershell
gh auth status
```

---

## Part 3 — Get your credentials ready

You need three values. Have them in a notepad before the next part.

**3a. OANDA token (rotate it — it was shared in chat):**
1. Log in to the OANDA **practice** account at oanda.com.
2. Go to **Manage API Access** → **Revoke** the old token → **Generate** a new one.
3. Copy the new token. (Account ID is NOT required for backtesting — skip it.)

**3b. Slack bot token:**
1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**.
2. Name it (e.g. `oanda-backtest-bot`), pick your workspace → **Create App**.
3. Left menu → **OAuth & Permissions** → scroll to **Scopes** → **Bot Token
   Scopes** → **Add an OAuth Scope** → add `chat:write`.
4. Scroll up → **Install to Workspace** → **Allow**.
5. Copy the **Bot User OAuth Token** (starts with `xoxb-`).
6. In Slack, open your `#trading-bot` channel and type: `/invite @oanda-backtest-bot`.

**3c. Slack channel ID:** already known — `C0B88CUAZPD`.

---

## Part 4 — Push the bot to the cloud (one time)

```powershell
cd "C:\Users\Prem\Desktop\prem\OANDA"

# SAFETY: confirm your secret file is ignored (should print: .env)
git init
git check-ignore .env
```

If the line above printed `.env`, you are safe to continue. If it printed
nothing, STOP and tell me — do not commit until `.env` is ignored.

```powershell
git add .
git commit -m "OANDA backtesting bot"
git branch -M main
git remote add origin https://github.com/burugupallyprem-coder/OANDA_Backtesting_bot.git
git push -u origin main
```

If the push is **rejected** because the GitHub repo already has a README:

```powershell
git pull origin main --allow-unrelated-histories --no-edit
git push -u origin main
```

Confirm `.env` did NOT get uploaded (this should print nothing):

```powershell
git ls-files | Select-String "^\.env$"
```

---

## Part 5 — Add the secrets (from PowerShell, encrypted)

Run these **inside** the repo folder. Each command prompts you to paste the
value and hides it from your command history. Press Enter, paste, Enter.

```powershell
gh secret set OANDA_API_KEY
gh secret set SLACK_BOT_TOKEN
gh secret set SLACK_CHANNEL_ID
```

For `SLACK_CHANNEL_ID` paste exactly: `C0B88CUAZPD`

Verify they exist (values are never shown):

```powershell
gh secret list
```

You should see `OANDA_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`.

---

## Part 6 — Let the bot commit its own results

The workflow needs write permission to save results back to the repo:

```powershell
gh api -X PUT "repos/burugupallyprem-coder/OANDA_Backtesting_bot/actions/permissions/workflow" -f default_workflow_permissions=write -F can_approve_pull_request_reviews=false
```

(If that errors, do it in the browser instead: repo **Settings → Actions →
General → Workflow permissions → Read and write → Save**.)

---

## Part 7 — Run a backtest on demand (no laptop work)

```powershell
gh workflow run backtest.yml
```

Watch it run live:

```powershell
gh run watch
```

Or list recent runs and open the log:

```powershell
gh run list --workflow backtest.yml
gh run view --log
```

When it finishes (~1–2 min): check the **Slack channel** for a `[BACKTEST]`
summary, and the results are committed into the repo.

---

## Part 8 — See your results (without the bot on your laptop)

Open the repo on github.com and look at:

- `reports/summary_latest.json` — headline metrics (trades, win rate, profit
  factor, expectancy, drawdown, by-setup breakdown).
- `reports/walkforward.json` — out-of-sample walk-forward (the number that
  actually matters).
- `memory/results.json` — latest snapshot with config + metrics.
- `memory/lessons.md` — Friday weekly reviews accumulate here.
- `VERDICT.md` — fill in which branch the real numbers land in.

Or pull just the results to read locally any time, then delete again:

```powershell
gh api repos/burugupallyprem-coder/OANDA_Backtesting_bot/contents/reports/summary_latest.json --jq ".content" | % { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
```

---

## Part 9 — It now runs by itself

The schedule in `.github/workflows/backtest.yml`:
- **Mon–Fri 22:00 UTC** — refresh OANDA data + backtest + commit + Slack.
- **Fri 22:30 UTC** — weekly review appended to `memory/lessons.md` + Slack.

You never open your laptop for this. To run it any time, use Part 7. To pause
it, in the repo edit `.github/workflows/backtest.yml` and comment out the
`schedule:` lines (or disable the workflow in the Actions tab).

---

## You can delete the local folder now (optional)

After a successful push + a successful Actions run, the cloud repo is the source
of truth. You can delete `C:\Users\Prem\Desktop\prem\OANDA`. To work on it again
later, re-clone:

```powershell
gh repo clone burugupallyprem-coder/OANDA_Backtesting_bot
```

(Re-create `.env` from `.env.example` only if you ever want to run it locally —
the cloud uses GitHub Secrets, not `.env`.)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `git push` asks for a password | Run `gh auth login` again (HTTPS + authenticate Git). |
| Push rejected, "fetch first" | `git pull origin main --allow-unrelated-histories --no-edit` then push. |
| Actions run fails at "Fetch candles" | OANDA token wrong/expired → `gh secret set OANDA_API_KEY` with a fresh token. |
| No Slack message | Bot not invited to channel, or token missing `chat:write` → re-check Part 3b, re-set `SLACK_BOT_TOKEN`. |
| Workflow can't commit | Re-run Part 6 (write permission). |
| `.env` showed up in `git ls-files` | `git rm --cached .env; git commit -m "drop env"; git push` and rotate every key immediately. |
```
