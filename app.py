from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import numpy as np
from tensorflow.keras.models import load_model # type: ignore
from tensorflow.keras.preprocessing import image # type: ignore
import os
from werkzeug.utils import secure_filename
from tensorflow.keras.layers import Dropout # type: ignore
from dotenv import load_dotenv

load_dotenv()

# ---------------- FIXED DROPOUT ----------------
class FixedDropout(Dropout):
    def _get_noise_shape(self, inputs):
        return self.noise_shape

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# ---------------- DATABASE FUNCTION ----------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="project",
        buffered=True
    )
    

# ---------------- LOAD MODEL ----------------
model = load_model(
    "model.h5",
    compile=False,
    custom_objects={"FixedDropout": FixedDropout}
    )

#print("Model Input Shape:", model.input_shape)
#print("Model Output Shape:", model.output_shape)

# ---------------- UPLOAD FOLDER ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- HOME ----------------
@app.route('/')
def index():
    return redirect(url_for('login'))

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('fullname')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (fullname, email, username, password) VALUES (%s,%s,%s,%s)",
            (name, email, username, password)
        )
        db.commit()
        cursor.close()
        db.close()

        return redirect(url_for('login'))

    return render_template('register.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 🔐 Admin Login (Hardcoded)
        if username == "admin" and password == "admin123":
            session['username'] = "admin"
            return redirect(url_for('admin'))

        # 👤 Normal User Login
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            session['username'] = user['username']
            return redirect(url_for('home'))
        else:
            return "Invalid Credentials"

    return render_template('login.html')

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

# ---------------- UPLOAD PAGE ----------------
@app.route('/upload')
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))

    disease = session.pop('disease', None)
    confidence = session.pop('confidence', None)
    severity = session.pop('severity', None)
    ai_message = session.pop('ai_message', None)
    treatment = session.pop('treatment', None)
    prevention = session.pop('prevention', None)

    return render_template(
        'upload.html',
        disease=disease,
        confidence=confidence,
        severity=severity,
        ai_message=ai_message,
        treatment=treatment,
        prevention=prevention
    )

# ---------------- PREDICT ----------------
@app.route('/predict', methods=['POST'])
def predict():
    if 'username' not in session:
        return redirect(url_for('login'))

    img_file = request.files.get('image')
    if not img_file or img_file.filename == '':
        return "No image selected", 400

    filename = secure_filename(img_file.filename)
    img_path = os.path.join(UPLOAD_FOLDER, filename)
    img_file.save(img_path)

    # Image preprocessing (matches model input shape 512x512)
    img = image.load_img(img_path, target_size=(128, 128))
    img_array = image.img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    # Predict
    prediction = model.predict(img_array)
    confidence = float(np.max(prediction)) * 100
    class_index = np.argmax(prediction)

    if class_index == 0:
        disease = "Early_blight"
    elif class_index == 1:
        disease = "Healthy"
    elif class_index == 2:
        disease = "Late_blight"
    else:
        disease = "Unknown"
 
    # ---------------- AI INTELLIGENCE ----------------
    if disease=="Healthy":
        severity="No Risk"
        ai_message="The plant appears healthy. No immediate action required."
    elif confidence >= 90:
        severity = "High Risk"
        ai_message = "High confidence detection. Immediate action is recommended."
    elif confidence >= 70:
        severity = "Moderate Risk"
        ai_message = "Moderate confidence detection. Monitor the plant closely."
    else:
        severity = "Low Confidence"
        ai_message = "Low confidence result. Try uploading a clearer image."

    tips_data = {
    "Early_blight": {
        "treatment": "Remove infected leaves and apply fungicide weekly.",
        "prevention": "Avoid overhead watering and ensure proper plant spacing."
    },
    "Late_blight": {
        "treatment": "Use copper-based fungicide immediately.",
        "prevention": "Improve air circulation and avoid excessive moisture."
    },
    "Healthy": {
        "treatment": "No treatment required.",
        "prevention": "Maintain regular watering and proper sunlight."
    }
}

    tips = tips_data.get(disease, {
    "treatment": "No data available.",
    "prevention": "No data available."
})

    # Clean display name
    disease_display = disease.replace("Apple___", "").replace("_", " ")

    # Save prediction
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO predictions (username, disease, confidence) VALUES (%s,%s,%s)",
        (session['username'], disease_display, round(confidence, 2))
    )
    db.commit()
    cursor.close()
    db.close()

    # Save result in session (temporary)
    session['disease'] = disease_display
    session['confidence'] = round(confidence, 2)
    session['severity'] = severity
    session['ai_message'] = ai_message
    session['treatment'] = tips['treatment']
    session['prevention'] = tips['prevention']
   # print("raw prediction:", prediction)
   # print("Class index:", class_index)
    return redirect(url_for('upload')
    )
    
# ---------------- ADMIN PAGE ----------------
@app.route('/admin')
def admin():

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM predictions")
    total_predictions = cursor.fetchone()['total']

    cursor.execute("SELECT id,username,disease,confidence FROM predictions ORDER BY id DESC")
    predictions = cursor.fetchall()

    cursor.execute("SELECT disease, COUNT(*) as count FROM predictions GROUP BY disease")
    result = cursor.fetchall()

    labels = [row['disease'] for row in result]
    values = [row['count'] for row in result]

    return render_template(
        "admin.html",
        total_users=total_users,
        total_predictions=total_predictions,
        predictions=predictions,
        labels=labels,
        values=values
    )

@app.route('/delete_user/<username>')
def delete_user(username):

    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM users WHERE username=%s",(username,))
    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for('admin'))

@app.route('/delete_prediction/<int:id>')
def delete_history(id):

    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM predictions WHERE id=%s",(id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect(url_for('admin'))

# ---------------- PREMIUM HISTORY PAGE ----------------
@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Get all records
    cursor.execute(
        "SELECT id, disease, confidence FROM predictions WHERE username=%s ORDER BY id DESC",
        (session['username'],)
    )
    records = cursor.fetchall()

    # Total predictions
    cursor.execute(
        "SELECT COUNT(*) AS total FROM predictions WHERE username=%s",
        (session['username'],)
    )
    total = cursor.fetchone()['total']

    # Most common disease
    cursor.execute("""
        SELECT disease, COUNT(*) AS count
        FROM predictions
        WHERE username=%s
        GROUP BY disease
        ORDER BY count DESC
        LIMIT 1
    """, (session['username'],))
    most_common = cursor.fetchone()

    # Average confidence
    cursor.execute(
        "SELECT AVG(confidence) AS avg_conf FROM predictions WHERE username=%s",
        (session['username'],)
    )
    avg_conf = cursor.fetchone()['avg_conf']

    cursor.close()
    db.close()

    return render_template(
        'history.html',
        records=records,
        total=total,
        most_common=most_common,
        avg_conf=round(avg_conf, 2) if avg_conf else 0
    )

@app.route('/delete/<int:id>')
def delete_prediction(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "DELETE FROM predictions WHERE id=%s AND username=%s",
        (id, session['username'])
    )

    db.commit()
    cursor.close()
    db.close()

    return redirect(url_for('history'))
# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)