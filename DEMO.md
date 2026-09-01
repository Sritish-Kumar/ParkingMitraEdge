# ParkingMitra Edge — Demo Runbook

A 3-part demo: an **MQTT broker**, the **edge node** (`phase2.py`) that detects
parking events, and a **browser dashboard** that shows them live. Optionally a
CLI subscriber that prints the raw event stream (stands in for the cloud).

```
phase2.py  ──publish──▶  MQTT broker  ──▶  dashboard_standalone.html (browser)
 (edge node)             (mosquitto)   └──▶  tools/subscribe.py (optional)
```

---

## Prerequisites (each machine)

| Need | Why | Check |
|------|-----|-------|
| Git | clone the repo | `git --version` |
| Python 3.11+ (3.12 recommended) | runs the edge node | `python3 --version` |
| Docker | runs the MQTT broker in one command | `docker --version` |
| A modern browser | the dashboard | — |

> No Docker? See **Broker without Docker** at the bottom.

---

## One-time setup

```bash
git clone git@github.com:Sritish-Kumar/ParkingMitraEdge.git
cd ParkingMitraEdge

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

*Fast path (skips the ~200 MB PyTorch download — the demo uses a fake detector
and never loads the model):*

```bash
pip install paho-mqtt PyYAML opencv-python numpy
```

---

## Run the demo — in this order

### 1. Terminal 1 — start the MQTT broker (leave it running)

```bash
docker run -it --rm --name mosquitto \
  -p 1883:1883 -p 9001:9001 \
  -v "$PWD/mosquitto-demo.conf:/mosquitto/config/mosquitto.conf" \
  eclipse-mosquitto
```

Wait for these lines:

```
Opening ipv4 listen socket on port 1883.
Opening ipv4 listen socket on port 9001.
```

- `1883` = plain MQTT, used by `phase2.py`
- `9001` = MQTT-over-WebSocket, used by the browser

*(Windows CMD: replace `$PWD` with the full path. PowerShell: use `${PWD}`.)*

### 2. Browser — open the dashboard

Double-click **`dashboard_standalone.html`** (or drag it into a browser tab).

- It is a single self-contained file — no web server, no internet needed.
- The dot at the top-right should turn green: **live**.
- It will show `Parked 0 / Violation 0 / Free 17` until the edge node starts.

> Use `dashboard_standalone.html`, **not** `dashboard.html`. The plain one needs
> a web server and will show a black screen if opened directly.

### 3. Terminal 2 — start the edge node

```bash
source .venv/bin/activate
python phase2.py
```

Within a few seconds it prints event lines:

```
[01:15:37] EVENT CAM_01 A03 OK->BAD overstay 42m  ***  id=1a2b3c4d
```

The dashboard now fills in live — **green = parked, red = violation** — and the
**Recent changes** panel scrolls. Give it ~30 s to build up a good picture.

### 4. (Optional) Terminal 3 — the "cloud" subscriber

```bash
source .venv/bin/activate
python tools/subscribe.py
```

Prints every event as it arrives and a summary on exit. Good for showing the
raw JSON contract. `--raw` dumps the exact payloads.

---

## Stopping

- Terminal 2 (`phase2.py`): **Ctrl+C** — prints an outbox summary.
- Terminal 3 (`subscribe.py`): **Ctrl+C**.
- Terminal 1 (broker): **Ctrl+C** — `--rm` removes the container automatically.

---

## Demo talking points

**Offline resilience (the headline feature).** With `phase2.py` running, press
**Ctrl+C in the broker terminal**. Events keep coming but now pile up in
`outbox.db` on disk (watch the `outbox unsent=` counter climb). Restart the
broker (step 1 again) — the backlog flushes in order, no duplicates, and the
dashboard catches up on its own.

**Zero-install dashboard.** One HTML file. No build step, no server, works on a
locked-down laptop with no internet.

**Add a camera = config only.** A block in `config/cameras.yaml` + a slot file
in `config/slots/`. No code change.

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| Dashboard dot stays grey / red "broker unreachable" | Broker (Terminal 1) isn't running yet, or port 9001 is blocked. Start it first. |
| Dashboard is a black screen | You opened `dashboard.html`. Use `dashboard_standalone.html`. |
| `phase2.py`: `ModuleNotFoundError: No module named 'paho'` | venv not activated, or deps not installed. `source .venv/bin/activate` then `pip install -r requirements.txt`. |
| Broker and browser on **different** machines | Edit one line in `dashboard_standalone.html`: `const BROKER = "ws://<broker-ip>:9001";` |
| `phase2.py` connects to a remote broker | `MQTT_HOST=<ip> MQTT_PORT=1883 python phase2.py` |
| Docker port already in use | Something else is on 1883/9001. Stop it, or change the left side of `-p` and update `BROKER`. |

### Broker without Docker

```bash
# macOS:  brew install mosquitto
# Debian/Ubuntu:  sudo apt install mosquitto
mosquitto -c mosquitto-demo.conf
```
