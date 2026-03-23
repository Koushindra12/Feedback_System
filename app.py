from flask import Flask, render_template, request, redirect, session, url_for, flash, make_response
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import datetime
import os
import csv
from io import StringIO

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

students_col = db["students"]
faculty_col = db["faculty"]
feedback_col = db["feedback"]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -----------------------------
# Home
# -----------------------------
@app.route("/")
def home():
    return render_template("home.html")


# -----------------------------
# Export Faculty Feedback CSV
# -----------------------------
@app.route("/export_feedback_csv")
def export_feedback_csv():
    if "faculty" not in session:
        return redirect(url_for("faculty_login"))

    current_faculty = faculty_col.find_one({"_id": ObjectId(session["faculty"])})
    if not current_faculty:
        session.clear()
        return redirect(url_for("faculty_login"))

    feedbacks = list(
        feedback_col.find({"faculty_id": session["faculty"]}).sort("date", -1)
    )

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Student Name",
        "Roll No",
        "Department",
        "Category",
        "Rating",
        "Comment",
        "Faculty Response",
        "Date"
    ])

    for fb in feedbacks:
        writer.writerow([
            fb.get("student_name", ""),
            fb.get("roll_no", ""),
            fb.get("department", ""),
            fb.get("category", "Other"),
            fb.get("rating", ""),
            fb.get("comment", ""),
            fb.get("faculty_response", ""),
            fb.get("date", "")
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=faculty_feedback.csv"
    response.headers["Content-type"] = "text/csv"

    return response


# -----------------------------
# Student Register
# -----------------------------
@app.route("/student_register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        roll_no = request.form["roll_no"].strip()
        name = request.form["name"].strip()
        department = request.form["department"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        existing_student = students_col.find_one({
            "$or": [
                {"roll_no": roll_no},
                {"email": email}
            ]
        })

        if existing_student:
            flash("Student already registered with this roll number or email.", "error")
            return redirect(url_for("student_register"))

        photo_path = ""
        if "profile_photo" in request.files:
            file = request.files["profile_photo"]
            if file and file.filename != "":
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"student_{roll_no}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
                    file.save(save_path)
                    photo_path = f"uploads/{unique_filename}"
                else:
                    flash("Only image files are allowed for student profile photo.", "error")
                    return redirect(url_for("student_register"))

        hashed_password = generate_password_hash(password)

        students_col.insert_one({
            "roll_no": roll_no,
            "name": name,
            "department": department,
            "email": email,
            "password": hashed_password,
            "profile_photo": photo_path
        })

        flash("Student registration successful. Please login.", "success")
        return redirect(url_for("student_login"))

    return render_template("student_register.html")


# -----------------------------
# Faculty Register
# -----------------------------
@app.route("/faculty_register", methods=["GET", "POST"])
def faculty_register():
    if request.method == "POST":
        name = request.form["name"].strip()
        department = request.form["department"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        existing_faculty = faculty_col.find_one({"email": email})
        if existing_faculty:
            flash("Faculty already registered with this email.", "error")
            return redirect(url_for("faculty_register"))

        photo_path = ""
        if "profile_photo" in request.files:
            file = request.files["profile_photo"]
            if file and file.filename != "":
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    safe_email = email.replace("@", "_").replace(".", "_")
                    unique_filename = f"faculty_{safe_email}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
                    file.save(save_path)
                    photo_path = f"uploads/{unique_filename}"
                else:
                    flash("Only image files are allowed for faculty profile photo.", "error")
                    return redirect(url_for("faculty_register"))

        hashed_password = generate_password_hash(password)

        faculty_col.insert_one({
            "name": name,
            "department": department,
            "email": email,
            "password": hashed_password,
            "profile_photo": photo_path
        })

        flash("Faculty registration successful. Please login.", "success")
        return redirect(url_for("faculty_login"))

    return render_template("faculty_register.html")


# -----------------------------
# Student Login
# -----------------------------
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        roll_no = request.form["roll_no"].strip()
        password = request.form["password"]

        student = students_col.find_one({"roll_no": roll_no})

        if student and check_password_hash(student["password"], password):
            session.clear()
            session["student"] = roll_no
            return redirect(url_for("student_dashboard"))

        flash("Invalid student roll number or password.", "error")
        return redirect(url_for("student_login"))

    return render_template("student_login.html")


# -----------------------------
# Faculty Login
# -----------------------------
@app.route("/faculty_login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        fac = faculty_col.find_one({"email": email})

        if fac and check_password_hash(fac["password"], password):
            session.clear()
            session["faculty"] = str(fac["_id"])
            return redirect(url_for("faculty_dashboard"))

        flash("Invalid faculty email or password.", "error")
        return redirect(url_for("faculty_login"))

    return render_template("faculty_login.html")


# -----------------------------
# Student Dashboard
# -----------------------------
@app.route("/student_dashboard", methods=["GET", "POST"])
def student_dashboard():
    if "student" not in session:
        return redirect(url_for("student_login"))

    current_student = students_col.find_one({"roll_no": session["student"]})
    if not current_student:
        session.clear()
        return redirect(url_for("student_login"))

    department = current_student["department"]
    faculty_list = list(faculty_col.find({"department": department}))

    if request.method == "POST":
        faculty_id = request.form["faculty_id"]
        category = request.form.get("category", "Other")
        rating = request.form["rating"]
        comment = request.form["comment"].strip()

        image_path = ""
        if "feedback_image" in request.files:
            file = request.files["feedback_image"]
            if file and file.filename != "":
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"feedback_{current_student['roll_no']}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
                    file.save(save_path)
                    image_path = f"uploads/{unique_filename}"
                else:
                    flash("Only image files are allowed for feedback screenshot.", "error")
                    return redirect(url_for("student_dashboard"))

        feedback_col.insert_one({
            "roll_no": current_student["roll_no"],
            "student_name": current_student["name"],
            "faculty_id": faculty_id,
            "department": department,
            "category": category,
            "rating": int(rating),
            "comment": comment,
            "image_path": image_path,
            "faculty_response": "",
            "student_notified": False,
            "faculty_notified": False,
            "date": datetime.datetime.now()
        })

        flash("Feedback submitted successfully.", "success")
        return redirect(url_for("student_dashboard"))

    student_feedback = list(
        feedback_col.find({"roll_no": current_student["roll_no"]}).sort("date", -1)
    )

    feedback_data = []
    for fb in student_feedback:
        fac = faculty_col.find_one({"_id": ObjectId(fb["faculty_id"])})
        fb["faculty_name"] = fac["name"] if fac else "Unknown Faculty"

        if "image_path" not in fb:
            fb["image_path"] = ""

        if "category" not in fb:
            fb["category"] = "Other"

        feedback_data.append(fb)

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
        {
            "roll_no": current_student["roll_no"],
            "student_notified": True
        },
        {
            "$set": {"student_notified": False}
        }
    )

    return render_template(
        "student_dashboard.html",
        student=current_student,
        faculty_list=faculty_list,
        feedbacks=feedback_data,
        notifications=student_notifications
    )


# -----------------------------
# Faculty Dashboard
# -----------------------------
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
        response = request.form["response"].strip()

        feedback_col.update_one(
            {"_id": ObjectId(feedback_id), "faculty_id": session["faculty"]},
            {"$set": {
                "faculty_response": response,
                "student_notified": True
            }}
        )

        flash("Response submitted successfully.", "success")
        return redirect(url_for("faculty_dashboard"))

    faculty_notifications = list(
        feedback_col.find({
            "faculty_id": session["faculty"],
            "faculty_notified": False
        })
    )

    feedback_col.update_many(
        {
            "faculty_id": session["faculty"],
            "faculty_notified": False
        },
        {
            "$set": {"faculty_notified": True}
        }
    )

    feedbacks = list(
        feedback_col.find({"faculty_id": session["faculty"]}).sort("date", -1)
    )

    for fb in feedbacks:
        if "category" not in fb:
            fb["category"] = "Other"
        if "image_path" not in fb:
            fb["image_path"] = ""

    return render_template(
        "faculty_dashboard.html",
        faculty=current_faculty,
        feedbacks=feedbacks,
        notifications=faculty_notifications
    )


# -----------------------------
# Logout
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)