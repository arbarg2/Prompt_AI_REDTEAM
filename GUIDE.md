# THIS NEEDS TO BE MADE GENERIC. Step-by-Step Guide: Set Up, Deploy and Run the AI Red-Team Demo Target

**Audience:** anyone on the team, no coding experience needed.
**Time:** about 15 minutes the first time, 3 minutes for every scan after that.
**Outcome:** a running demo target that a Prompt Security AI Red Teaming scan can attack, with fresh fictional data for every scan.

> This is an intentionally vulnerable demo app with **fake data only**. Never put real data in it, never leave it running unattended, and never share your keys.

## What you need (one time)

| Item | Why | How to get it |
|---|---|---|
| Docker Desktop | Runs the target in one container | docker.com/products/docker-desktop, install, open it, wait until it says "running" |
| ngrok account + app | Gives the hosted scanner a public HTTPS address to your laptop | ngrok.com (free account), then `brew install ngrok` |
| This folder (`ai-redteam-target`) | The app | Already on your machine |

---

## Part 1: One-time setup

### Step 1. Open a terminal in the project folder
```bash
cd "/Users/patrick.meehan/Claude/Projects/Prompt Security Enablement/ai-redteam-target"
```
(Use your own path if the folder is somewhere else.)

### Step 2. Create your two keys
The app needs two different secret keys. Run this command **twice** and keep both outputs:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
- First output = **target key** (the scanner uses this).
- Second output = **admin key** (only you use this, to prepare scans).

### Step 3. Create the settings file
```bash
cp .env.example .env
open -e .env
```
In the editor that opens, fill in the two lines (no spaces, no quotes):
```
TARGET_API_KEY=paste-the-first-key-here
ADMIN_API_KEY=paste-the-second-key-here
```
Optional but recommended for scans: set `RATE_LIMIT_PER_MINUTE=0` so the scan is never throttled. Save and close.

> `.env` starts with a dot, so Finder hides it. In Finder press **Cmd+Shift+.** to show hidden files.
> The app refuses to start if a key is missing, shorter than 24 characters, looks like a placeholder, or both keys are identical.

### Step 4. Connect ngrok to your account
Copy your authtoken from the ngrok dashboard, then:
```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

---

## Part 2: Start the target

### Step 5. Start it
Make sure Docker Desktop is running, then:
```bash
docker compose up --build -d
```
The first run takes a minute or two.

### Step 6. Check it is healthy
```bash
curl http://127.0.0.1:8000/health
```
Expected: `{"status":"ok"}`

### Step 7. Try a real question
Replace `YOUR_TARGET_API_KEY` with your target key:
```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TARGET_API_KEY" \
  -d '{"prompt":"What are your support hours?","profile":"support"}'
```
Expected: JSON containing `"response"` and `"dataset_id"`. If you see `unauthorized`, the key is wrong.

---

## Part 3: Make it reachable by the scanner

A hosted scanner cannot reach `127.0.0.1` on your laptop, so you open a temporary tunnel.

### Step 8. Start the tunnel
Open a **second** terminal window and run:
```bash
ngrok http 8000
```
Leave it open. Copy the address on the **Forwarding** line, for example `https://something-random.ngrok-free.dev`. This is your **public URL**.

### Step 9. Test through the tunnel
```bash
curl -s -X POST 'https://YOUR_PUBLIC_URL/chat' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TARGET_API_KEY' \
  -d '{"prompt":"What are your support hours?"}'
```
You should get the same kind of JSON answer. If you get an HTML page instead, add `-H 'ngrok-skip-browser-warning: true'`.

---

## Part 4: Before every scan (30 seconds)

### Step 10. Prepare the next scan
1. In your browser open **`http://127.0.0.1:8000/admin/ui`** (the local address, not the ngrok one).
2. Paste the **admin key**.
3. Click **Prepare next scan** **once**.
4. Wait for the page to show a new **Run ID** and **Record count**. Write down the **Seed** if you may want to reproduce this dataset later.

The data now stays exactly the same, however many prompts the scan sends, until you click the button again. **Rule: click the button, then start the scan.**

---

## Part 5: Configure and run the scan in Prompt Security

### Step 11. Add the target
In the AI Red Teaming target setup (Connectivity section):

1. **API key field:** paste your **target key** (not the admin key).
2. **cURL field:** paste this, exactly as written except for your URL. Keep `{{prompt}}` and `{{api_key}}` as they are, because the scanner fills them in:
   ```bash
   curl -X POST 'https://YOUR_PUBLIC_URL/chat' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer {{api_key}}' \
     -d '{"prompt":"{{prompt}}","profile":"support"}'
   ```
3. **Response field:** select **`response`**.

Common mistake: pasting a curl with a real key or a fixed question in it. The form will say it must contain `{{prompt}}` and `{{api_key}}`.

### Step 12. Pick a profile (optional)
Change `"profile":"support"` to one of: `support`, `hr`, `finance`, `healthcare`, `developer`, `rag`, `agent`. Use the matching target description and competitor list from the README ("Suggested contextual target settings per profile") when the scanner asks for context.
Tip: use `agent` to include the agent-only scenarios.

### Step 13. Run the scan
Start it from Prompt Security. Do **not** click Prepare next scan while it is running.

---

## Part 6: After the scan

### Step 14. Check the ground truth (optional)
This lists the scenarios and the planted canary values so you can search the scan results for leaks. Replace `YOUR_ADMIN_API_KEY`:
```bash
curl -s "http://127.0.0.1:8000/admin/manifest?reveal_canaries=true" -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

### Step 15. Shut everything down
- In the ngrok window press **Ctrl+C**.
- Then stop the target:
  ```bash
  docker compose down
  ```

To scan again later: `docker compose up -d`, start `ngrok http 8000` (the URL changes on the free plan, so update the scanner's cURL), do Step 10, run the scan.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose` says it cannot connect to the daemon | Open Docker Desktop and wait until it is running |
| Container exits at start | Run `docker compose logs`. Almost always a missing, short or identical key in `.env` |
| `401 unauthorized` | Wrong key. `/chat` needs the target key; the admin page needs the admin key |
| `429 rate_limited` | Set `RATE_LIMIT_PER_MINUTE=0` in `.env`, run `docker compose up -d`, then redo Step 10 (a restart creates new data) |
| `422 invalid_request` | Bad JSON, empty prompt, or an unknown profile name |
| Scanner gets HTML, not JSON | Add the `ngrok-skip-browser-warning: true` header to the cURL |
| ngrok URL changed | Free URLs change on every restart. Update the cURL in the scanner |
| Cannot find `.env` | Press Cmd+Shift+. in Finder to show hidden files |
| Port 8000 already in use | Stop whatever is using it, or change `8000:8000` in `docker-compose.yml` and run ngrok on the new port |
| Page or scan shows old data | Click Prepare next scan again (and then start the scan) |

## Rules of thumb

1. One click of **Prepare next scan** per scan. Data never changes by itself.
2. Run exactly one copy of the app. It keeps data in memory and is not built for several copies.
3. Keep both keys private. If one leaks, change it in `.env` and run `docker compose up -d`.
4. Never leave the tunnel running when you are not scanning.
5. This target does not reproduce every AI risk. See [COVERAGE.md](COVERAGE.md) for what is real, simulated or unsupported.

## Run without Docker (alternative)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
set -a; source .env; set +a
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```
Then continue from Step 6.
