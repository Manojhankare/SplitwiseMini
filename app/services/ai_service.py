import json

import requests
from flask import current_app

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def parse_expense_with_ai(text):
    prompt = f"""Extract expense info from this message and return ONLY valid JSON, no markdown, no explanation, no code fences.

Format exactly: {{"description": "short description", "amount": number, "payer": "name", "participants": ["name1", "name2"]}}

Rules:
- "participants" = everyone the cost is split between. Include the payer in the list too if they also share the cost (which is the normal case).
- If no payer is mentioned, assume "me" paid.
- Lowercase and trim all names.
- "amount" is a plain number, no currency symbols or words.

Message: "{text}"
"""
    resp = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {current_app.config['GROQ_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": current_app.config["GROQ_MODEL"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
        timeout=30,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()

    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    parsed = json.loads(content)

    parsed["description"] = str(parsed.get("description", "expense")).strip()
    parsed["amount"] = float(parsed["amount"])
    parsed["payer"] = str(parsed.get("payer", "me")).strip().lower()
    participants = [str(p).strip().lower() for p in parsed.get("participants", [])]
    if parsed["payer"] not in participants:
        participants.append(parsed["payer"])
    parsed["participants"] = participants
    return parsed
