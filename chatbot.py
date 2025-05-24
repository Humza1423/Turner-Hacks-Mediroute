import google.generativeai as genai
import os
from datetime import datetime
import pyttsx3
import requests
import json
import sys
import time


# Configure the APIs
GEMINI_API_KEY = 'AIzaSyAkYbqRRED7Ui4DbIPGXZ2trKlpItQvQ1o'
CARTESIA_API_KEY = 'sk_car_AQem1XavJzgnqFYLN7RHqz'
genai.configure(api_key=GEMINI_API_KEY)


# Initialize text-to-speech engine
try:
    engine = pyttsx3.init()
except Exception as e:
    print("Error initializing text-to-speech engine:", str(e))
    sys.exit(1)


# Configure the model
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 1024,
}


# Initialize the model with the correct name and version
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",  # Using the flash model for faster responses
    generation_config=generation_config,
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


class HospitalChatbot:
    def __init__(self):
        self.hospital_data = {
            "hospitals": [
                {"name": "City General", "district": "Downtown", "wait_time": "30-45 minutes", "busyness": "high"},
                {"name": "Northside Medical", "district": "Northside", "wait_time": "15-20 minutes", "busyness": "medium"},
                {"name": "Southwest Clinic", "district": "Southwest", "wait_time": "5-10 minutes", "busyness": "low"},
                {"name": "Eastside Hospital", "district": "Eastside", "wait_time": "20-30 minutes", "busyness": "medium"},
                {"name": "Westside Medical", "district": "Westside", "wait_time": "10-15 minutes", "busyness": "low"}
            ]
        }
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests
        # Initialize chat session
        self.chat = model.start_chat(history=[])
        # Add system context
        self.initialize_chat_context()


    def wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        self.last_request_time = time.time()


    def initialize_chat_context(self):
        """Initialize the chat with system context"""
        context = f"""You are a helpful hospital assistant AI. You have access to the following hospital data:


{self.hospital_data}


Please provide helpful, natural responses based on the hospital data.
Focus on being informative and friendly. If asked about something not in the data,
politely explain what information you do have access to. Keep responses concise and clear for voice interaction."""
       
        try:
            self.wait_for_rate_limit()
            self.chat.send_message(context)
        except Exception as e:
            print(f"Error initializing chat context: {str(e)}")
            print("Continuing without context...")


    def speak(self, text):
        """Convert text to speech"""
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Error in text-to-speech: {str(e)}")
            print("Continuing with text-only mode...")


    def listen(self):
        """Listen for user input using Cartesia API"""
        try:
            print("Listening... (Press Enter when done speaking)")
            input("Press Enter to stop recording...")
           
            # Here you would implement the actual audio recording and sending to Cartesia
            # For now, we'll use a placeholder that simulates the API call
            headers = {
                "Authorization": f"Bearer {CARTESIA_API_KEY}",
                "Content-Type": "application/json"
            }
           
            # Simulate API response (replace this with actual API call)
            # response = requests.post("https://api.cartesia.ai/v1/speech-to-text",
            #                        headers=headers,
            #                        json={"audio": "base64_encoded_audio_data"})
           
            # For testing, we'll use text input instead
            user_input = input("Enter your message: ")
            print(f"You: {user_input}")
            return user_input


        except Exception as e:
            print(f"Error in speech recognition: {str(e)}")
            return None


    def get_current_time(self):
        return datetime.now().strftime("%H:%M")


    def get_response(self, user_message):
        try:
            # Add current time context to the message
            message_with_context = f"Current time is {self.get_current_time()}. {user_message}"
           
            # Wait for rate limit before making request
            self.wait_for_rate_limit()
           
            # Send message to chat and get response
            response = self.chat.send_message(message_with_context)
           
            return response.text


        except Exception as e:
            print(f"Debug - Error details: {str(e)}")
            if "quota" in str(e).lower():
                return "I'm currently experiencing high demand. Please wait a moment and try again."
            return "I apologize, but I encountered an error. Please try again in a moment."


    def start_chat(self):
        welcome_message = "Welcome to the Hospital Assistant. I can help you with information about hospitals, wait times, and locations. How can I assist you today?"
        print(f"\nBot: {welcome_message}")
        self.speak(welcome_message)


        while True:
            user_input = self.listen()
           
            if user_input is None:
                continue
               
            if user_input.lower() in ['quit', 'exit', 'goodbye', 'bye']:
                farewell = "Thank you for using the Hospital Assistant. Goodbye!"
                print(f"\nBot: {farewell}")
                self.speak(farewell)
                break


            print("\nBot: ", end="")
            response = self.get_response(user_input)
            print(response)
            self.speak(response)


if __name__ == "__main__":
    try:
        chatbot = HospitalChatbot()
        chatbot.start_chat()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")
        print("Please make sure all required packages are installed and try again.")

