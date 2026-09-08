"""AI reply engine for the SolarEase chat widget.

Uses Google's Gemini API (free tier — no credit card needed, cloud-based,
works from any hosting including cheap shared hosting since nothing runs
locally). The system prompt keeps the assistant strictly scoped to the
visitor's solar / home-energy requirements and SolarEase's own services —
anything else gets politely declined and steered back on topic.

Setup:
    1. Go to https://aistudio.google.com
    2. Click "Get API key" (top of the page) and create a free key.
    3. Add it to your .env file:
        GEMINI_API_KEY=your_key_here
        GEMINI_MODEL=gemini-3.6-flash        (optional, this is the default)

The free tier is rate-limited (a generous number of requests per day) but
costs nothing. If GEMINI_API_KEY is missing or the API call fails for any
reason, a safe fallback message is returned instead of crashing the chat.
"""

import os
import requests

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

SYSTEM_PROMPT = """You are "SolarEase Assistant", the official website chat assistant for
SolarEase, a solar panel sales & installation company in Pakistan (SolarEase - Smart Solar
Management System).

STRICT SCOPE — this is a hard rule, never break it:
Only ever answer questions about:
- The visitor's own home/property solar & energy requirements (monthly electricity units,
  monthly bill amount, roof area, budget, backup hours needed, property type).
- SolarEase's system types (On-Grid, Hybrid, Off-Grid), solar packages, indicative pricing,
  and services: free site survey, custom quotation, installation, annual maintenance plans,
  warranty, complaints/support, and net-metering.
- General solar-energy education that is directly useful for the visitor to decide on a
  home/commercial solar system.

If the visitor asks about ANYTHING outside that scope (general knowledge, unrelated
companies, personal life, coding, politics, entertainment, etc.), do NOT answer it — politely
decline in one short line and steer the conversation back to their solar / home energy
requirements. For example: "Mai sirf aapki solar/home energy requirements mein madad kar
sakta hoon — jaise bijli ka bill, roof space ya system type. Bataiye, aapki requirement kya
hai?"

Tone & style:
- Keep replies short: 2-5 sentences, friendly and practical.
- Reply in whichever language/style the visitor used (English, Urdu, or Roman Urdu).
- Never invent an exact final price — mention prices only as indicative ranges and always
  say a Sales Representative will confirm the final quotation after understanding their
  requirement / site survey.
- If the visitor sounds ready to move forward (wants pricing finalized, wants a quotation,
  wants a site survey, or asks to talk to a person), tell them a Sales Representative has
  been notified and will join the chat shortly.

Reference info about SolarEase (use only when relevant; treat prices as indicative only):
{context}
"""

CONTEXT = """
System types:
- On-Grid: grid-tied, net-metering supported, no battery — best for straightforward bill reduction.
- Hybrid: grid-connected with battery backup — keeps essentials running during loadshedding.
- Off-Grid: fully independent, battery-based — for remote or un-serviced locations.

Sample residential packages (indicative PKR):
- 3 kW On-Grid: ~ PKR 525,000
- 5 kW Hybrid: ~ PKR 1,250,000
- 8 kW Hybrid: ~ PKR 1,650,000

Sample commercial/industrial packages (indicative PKR):
- 10 kW On-Grid: ~ PKR 1,750,000
- 20 kW Hybrid: ~ PKR 3,400,000
- 50 kW Industrial: ~ PKR 7,500,000
- Agricultural tube-well (15 kW, off-grid capable): ~ PKR 2,500,000

Services: free site survey, custom quotation, installation & commissioning,
Basic/Premium annual maintenance plans, up to 10-year equipment warranty, complaint support.
"""

FALLBACK_MESSAGE = (
    "Mujhe abhi jawab dene mein masla ho raha hai. Aap apni requirement (jaise monthly "
    "bill, roof space, ya system type) likh dijiye — hamari sales team jald hi rabta karegi."
)

NOT_CONFIGURED_MESSAGE = (
    "Shukriya aapke message ke liye! Hamara AI assistant abhi setup ho raha hai. "
    "Baraye meherbani apni solar/home energy requirement (bijli ka bill, roof area, ya "
    "system type) likh dein — hamari sales team jald hi aapse rabta karegi."
)


def get_bot_reply(history, user_message):
    """Return the assistant's reply text for `user_message`.

    `history` is a list of dicts: {'sender_type': 'user'|'bot'|'sales', 'message': str},
    ordered oldest -> newest, used only for short-term conversational context.

    Talks to Google's Gemini API (cloud, free tier) — no local server needed.
    """
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return NOT_CONFIGURED_MESSAGE

    model = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')

    contents = []
    for item in history[-10:]:
        if item.get('sender_type') == 'sales':
            # Don't feed sales-rep conversation into the bot's context.
            continue
        role = "model" if item.get('sender_type') == 'bot' else "user"
        contents.append({"role": role, "parts": [{"text": item.get('message', '')}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        response = requests.post(
            f"{GEMINI_API_BASE}/{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT.format(context=CONTEXT)}]},
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 500,
                    # Gemini 3.x models "think" before answering by default, which eats into
                    # maxOutputTokens and can cut the visible reply short. This is a simple
                    # chat widget, so we turn thinking off for fast, complete replies.
                    "thinkingConfig": {"thinkingLevel": "minimal"},
                },
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        reply = data['candidates'][0]['content']['parts'][0]['text'].strip()
        return reply or FALLBACK_MESSAGE
    except Exception as e:
        # Printed to the terminal running `python run.py` so you can see the
        # real cause (bad key, wrong model name, quota, network, etc.).
        print("=" * 60)
        print("[Gemini chatbot error]", type(e).__name__, "-", e)
        try:
            print("[Gemini response body]", response.text)
        except Exception:
            pass
        print("=" * 60)
        return FALLBACK_MESSAGE
