import os
import json
import requests
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from groq import Groq

app = Flask(__name__)
sessions = {}

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

CLINICS = {
    "dental": {
        "name": "DFW Crown Dental",
        "address": "Dallas, TX",
        "phone": "their number",
        "hours": "Mon-Fri 12pm-6:30pm, Sat 9am-3pm",
        "services": "crowns, cleanings, fillings, whitening, root canals",
        "doctors": "our dental team",
        "insurance": "contact us for insurance info",
        "type": "dental"
    },
    "medical": {
        "name": "Sunshine Medical Clinic",
        "address": "123 Health Street, Miami FL",
        "phone": "+1 (555) 000-1234",
        "hours": "Mon-Fri 8am-6pm, Sat 9am-1pm",
        "services": "general practice, pediatrics, checkups, vaccinations",
        "doctors": "Dr. Sarah Johnson, Dr. Michael Lee",
        "insurance": "Aetna, Blue Cross, Cigna, Medicare",
        "type": "medical"
    },
    "chiropractic": {
        "name": "Spine and Wellness Clinic",
        "address": "Houston TX",
        "phone": "their number",
        "hours": "Mon-Fri 9am-5pm",
        "services": "spinal adjustments, pain relief, posture correction",
        "doctors": "Dr. Williams",
        "insurance": "most major insurance accepted",
        "type": "chiropractic"
    }
}

NUMBER_TO_CLINIC = {
    "+12764959683": "dental",
    "+1xxxxxxxxxx": "medical",
    "+1xxxxxxxxxx": "chiropractic"
}

def build_prompt(clinic):

    base_rules = f"""
You are Aria, a professional AI receptionist
for {clinic['name']}.
Keep responses under 2 sentences.
This is a phone call — no bullet points.
NEVER give medical or dental advice.
"""

    if clinic['type'] == 'dental':
        extra_rules = """
This is a dental clinic.
Common services: cleanings, fillings, crowns,
whitening, extractions, root canals.
New patient visits are 60-90 minutes.
Regular checkups every 6 months.
For severe tooth pain say:
Please visit us immediately or go to
emergency dental care.
"""
    elif clinic['type'] == 'medical':
        extra_rules = """
This is a medical clinic.
For emergencies say:
Please hang up and call 911 now.
Never diagnose conditions.
Annual checkups recommended yearly.
"""
    elif clinic['type'] == 'chiropractic':
        extra_rules = """
This is a chiropractic clinic.
Common services: spinal adjustments,
pain relief, posture correction.
First visit includes consultation
and assessment.
Never diagnose conditions.
"""
    else:
        extra_rules = """
For emergencies say:
Please hang up and call 911 now.
"""

    return f"""
{base_rules}
{extra_rules}
Clinic Info:
- Address: {clinic['address']}
- Hours: {clinic['hours']}
- Services: {clinic['services']}
- Team: {clinic['doctors']}
- Insurance: {clinic['insurance']}
"""


@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    call_sid = request.form.get("CallSid")
    called_number = request.form.get("To")

    clinic_key = NUMBER_TO_CLINIC.get(called_number, "medical")
    clinic = CLINICS[clinic_key]

    sessions[call_sid] = {"clinic": clinic, "history": []}

    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/handle-speech",
        timeout=5,
        speech_timeout="auto",
        language="en-US"
    )
    gather.say(
        f"Hello! Thank you for calling {clinic['name']}. This is Aria. How can I help you today?",
        voice="alice"
    )
    response.append(gather)
    return Response(str(response), mimetype="text/xml")


@app.route("/handle-speech", methods=["POST"])
def handle_speech():
    call_sid = request.form.get("CallSid")
    patient_speech = request.form.get("SpeechResult", "")

    session = sessions.get(call_sid, {})
    clinic = session.get("clinic", CLINICS["medical"])
    history = session.get("history", [])

    if not patient_speech:
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action="/handle-speech",
            timeout=5,
            speech_timeout="auto"
        )
        gather.say(
            "Sorry I didn't catch that. Could you repeat please?",
            voice="alice"
        )
        response.append(gather)
        return Response(str(response), mimetype="text/xml")

    history.append({"role": "user", "content": patient_speech})

    ai_response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": build_prompt(clinic)},
            *history
        ],
        temperature=0.4,
        max_tokens=150
    )

    aria_reply = ai_response.choices[0].message.content
    history.append({"role": "assistant", "content": aria_reply})
    sessions[call_sid]["history"] = history

    response = VoiceResponse()
    end_phrases = ["goodbye", "bye", "thank you", "that's all"]

    if any(phrase in patient_speech.lower() for phrase in end_phrases):
        response.say(aria_reply, voice="alice")
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    gather = Gather(
        input="speech",
        action="/handle-speech",
        timeout=5,
        speech_timeout="auto"
    )
    gather.say(aria_reply, voice="alice")
    response.append(gather)
    return Response(str(response), mimetype="text/xml")


@app.route("/health", methods=["GET"])
def health():
    return "Aria is running!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



