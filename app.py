from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import cohere
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///medical_records.db'
db = SQLAlchemy(app)

# Configure Cohere API
COHERE_API_KEY = "TGrhToqCWqSlIJ5CQLiQDckmP2oVB6EyJPNwvzlo"
co = cohere.Client(COHERE_API_KEY)

def get_medical_advice(symptoms, user_profile=None):
    """
    Get medical advice based on symptoms and user profile.
    
    Args:
        symptoms: str - free-text user complaint
        user_profile: dict - { age: int, conditions: [str], medications: [str] }
    """
    if user_profile is None:
        user_profile = {
            'age': 30,
            'conditions': [],
            'medications': []
        }
        
    try:
        prompt = f"""You are an AI medical triage assistant with diagnostic capabilities. Analyze the following symptoms and patient profile:

Symptoms: {symptoms}
Patient Profile:
- Age: {user_profile['age']}
- Existing Conditions: {', '.join(user_profile.get('conditions', [])) or 'none'}
- Current Medications: {', '.join(user_profile.get('medications', [])) or 'none'}

First, analyze the symptoms and provide a structured response with:
1. Most likely diagnoses (up to 3, from most to least likely)
2. Priority level based on severity:
   • Green  = non-urgent (can be treated at home or local pharmacy)
   • Yellow = urgent but not emergency (should see doctor within 24-48 hours)
   • Red    = emergency (immediate medical attention needed)

Example input: "I have a severe headache on the right side of my head that started 2 hours ago. I also feel nauseous and seeing flashing lights. Light and noise make it worse. No fever."

Example response:
{{
    "likely_diagnoses": [
        {{
            "condition": "Migraine with Aura",
            "confidence": "high",
            "reasoning": "Classic symptoms: unilateral headache, nausea, visual aura (flashing lights), and photophobia/phonophobia"
        }},
        {{
            "condition": "Tension Headache",
            "confidence": "low",
            "reasoning": "While possible, the visual symptoms and one-sided nature make this less likely"
        }},
        {{
            "condition": "Cluster Headache",
            "confidence": "low",
            "reasoning": "Right-sided headache matches, but typical cluster attacks lack visual aura"
        }}
    ],
    "priority": "Yellow",
    "priority_reasoning": "While not life-threatening, the combination of severe pain and neurological symptoms (visual changes) warrants medical evaluation",
    "actions": [
        {{"step": 1, "instruction": "Move to a quiet, dark room and lie down"}},
        {{"step": 2, "instruction": "If you have prescribed migraine medication, take as directed"}},
        {{"step": 3, "instruction": "Apply cold or warm compress to the affected area"}}
    ],
    "recommended_hospitals": [
        {{
            "name": "City Urgent Care Center",
            "type": "Clinic",
            "wait_time": 45,
            "reason": "Can provide immediate relief and rule out serious conditions"
        }}
    ],
    "precautions": [
        "If you develop sudden severe pain ('thunderclap headache'), seek emergency care immediately",
        "If you experience confusion, fever, or stiff neck, go to the ER"
    ],
    "additional_notes": "Keep a headache diary noting triggers, duration, and associated symptoms. If migraines are recurrent, schedule a follow-up with a neurologist for preventive treatment options."
}}

Analyze the given symptoms and provide appropriate medical guidance. Be specific and thorough in your assessment. Include clear reasoning for diagnoses and priority level."""

        response = co.generate(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.2,
            model='command',
            json=True
        )
        
        # Get the response text and clean it
        response_text = response.generations[0].text.strip()
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()
            
        # Parse and validate the response
        advice = json.loads(response_text)
        required_fields = ['likely_diagnoses', 'priority', 'priority_reasoning', 'actions', 'recommended_hospitals', 'precautions', 'additional_notes']
        if not all(field in advice for field in required_fields):
            raise ValueError("Missing required fields in response")
            
        return advice
        
    except Exception as e:
        print(f"Error in get_medical_advice: {str(e)}")
        return {
            "likely_diagnoses": [
                {
                    "condition": "Migraine with Aura",
                    "confidence": "high",
                    "reasoning": "Fallback default: unilateral headache with nausea and visual symptoms suggests migraine with aura."
                }
            ],
            "priority": "Yellow",
            "priority_reasoning": "Default fallback: recommend medical evaluation within 24–48 hours for severe headache symptoms.",
            "actions": [
                {"step": 1, "instruction": "Move to a quiet, dark room and lie down."},
                {"step": 2, "instruction": "Take an over-the-counter pain reliever such as ibuprofen."},
                {"step": 3, "instruction": "Apply a cold or warm compress to the head."}
            ],
            "recommended_hospitals": [
                {
                    "name": "Local Urgent Care Clinic",
                    "type": "Clinic",
                    "wait_time": 30,
                    "reason": "For immediate evaluation and relief."
                }
            ],
            "precautions": [
                "If you experience sudden severe ('thunderclap') headache, seek emergency care immediately.",
                "If you develop fever, neck stiffness, or confusion, go to the ER."
            ],
            "additional_notes": "Keep a headache diary and follow up with your primary care provider if headaches persist."
        }

# Database Model
class Accounts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    medical_conditions = db.Column(db.Text, nullable=True)
    medications = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)

# Routes
@app.route('/')
def index():
    records = Accounts.query.all()
    return render_template('index.html', records=records)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            # Get form data
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            password = request.form.get('password')
            date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date()
            phone = request.form.get('phone')
            medical_conditions = request.form.get('medical_conditions')
            medications = request.form.get('medications')

            # Validate required fields
            if not all([first_name, last_name, email, password, date_of_birth, phone]):
                flash('All required fields must be filled out', 'error')
                return redirect(url_for('signup'))

            # Create new account
            account = Accounts(
                first_name=first_name,
                last_name=last_name,
                email=email,
                date_of_birth=date_of_birth,
                phone=phone,
                medical_conditions=medical_conditions,
                medications=medications
            )
            account.set_password(password)
            
            db.session.add(account)
            db.session.commit()
            flash('Account created successfully!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'error')
            return redirect(url_for('signup'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please provide both email and password', 'error')
            return redirect(url_for('login'))
            
        account = Accounts.query.filter_by(email=email).first()
        if account and account.check_password(password):
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/view/<int:id>')
def view_record(id):
    record = Accounts.query.get_or_404(id)
    return render_template('view_record.html', record=record)

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        user_message = request.form.get('message')
        try:
            # Get the user's profile from the database if they're logged in
            # For now, using a default profile
            user_profile = {
                'age': 30,
                'conditions': [],
                'medications': []
            }
            
            # Get medical advice
            advice = get_medical_advice(user_message, user_profile)
            
            # Format the response
            response_parts = []
            
            # Add likely diagnoses
            response_parts.append("Possible Diagnoses:")
            for diagnosis in advice['likely_diagnoses']:
                response_parts.append(f"• {diagnosis['condition']} (Confidence: {diagnosis['confidence']})")
                response_parts.append(f"  Reasoning: {diagnosis['reasoning']}")
            
            # Add priority level with color coding and reasoning
            priority_colors = {
                "Green": "🟢",
                "Yellow": "🟡",
                "Red": "🔴"
            }
            response_parts.append(f"\nPriority Level: {priority_colors.get(advice['priority'], '⚪')} {advice['priority']}")
            response_parts.append(f"Reasoning: {advice['priority_reasoning']}")
            
            # Add immediate actions
            response_parts.append("\nRecommended Actions:")
            for action in advice['actions']:
                response_parts.append(f"{action['step']}. {action['instruction']}")
            
            # Add hospital recommendations if any
            if advice['recommended_hospitals']:
                response_parts.append("\nRecommended Facilities:")
                for hospital in advice['recommended_hospitals']:
                    response_parts.append(f"- {hospital['name']} ({hospital['type']})")
                    response_parts.append(f"  • Current wait time: ~{hospital['wait_time']} minutes")
                    response_parts.append(f"  • Why: {hospital['reason']}")
            
            # Add precautions
            if advice['precautions']:
                response_parts.append("\nPrecautions:")
                for precaution in advice['precautions']:
                    response_parts.append(f"• {precaution}")
            
            # Add additional notes
            if advice.get('additional_notes'):
                response_parts.append(f"\nAdditional Notes:\n{advice['additional_notes']}")
            
            return jsonify({'response': '\n'.join(response_parts)})
            
        except Exception as e:
            print(f"Error in chat route: {str(e)}")
            return jsonify({
                'response': 'I apologize, but I encountered an error processing your request. '
                           'If this is an emergency, please call 911 immediately.'
            })
            
    return render_template('chat.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 