from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import httpx
import os
from datetime import datetime

app = FastAPI()

# ─── CONFIG (set these as environment variables in Railway) ───────────────────
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")       # Meta access token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")     # e.g. 1097285630136638
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "fasih123")
HASSAN_PHONE = os.getenv("HASSAN_PHONE")           # Hassan's number: 212XXXXXXXXX
# ─────────────────────────────────────────────────────────────────────────────

WHATSAPP_API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

# In-memory conversation state: { phone: { step: int, data: dict } }
conversations = {}


# ─── BOT MESSAGES ─────────────────────────────────────────────────────────────

WELCOME = """مرحباً! 👋 أنا المساعد الآلي لـ Déco Prestige.

Chno bghiti? 🏠

1️⃣ Peinture
2️⃣ Décoration intérieure
3️⃣ Construction / Rénovation
4️⃣ Autre"""

LOCATION = "Mzian! ✅\n\nF ach madinat nta? 🏙️\n(Écrivez le nom de votre ville)"

BUDGET = """Chno ghat7taj f had lmachar? 💰

1️⃣ Moins de 10,000 DH
2️⃣ 10,000 - 50,000 DH
3️⃣ 50,000 - 100,000 DH
4️⃣ Plus de 100,000 DH"""

TIMING = """Imta bghiti tbda? ⏰

1️⃣ Cette semaine
2️⃣ Ce mois-ci
3️⃣ Dans 2-3 mois
4️⃣ Pas encore décidé"""

NAME = "Chno smitk? / Votre prénom? 😊"

def closing(name):
    return f"شكراً {name}! 🙏\n\nMqabl mn l'équipe Déco Prestige ghadi yt9l b9ik f aqrab waqt.\n\nBslama! 👋"

SERVICES = {"1": "Peinture", "2": "Décoration intérieure", "3": "Construction / Rénovation", "4": "Autre"}
BUDGETS  = {"1": "- 10,000 DH", "2": "10,000–50,000 DH", "3": "50,000–100,000 DH", "4": "+ 100,000 DH"}
TIMINGS  = {"1": "Cette semaine", "2": "Ce mois-ci", "3": "Dans 2-3 mois", "4": "Pas encore décidé"}


# ─── WHATSAPP API ──────────────────────────────────────────────────────────────

async def send_message(to: str, body: str):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(WHATSAPP_API_URL, json=payload, headers=headers)
        print(f"[SEND] to={to} status={r.status_code} body={r.text}")


async def notify_hassan(lead: dict, phone: str):
    msg = f"""🔔 NOUVEAU LEAD — Déco Prestige

👤 Nom : {lead.get('name', '—')}
📱 Téléphone : {phone}
🔧 Service : {lead.get('service', '—')}
📍 Ville : {lead.get('location', '—')}
💰 Budget : {lead.get('budget', '—')}
⏰ Timing : {lead.get('timing', '—')}
🕐 Heure : {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
    await send_message(HASSAN_PHONE, msg)


# ─── WEBHOOK ──────────────────────────────────────────────────────────────────

@app.get("/webhook")
async def verify(request: Request):
    """Meta calls this once to verify the webhook URL."""
    params = dict(request.query_params)
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/webhook")
async def receive(request: Request):
    """Every incoming WhatsApp message arrives here."""
    data = await request.json()
    print(f"[RECV] {data}")

    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return {"status": "ok"}

        msg = value["messages"][0]
        if msg["type"] != "text":
            return {"status": "ok"}

        phone = msg["from"]
        text  = msg["text"]["body"].strip()

        # Get or init conversation
        if phone not in conversations:
            conversations[phone] = {"step": 0, "data": {}}

        conv = conversations[phone]
        step = conv["step"]

        if step == 0:
            await send_message(phone, WELCOME)
            conv["step"] = 1

        elif step == 1:
            conv["data"]["service"] = SERVICES.get(text, text)
            await send_message(phone, LOCATION)
            conv["step"] = 2

        elif step == 2:
            conv["data"]["location"] = text
            await send_message(phone, BUDGET)
            conv["step"] = 3

        elif step == 3:
            conv["data"]["budget"] = BUDGETS.get(text, text)
            await send_message(phone, TIMING)
            conv["step"] = 4

        elif step == 4:
            conv["data"]["timing"] = TIMINGS.get(text, text)
            await send_message(phone, NAME)
            conv["step"] = 5

        elif step == 5:
            conv["data"]["name"] = text
            await send_message(phone, closing(text))
            await notify_hassan(conv["data"], phone)
            conv["step"] = 6  # done

    except Exception as e:
        print(f"[ERROR] {e}")

    return {"status": "ok"}


@app.get("/")
async def root():
    return {"status": "Déco Prestige Bot is running 🚀"}
