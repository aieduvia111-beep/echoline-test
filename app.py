from flask import Flask, request, Response
import requests
import os

app = Flask(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

@app.route("/")
def home():
    return "EchoLine test server running"

@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    text = "Dzień dobry, tu automatyczny asystent EchoLine. To jest pierwszy test systemu. Dziękuję i do usłyszenia."

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2"
    }

    r = requests.post(url, json=payload, headers=headers)

    if r.status_code == 200:
        with open("static/powitanie.mp3", "wb") as f:
            f.write(r.content)
        audio_url = request.url_root + "static/powitanie.mp3"
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{audio_url}</Play>
</Response>"""
    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="pl-PL">Przepraszam, wystąpił błąd.</Say>
</Response>"""

    return Response(twiml, mimetype="text/xml")

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
