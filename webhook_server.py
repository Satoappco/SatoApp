# webhook.py
import os
import json
from flask import Flask, request, jsonify
from database import db_manager, init_database

API_KEY = os.environ.get("API_KEY", "SatoLogos")  # set a strong key in prod

app = Flask(__name__)

# Initialize database at startup
try:
    init_database()
    print("Database initialized successfully")
except Exception as e:
    print(f"Failed to initialize database: {e}")
    # You might want to exit here in production
    # import sys; sys.exit(1)

@app.route("/webhook", methods=["POST"])
def webhook():
    # AUTH: check Bearer token
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {API_KEY}"
    if API_KEY and auth != expected:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Invalid or missing JSON body"}), 400

    # Playbooks (OpenAPI) will typically POST {user_name, user_choice}
    user_name = data.get("user_name")
    user_choice = data.get("user_choice")

    # But Dialogflow CX webhook format may have sessionInfo.parameters
    if not user_name or not user_choice:
        session = data.get("sessionInfo", {})
        params = session.get("parameters", {}) if isinstance(session, dict) else {}
        user_name = user_name or params.get("user_name")
        user_choice = user_choice or params.get("user_choice")

  # ADD THIS: Print the raw incoming data
    print("=" * 50)
    print("INCOMING WEBHOOK DATA:")
    print(json.dumps(data, indent=2))
    print("=" * 50)


    # Store whatever we have (allow empty values but still store raw)
    try:
        entry = db_manager.save_webhook_entry(user_name, user_choice, json.dumps(data))
        return jsonify({
            "message": f"Saved: user_name={user_name}, user_choice={user_choice}",
            "entry_id": entry.id,
            "timestamp": entry.created_at.isoformat()
        }), 200
    except Exception as e:
        print(f"Error saving webhook entry: {e}")
        return jsonify({"message": "Failed to save entry", "error": str(e)}), 500


@app.route("/webhook/trigger-crew", methods=["POST"])
def trigger_crew_from_webhook():
    """Trigger the Sato crew based on webhook data and return AI response"""
    # AUTH: check Bearer token
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {API_KEY}"
    if API_KEY and auth != expected:
        return jsonify({"message": "Unauthorized"}), 401
    
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Invalid or missing JSON body"}), 400
    
    # Extract user input for the crew
    user_name = data.get("user_name")
    user_choice = data.get("user_choice")
    topic = data.get("topic", user_choice or "general inquiry")
    
    # Handle Dialogflow format
    if not user_name or not user_choice:
        session = data.get("sessionInfo", {})
        params = session.get("parameters", {}) if isinstance(session, dict) else {}
        user_name = user_name or params.get("user_name")
        user_choice = user_choice or params.get("user_choice")
        topic = topic or params.get("topic", user_choice or "general inquiry")
    
    try:
        # Save the webhook entry first
        entry = db_manager.save_webhook_entry(user_name, user_choice, json.dumps(data))
        
        # Import and run the Sato crew
        from src.sato.crew import Sato
        from datetime import datetime
        
        inputs = {
            'topic': topic,
            'current_year': str(datetime.now().year)
        }
        
        # Run the crew
        sato_crew = Sato()
        crew_result = sato_crew.crew().kickoff(inputs=inputs)
        
        return jsonify({
            "message": f"Crew executed for user: {user_name}",
            "entry_id": entry.id,
            "topic": topic,
            "crew_result": str(crew_result),
            "timestamp": entry.created_at.isoformat()
        }), 200
        
    except Exception as e:
        print(f"Error running crew from webhook: {e}")
        # Still save the webhook entry even if crew fails
        try:
            entry = db_manager.save_webhook_entry(user_name, user_choice, json.dumps(data))
            return jsonify({
                "message": "Webhook saved but crew execution failed", 
                "entry_id": entry.id,
                "error": str(e)
            }), 500
        except:
            return jsonify({"message": "Both webhook save and crew execution failed", "error": str(e)}), 500


@app.route("/webhook/recent", methods=["GET"])
def get_recent_entries():
    """Get recent webhook entries for debugging/monitoring"""
    # AUTH: check Bearer token (same as webhook)
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {API_KEY}"
    if API_KEY and auth != expected:
        return jsonify({"message": "Unauthorized"}), 401
    
    try:
        limit = request.args.get("limit", 10, type=int)
        entries = db_manager.get_recent_entries(limit=limit)
        
        result = []
        for entry in entries:
            result.append({
                "id": entry.id,
                "user_name": entry.user_name,
                "user_choice": entry.user_choice,
                "created_at": entry.created_at.isoformat(),
                "raw_payload": json.loads(entry.raw_payload) if entry.raw_payload else None
            })
        
        return jsonify({
            "entries": result,
            "total": len(result)
        }), 200
    except Exception as e:
        print(f"Error fetching recent entries: {e}")
        return jsonify({"message": "Failed to fetch entries", "error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with db_manager.get_session() as session:
            session.execute("SELECT 1")
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": "disconnected", "error": str(e)}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))