from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from datetime import datetime, timedelta
import logging
import speech_recognition as sr
import pyttsx3
import time
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:*", "http://127.0.0.1:*", "file://*", "http://10.75.157.159:*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

API_KEY = 'AIzaSyAkYbqRRED7Ui4DbIPGXZ2trKlpItQvQ1o'
genai.configure(api_key=API_KEY)

try:
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",  # Using the flash model for faster responses
        generation_config={
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 256,  # Reduced from 1024 to encourage shorter responses
        },
        safety_settings=[
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    )
    logger.info("Successfully initialized Gemini model")
except Exception as e:
    logger.error(f"Error initializing Gemini model: {str(e)}")
    raise

try:
    recognizer = sr.Recognizer()
    logger.info("Successfully initialized speech recognition")
except Exception as e:
    logger.error(f"Error initializing speech recognition: {str(e)}")
    raise

def init_tts_engine():
    """Initialize and configure the text-to-speech engine"""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id)  # Use the first available voice
        engine.setProperty('rate', 150)  # Speed of speech
        engine.setProperty('volume', 1.0)  # Volume (0.0 to 1.0)
        return engine
    except Exception as e:
        logger.error(f"Error initializing text-to-speech engine: {str(e)}")
        return None

hospital_data = {
    "hospitals": [
        {"name": "City General", "district": "Downtown", "wait_time": "30-45 minutes", "busyness": "high"},
        {"name": "Northside Medical", "district": "Northside", "wait_time": "15-20 minutes", "busyness": "medium"},
        {"name": "Southwest Clinic", "district": "Southwest", "wait_time": "5-10 minutes", "busyness": "low"},
        {"name": "Eastside Hospital", "district": "Eastside", "wait_time": "20-30 minutes", "busyness": "medium"},
        {"name": "Westside Medical", "district": "Westside", "wait_time": "10-15 minutes", "busyness": "low"}
    ]
}

appointments = {}
urgency_levels = {
    "emergency": {"max_wait": 0, "description": "Immediate attention required"},
    "urgent": {"max_wait": 2, "description": "Attention needed within 2 hours"},
    "routine": {"max_wait": 24, "description": "Can be scheduled within 24 hours"}
}

def book_appointment(hospital_name, urgency, patient_name):
    """Book an appointment at the specified hospital based on urgency"""
    current_time = datetime.now()
    
    hospital = next((h for h in hospital_data["hospitals"] if h["name"].lower() == hospital_name.lower()), None)
    if not hospital:
        return None, "Hospital not found"
    
    if urgency == "emergency":
        appointment_time = current_time
    else:
        wait_time = int(hospital["wait_time"].split("-")[1].split()[0])
        appointment_time = current_time + timedelta(minutes=wait_time)
    
    appointment = {
        "patient_name": patient_name,
        "hospital": hospital_name,
        "urgency": urgency,
        "appointment_time": appointment_time.strftime("%Y-%m-%d %H:%M"),
        "status": "confirmed"
    }
    
    if hospital_name not in appointments:
        appointments[hospital_name] = []
    appointments[hospital_name].append(appointment)
    
    return appointment, "Appointment booked successfully"

chat = model.start_chat(history=[])

@app.route('/test', methods=['GET'])
def test():
    logger.info("Test endpoint called")
    return jsonify({"status": "Server is running"})

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        logger.info("Received chat request")
        data = request.json
        if not data or 'message' not in data:
            logger.error("Invalid request data")
            return jsonify({
                'response': "Invalid request format",
                'status': 'error'
            }), 400

        user_message = data.get('message', '')
        logger.info(f"Processing message: {user_message}")
        
        message_with_context = f"""You are a helpful hospital assistant. Here is the current hospital data:

{json.dumps(hospital_data, indent=2)}

Current time is {datetime.now().strftime('%H:%M')}. 

You can help with:
1. Providing wait times and busyness levels
2. Booking appointments based on urgency (emergency, urgent, or routine)
3. Finding the best hospital based on current conditions

When booking appointments:
- Emergency: Immediate attention
- Urgent: Within 2 hours
- Routine: Within 24 hours

Please provide a brief, concise response (1-2 sentences maximum) to: {user_message}
Focus on providing accurate wait times, busyness levels, and appointment booking information."""
        
        try:
            response = chat.send_message(message_with_context)
            response_text = response.text
            logger.info("Successfully generated response from Gemini")

            if any(word in user_message.lower() for word in ["book", "appointment", "schedule"]):
                for hospital in hospital_data["hospitals"]:
                    if hospital["name"].lower() in response_text.lower():
                        for urgency in urgency_levels.keys():
                            if urgency in response_text.lower():
                                patient_name = f"Patient_{len(appointments) + 1}"
                                appointment, status = book_appointment(hospital["name"], urgency, patient_name)
                                if appointment:
                                    response_text = f"Appointment booked at {hospital['name']} for {urgency} care. Appointment time: {appointment['appointment_time']}"

            try:
                logger.info("Attempting to convert response to speech")
                engine = init_tts_engine()
                if engine:
                    engine.say(response_text)
                    engine.runAndWait()
                    logger.info("Successfully converted response to speech")
                else:
                    logger.error("Failed to initialize text-to-speech engine")
            except Exception as e:
                logger.error(f"Error converting response to speech: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating response from Gemini: {str(e)}")
            if "quota" in str(e).lower():
                return jsonify({
                    'response': "I'm currently experiencing high demand. Please wait a moment and try again.",
                    'status': 'error',
                    'error': str(e)
                }), 500
            return jsonify({
                'response': "I apologize, but I'm having trouble generating a response right now. Please try again in a moment.",
                'status': 'error',
                'error': str(e)
            }), 500
        
        return jsonify({
            'response': response_text,
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        return jsonify({
            'response': "I apologize, but I'm having trouble connecting right now. Please try again in a moment.",
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/listen', methods=['POST'])
def listen():
    try:
        logger.info("Received listen request")
        with sr.Microphone() as source:
            logger.info("Listening...")
            audio = recognizer.listen(source)
            try:
                text = recognizer.recognize_google(audio)
                logger.info(f"Recognized text: {text}")
                return jsonify({
                    'text': text,
                    'status': 'success'
                })
            except sr.UnknownValueError:
                logger.error("Could not understand audio")
                return jsonify({
                    'text': "Sorry, I couldn't understand that.",
                    'status': 'error',
                    'error': 'Could not understand audio'
                }), 400
            except sr.RequestError as e:
                logger.error(f"Error with speech recognition service: {str(e)}")
                return jsonify({
                    'text': "Sorry, there was an error with the speech recognition service.",
                    'status': 'error',
                    'error': str(e)
                }), 500
    except Exception as e:
        logger.error(f"Error in listen endpoint: {str(e)}")
        return jsonify({
            'text': "Sorry, there was an error with the microphone.",
            'status': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    logger.info("Starting Flask server...")
    app.run(debug=True, port=5000, host='0.0.0.0') 