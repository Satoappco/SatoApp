# webhook.py
import os
import json
import sqlite3
from flask import Flask, request, jsonify

DB = os.environ.get("DB_PATH", "data.db")
API_KEY = os.environ.get("API_KEY", "SatoLogos")  # set a strong key in prod

app = Flask(__name__)

def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("""
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            user_choice TEXT,
            raw_payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        conn.close()

# Initialize database at startup instead of using @app.before_first_request
init_db()

def save_entry(user_name, user_choice, raw):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO entries (user_name, user_choice, raw_payload) VALUES (?, ?, ?)",
              (user_name, user_choice, json.dumps(raw)))
    conn.commit()
    conn.close()

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
    save_entry(user_name, user_choice, data)

    return jsonify({"message": f"Saved: user_name={user_name}, user_choice={user_choice}"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))