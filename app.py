from flask import Flask, request, jsonify, render_template, session, send_file
from flask_cors import CORS
import sqlite3
import os
import hashlib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "secret123"
CORS(app)

# -------------------- DATABASE --------------------
def get_db():
    return sqlite3.connect("project.db", check_same_thread=False)

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        user TEXT,
        screen_time REAL,
        sleep REAL,
        study REAL,
        stress REAL,
        score REAL,
        date TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------- PASSWORD HASH --------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------- ML MODELS --------------------
texts = [
    "I feel alone","I feel sad","I feel depressed",
    "I avoid people","I hesitate to talk","I am shy",
    "I feel nervous","I like being alone",
    "I enjoy parties","I love friends",
    "I feel confident","I am outgoing",
    "I feel motivated","I overthink"
]

labels = [
    "Introvert","Introvert","Introvert",
    "Introvert","Low Confidence","Low Confidence",
    "Low Confidence","Introvert",
    "Extrovert","Extrovert",
    "High Confidence","Extrovert",
    "High Confidence","Low Confidence"
]

vectorizer = TfidfVectorizer()
X_text = vectorizer.fit_transform(texts)

model_personality = LinearSVC()
model_personality.fit(X_text, labels)

model_focus = RandomForestClassifier()

X_focus = [
    [6,5,2,8],[3,7,5,4],[2,8,6,3],
    [7,4,1,9],[1,9,7,2],[5,6,3,6],
    [4,8,5,3],[8,3,2,9]
]

y_focus = ["Low","High","High","Low","High","Medium","High","Low"]
model_focus.fit(X_focus, y_focus)

# -------------------- LOGIC --------------------
def calculate_score(screen, sleep, study, stress):
    score = (study * 10) + (sleep * 5) - (screen * 3) - (stress * 2)
    return max(0, min(score, 100))

# -------------------- ROUTES --------------------
@app.route("/")
def home():
    return render_template("index.html")

# SIGNUP
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO users VALUES (?, ?)",
                   (data["username"], hash_password(data["password"])))
    conn.commit()
    conn.close()

    return jsonify({"message": "User created"})

# LOGIN
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username=? AND password=?",
                   (data["username"], hash_password(data["password"])))
    user = cursor.fetchone()
    conn.close()

    if user:
        session["user"] = data["username"]
        return jsonify({"status": "success"})
    return jsonify({"status": "fail"})

# LOGOUT
@app.route("/logout")
def logout():
    session.pop("user", None)
    return jsonify({"message": "Logged out"})

# ANALYZE
@app.route("/analyze", methods=["POST"])
def analyze():
    if "user" not in session:
        return jsonify({"error": "Login required"})

    data = request.json

    screen = float(data["screen_time"])
    sleep = float(data["sleep"])
    study = float(data["study"])
    stress = float(data["stress"])
    text = data["text"]
    date = data["date"]

    text_vec = vectorizer.transform([text])
    personality = model_personality.predict(text_vec)[0]
    focus = model_focus.predict([[screen, sleep, study, stress]])[0]

    score = calculate_score(screen, sleep, study, stress)

    if score > 70:
        feedback = "Excellent productivity 🔥"
    elif score > 40:
        feedback = "Average performance 👍"
    else:
        feedback = "Needs improvement ⚠️"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO activity VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session["user"], screen, sleep, study, stress, score, date))
    conn.commit()
    conn.close()

    return jsonify({
        "personality": personality,
        "focus": focus,
        "score": score,
        "feedback": feedback
    })

# HISTORY
@app.route("/history")
def history():
    if "user" not in session:
        return jsonify([])

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT screen_time, sleep, study, stress, score, date 
    FROM activity WHERE user=?
    """, (session["user"],))

    data = cursor.fetchall()
    conn.close()

    return jsonify(data)

# PDF REPORT
@app.route("/report")
def report():
    if "user" not in session:
        return jsonify({"error": "Login required"})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM activity WHERE user=?", (session["user"],))
    data = cursor.fetchall()
    conn.close()

    file_path = "report.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []
    for row in data:
        text = f"User:{row[0]} Score:{row[5]} Date:{row[6]}"
        content.append(Paragraph(text, styles["Normal"]))

    doc.build(content)

    return send_file(file_path, as_attachment=True)

# -------------------- RUN --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)