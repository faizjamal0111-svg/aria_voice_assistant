
import os
import json
import requests
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from groq import Groq

app = Flask(__name__)
sessions = {}

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

CLINIC = {
    "name": "Sunshine Medical Clinic",
    "address": "123 Health Street, Miami, FL 33101",
    "phone": "+1 (555) 000-1234",
    "hours": "Monday to Friday 8am to 6pm, Saturday 9am to 1pm",
    "services": "general practice, pediatrics, checkups, vaccinations",
    "doctors": "Dr. Sarah Johnson, Dr. Michael Lee",
    "insurance": "Aetna, Blue Cross, Cigna, United Healthcare, Medicare",
    "parking": "free parking behind building"
}

def build_prompt():
    return f"""
You are Aria, a professional AI receptionist for {CLINIC["name"]}.
Keep responses under 2 sentences. Be warm but efficient.
This is a phone call — no bullet points, no lists.

Clinic Info:
- Address: {CLINIC["address"]}
- Hours: {CLINIC["hours"]}
- Services: {CLINIC["services"]}
- Doctors: {CLINIC["doctors"]}
- Insurance: {CLINIC["insurance"]}

Rules:
- NEVER give medical advice
- If emergency mentioned → say: Please hang up and call 911 now
- Keep responses short and natural
"""

def get_reply(call_sid, patient_text):
    if call_sid not in sessions:
        sessions[call_sid] = []
    
    sessions[call_sid].append({"role": "user", "content": patient_text})
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": build_prompt()},
            *sessions[call_sid]
        ],
        temperature=0.4,
        max_tokens=150
    )
    
    reply = response.choices[0].message.content
    sessions[call_sid].append({"role": "assistant", "content": reply})
    return reply


@app.route("/incoming-call", methods=["POST"])
def incoming_call():
    call_sid = request.form.get("CallSid")
    sessions[call_sid] = []
    
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/handle-speech",
        timeout=5,
        speech_timeout="auto",
        language="en-US"
    )
    gather.say(
        "Hello! Thank you for calling Sunshine Medical Clinic. This is Aria. How can I help you today?",
        voice="alice"
    )
    response.append(gather)
    return Response(str(response), mimetype="text/xml")


@app.route("/handle-speech", methods=["POST"])
def handle_speech():
    call_sid = request.form.get("CallSid")
    patient_speech = request.form.get("SpeechResult", "")
    
    if not patient_speech:
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action="/handle-speech",
            timeout=5,
            speech_timeout="auto"
        )
        gather.say("Sorry, I did not catch that. Could you repeat please?", voice="alice")
        response.append(gather)
        return Response(str(response), mimetype="text/xml")
    
    aria_reply = get_reply(call_sid, patient_speech)
    
    response = VoiceResponse()
    end_phrases = ["goodbye", "bye", "thank you", "that is all", "no thanks"]
    
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
