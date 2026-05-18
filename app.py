from flask import Flask, render_template, request, redirect, session, url_for, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import datetime
import os


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super_secret_key_change_this")

# Upload config
app.config["UPLOAD_FOLDER"] = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# MongoDB Atlas connection
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["Koushindra"]

students_col       = db["students"]
faculty_col        = db["faculty"]
feedback_col       = db["feedback"]
public_feedback_col = db["public_feedback"]   # For public/anonymous faculty feedback


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────
# Home
# ─────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html")



# ─────────────────────────────────────────────
# Export Feedback as Printable HTML Report (Save as PDF via browser)
# ─────────────────────────────────────────────
@app.route("/export_feedback_report")
def export_feedback_report():
    if "faculty" not in session:
        flash("Please login first", "error")
        return redirect(url_for("faculty_login"))

    current_faculty = faculty_col.find_one({"_id": ObjectId(session["faculty"])})
    if not current_faculty:
        session.clear()
        return redirect(url_for("faculty_login"))

    feedbacks = list(
        feedback_col.find({"faculty_id": session["faculty"]}).sort("date", -1)
    )

    for fb in feedbacks:
        fb["date_str"] = (
            fb.get("date").strftime("%d %b %Y, %H:%M") if fb.get("date") else "N/A"
        )
        if "category" not in fb:
            fb["category"] = "Other"

    today = datetime.datetime.now().strftime("%d %B %Y")

    return render_template(
        "faculty_feedback_report.html",
        faculty=current_faculty,
        feedbacks=feedbacks,
        today=today
    )


# ─────────────────────────────────────────────
# Student Register
# ─────────────────────────────────────────────
@app.route("/student_register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        roll_no    = request.form["roll_no"].strip()
        name       = request.form["name"].strip()
        department = request.form["department"].strip()
        email      = request.form["email"].strip().lower()
        password   = request.form["password"]

        existing = students_col.find_one({
            "$or": [{"roll_no": roll_no}, {"email": email}]
        })

        if existing:
            flash("Student already registered with this roll number or email.", "error")
            return redirect(url_for("student_register"))

        photo_path = ""
        if "profile_photo" in request.files:
            file = request.files["profile_photo"]
            if file and file.filename != "":
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = (
                        f"student_{roll_no}_"
                        f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    )
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
                    photo_path = f"uploads/{unique_filename}"
                else:
                    flash("Only image files are allowed for profile photo.", "error")
                    return redirect(url_for("student_register"))

        students_col.insert_one({
            "roll_no":       roll_no,
            "name":          name,
            "department":    department,
            "email":         email,
            "password":      generate_password_hash(password),
            "profile_photo": photo_path
        })

        flash("Student registration successful. Please login.", "success")
        return redirect(url_for("student_login"))

    return render_template("student_register.html")


# ─────────────────────────────────────────────
# Faculty Register
# ─────────────────────────────────────────────
@app.route("/faculty_register", methods=["GET", "POST"])
def faculty_register():
    if request.method == "POST":
        name       = request.form["name"].strip()
        department = request.form["department"].strip()
        email      = request.form["email"].strip().lower()
        password   = request.form["password"]

        if faculty_col.find_one({"email": email}):
            flash("Faculty already registered with this email.", "error")
            return redirect(url_for("faculty_register"))

        photo_path = ""
        if "profile_photo" in request.files:
            file = request.files["profile_photo"]
            if file and file.filename != "":
                if allowed_file(file.filename):
                    filename   = secure_filename(file.filename)
                    safe_email = email.replace("@", "_").replace(".", "_")
                    unique_filename = (
                        f"faculty_{safe_email}_"
                        f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    )
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
                    photo_path = f"uploads/{unique_filename}"
                else:
                    flash("Only image files are allowed for profile photo.", "error")
                    return redirect(url_for("faculty_register"))

        faculty_col.insert_one({
            "name":          name,
            "department":    department,
            "email":         email,
            "password":      generate_password_hash(password),
            "profile_photo": photo_path
        })

        flash("Faculty registration successful. Please login.", "success")
        return redirect(url_for("faculty_login"))

    return render_template("faculty_register.html")


# ─────────────────────────────────────────────
# Student Login
# ─────────────────────────────────────────────
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        roll_no  = request.form["roll_no"].strip()
        password = request.form["password"]

        student = students_col.find_one({"roll_no": roll_no})
        if student and check_password_hash(student["password"], password):
            session.clear()
            session["student"] = roll_no
            return redirect(url_for("student_dashboard"))

        flash("Invalid student roll number or password.", "error")
        return redirect(url_for("student_login"))

    return render_template("student_login.html")


# ─────────────────────────────────────────────
# Faculty Login
# ─────────────────────────────────────────────
@app.route("/faculty_login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        email    = request.form["email"].strip().lower()
        password = request.form["password"]

        fac = faculty_col.find_one({"email": email})
        if fac and check_password_hash(fac["password"], password):
            session.clear()
            session["faculty"] = str(fac["_id"])
            return redirect(url_for("faculty_dashboard"))

        flash("Invalid faculty email or password.", "error")
        return redirect(url_for("faculty_login"))

    return render_template("faculty_login.html")


# ─────────────────────────────────────────────
# Student Dashboard
# ─────────────────────────────────────────────
@app.route("/student_dashboard", methods=["GET", "POST"])
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("student_login"))

    current_student = students_col.find_one({"roll_no": session["student"]})
    if not current_student:
        session.clear()
        return redirect(url_for("student_login"))

    department   = current_student["department"]
    faculty_list = list(faculty_col.find({"department": department}))

    if request.method == "POST":
        faculty_id = request.form["faculty_id"]
        category   = request.form.get("category", "Other")
        comment    = request.form["comment"].strip()

        image_path = ""
        if "feedback_image" in request.files:
            file = request.files["feedback_image"]
            if file and file.filename != "":
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = (
                        f"feedback_{current_student['roll_no']}_"
                        f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    )
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
                    image_path = f"uploads/{unique_filename}"
                else:
                    flash("Only image files are allowed for feedback screenshot.", "error")
                    return redirect(url_for("student_dashboard"))

        feedback_col.insert_one({
            "roll_no":          current_student["roll_no"],
            "student_name":     current_student["name"],
            "faculty_id":       faculty_id,
            "department":       department,
            "category":         category,
            "comment":          comment,
            "image_path":       image_path,
            "faculty_response": "",
            "student_notified": False,
            "faculty_notified": False,
            "date":             datetime.datetime.now()
        })

        flash("Feedback submitted successfully.", "success")
        return redirect(url_for("student_dashboard"))

    # Fetch previous feedbacks
    student_feedback = list(
        feedback_col.find({"roll_no": current_student["roll_no"]}).sort("date", -1)
    )

    feedback_data = []
    for fb in student_feedback:
        fac = faculty_col.find_one({"_id": ObjectId(fb["faculty_id"])})
        fb["faculty_name"] = fac["name"] if fac else "Unknown Faculty"
        fb.setdefault("image_path", "")
        fb.setdefault("category", "Other")
        feedback_data.append(fb)

    # Notifications
    student_notifications = list(
        feedback_col.find({
            "roll_no": current_student["roll_no"],
            "student_notified": True
        })
    )

    for n in student_notifications:
        fac = faculty_col.find_one({"_id": ObjectId(n["faculty_id"])})
        n["faculty_name"] = fac["name"] if fac else "Faculty"

    feedback_col.update_many(
        {"roll_no": current_student["roll_no"], "student_notified": True},
        {"$set": {"student_notified": False}}
    )

    return render_template(
        "student_dashboard.html",
        student=current_student,
        faculty_list=faculty_list,
        feedbacks=feedback_data,
        notifications=student_notifications
    )


# ─────────────────────────────────────────────
# Submit Public Feedback for a Faculty (no login required)
# ─────────────────────────────────────────────
@app.route("/submit_public_feedback/<faculty_id>", methods=["POST"])
def submit_public_feedback(faculty_id):
    name    = request.form.get("pub_name", "").strip()
    comment = request.form.get("pub_comment", "").strip()

    if not comment:
        flash("Feedback message cannot be empty.", "error")
        return redirect(url_for("faculty_dashboard"))

    faculty = faculty_col.find_one({"_id": ObjectId(faculty_id)})
    if not faculty:
        flash("Faculty not found.", "error")
        return redirect(url_for("home"))

    public_feedback_col.insert_one({
        "faculty_id":   faculty_id,
        "faculty_name": faculty.get("name", ""),
        "name":         name if name else "Anonymous",
        "comment":      comment,
        "date":         datetime.datetime.now()
    })

    flash("Thank you! Your feedback has been submitted.", "success")
    # Redirect back — if faculty is logged in, back to dashboard; else home
    if "faculty" in session and session["faculty"] == faculty_id:
        return redirect(url_for("faculty_dashboard"))
    return redirect(url_for("home"))


# ─────────────────────────────────────────────
# Faculty Dashboard
# ─────────────────────────────────────────────
@app.route("/faculty_dashboard", methods=["GET", "POST"])
def faculty_dashboard():
    if "faculty" not in session:
        return redirect(url_for("faculty_login"))

    current_faculty = faculty_col.find_one({"_id": ObjectId(session["faculty"])})
    if not current_faculty:
        session.clear()
        return redirect(url_for("faculty_login"))

    if request.method == "POST":
        feedback_id = request.form["feedback_id"]
        response    = request.form["response"].strip()

        feedback_col.update_one(
            {"_id": ObjectId(feedback_id), "faculty_id": session["faculty"]},
            {"$set": {
                "faculty_response": response,
                "student_notified": True
            }}
        )

        flash("Response submitted successfully.", "success")
        return redirect(url_for("faculty_dashboard"))

    # New feedback notifications
    faculty_notifications = list(
        feedback_col.find({
            "faculty_id":       session["faculty"],
            "faculty_notified": False
        })
    )

    feedback_col.update_many(
        {"faculty_id": session["faculty"], "faculty_notified": False},
        {"$set": {"faculty_notified": True}}
    )

    feedbacks = list(
        feedback_col.find({"faculty_id": session["faculty"]}).sort("date", -1)
    )

    for fb in feedbacks:
        fb.setdefault("category", "Other")
        fb.setdefault("image_path", "")

    # Public feedback received
    public_feedbacks = list(
        public_feedback_col.find({"faculty_id": session["faculty"]}).sort("date", -1)
    )

    for pfb in public_feedbacks:
        pfb["date_str"] = (
            pfb["date"].strftime("%d %b %Y, %H:%M") if pfb.get("date") else "N/A"
        )

    return render_template(
        "faculty_dashboard.html",
        faculty=current_faculty,
        feedbacks=feedbacks,
        notifications=faculty_notifications,
        public_feedbacks=public_feedbacks
    )


# ─────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
