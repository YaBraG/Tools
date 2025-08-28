# TCP Auto Clock (GitHub Actions)

Hands-off clock in/out for TimeClock Plus (WebClock) using GitHub Actions + Playwright.

## What you get
- Runs every 5 minutes in the cloud (UTC); the script decides if it's time to **Clock In/Out** based on your local timezone.
- **Master toggle** via repo variable `TCP_ON` (1 = ON, 0 = OFF).
- **Skip days** via `skip_dates.txt` and **fixed holidays** via `holidays.txt`.
- **Discord notifications** on each run.
- Button workflow to toggle ON/OFF from your phone.

## Setup (once)

1. Create a new **private** GitHub repository and upload all files from this ZIP.
2. In the repo, go to **Settings → Secrets and variables → Actions**:
   - **Secrets** (Add new repository secret):
     - `TCP_URL` = `https://133654.tcplusondemand.com/app/webclock/#/EmployeeLogOn/133654`
     - `TCP_USERNAME` = your External ID (e.g., `elicona`)
     - `TCP_PASSWORD` = your password
     - `DISCORD_WEBHOOK` = your Discord Incoming Webhook URL (create in a channel → Integrations → Webhooks)
   - **Variables** (Repository variables):
     - `TCP_ON` = `1`   (set to `0` to pause all scheduling)
3. Open the **Actions** tab and enable workflows if prompted.
4. The workflow will run every 5 minutes automatically. You can also **Run workflow** manually.

## Daily use
- **Toggle ON/OFF**: Actions → `Toggle TCP_ON` → choose `on` or `off` → Run.
- **Skip Today**: Actions → `TCP Auto Clock` → Run workflow → `skip_today: yes`.
- **Edit holidays**: add `YYYY-MM-DD` dates to `holidays.txt` (one per line).

## Notes
- GitHub schedules use **UTC**. The script converts to your timezone from `schedule.yaml`.
- If the TCP site enables CAPTCHA/MFA, automation cannot proceed.
- GitHub pauses scheduled jobs after ~60 days of inactivity. Manually run a workflow or push a small change to keep it active.
