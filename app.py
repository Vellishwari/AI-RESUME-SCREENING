from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import os
import pytesseract
from PIL import Image
from PyPDF2 import PdfReader
from docx import Document


# --------------------------------------------------
# Flask Configuration
# --------------------------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = "ai_resume_secret_key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(BASE_DIR, "database.db")
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --------------------------------------------------
# Database
# --------------------------------------------------

db = SQLAlchemy(app)


# --------------------------------------------------
# Login Manager
# --------------------------------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# --------------------------------------------------
# User Model
# --------------------------------------------------

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )


# --------------------------------------------------
# Screening History Model
# --------------------------------------------------

class ScreeningHistory(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    filename = db.Column(
        db.String(255),
        nullable=False
    )

    job_role = db.Column(
        db.String(100),
        nullable=False
    )

    experience = db.Column(
        db.String(50)
    )

    score = db.Column(
        db.Integer,
        nullable=False
    )

    status = db.Column(
        db.String(50),
        nullable=False
    )

    matched_skills = db.Column(
        db.Text
    )

    missing_skills = db.Column(
        db.Text
    )


# --------------------------------------------------
# Load User
# --------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------
# Tesseract OCR Configuration
# --------------------------------------------------

tesseract_path = r"D:\Users\tesseract.exe"

if os.path.exists(tesseract_path):

    pytesseract.pytesseract.tesseract_cmd = tesseract_path

else:

    raise FileNotFoundError(
        f"Tesseract not found at: {tesseract_path}"
    )


# --------------------------------------------------
# Extract Text From Resume
# --------------------------------------------------

def extract_text(file_path):

    extension = file_path.lower().split(".")[-1]

    # JPG / JPEG / PNG
    if extension in ["jpg", "jpeg", "png"]:

        image = Image.open(file_path)

        text = pytesseract.image_to_string(image)

        return text

    # PDF
    elif extension == "pdf":

        text = ""

        reader = PdfReader(file_path)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text

        return text

    # DOCX
    elif extension == "docx":

        document = Document(file_path)

        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

        return text

    else:

        return ""


# --------------------------------------------------
# Job Skills
# --------------------------------------------------

JOB_SKILLS = {

    "Machine Learning Engineer": [
        "python",
        "machine learning",
        "tensorflow",
        "pytorch",
        "scikit-learn"
    ],

    "Web Developer": [
        "html",
        "css",
        "javascript",
        "react",
        "python",
        "flask"
    ],

    "Software Developer": [
        "python",
        "java",
        "c++",
        "sql",
        "git",
        "api"
    ],

    "Data Analyst": [
        "python",
        "sql",
        "excel",
        "pandas",
        "numpy",
        "power bi"
    ],

    "Data Scientist": [
        "python",
        "machine learning",
        "pandas",
        "numpy",
        "sql",
        "statistics"
    ]
}


# --------------------------------------------------
# Home Page
# --------------------------------------------------

@app.route("/")
def home():

    if current_user.is_authenticated:

        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# --------------------------------------------------
# Register
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        if not name or not email or not password:

            flash("All fields are required.")

            return redirect(url_for("register"))

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash("Email already registered.")

            return redirect(url_for("register"))

        hashed_password = generate_password_hash(
            password
        )

        new_user = User(
            name=name,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)

        db.session.commit()

        flash("Registration successful. Please login.")

        return redirect(url_for("login"))

    return render_template("register.html")


# --------------------------------------------------
# Login
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email")

        password = request.form.get("password")

        user = User.query.filter_by(
            email=email
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            login_user(user)

            return redirect(
                url_for("dashboard")
            )

        flash("Invalid email or password.")

    return render_template("login.html")


# --------------------------------------------------
# Logout
# --------------------------------------------------

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(url_for("login"))


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    history = ScreeningHistory.query.filter_by(
        user_id=current_user.id
    ).order_by(
        ScreeningHistory.id.desc()
    ).all()

    return render_template(
        "index.html",
        history=history
    )


# --------------------------------------------------
# Resume Screening
# --------------------------------------------------

@app.route("/screen", methods=["POST"])
@login_required
def screen_resume():

    resume = request.files.get("resume")

    job_role = request.form.get("job_role")

    experience = request.form.get("experience")


    # Check resume
    if not resume or resume.filename == "":

        flash("Please upload a resume.")

        return redirect(
            url_for("dashboard")
        )


    # Secure filename
    filename = secure_filename(
        resume.filename
    )


    # Save resume
    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    resume.save(file_path)


    # Extract resume text
    resume_text = extract_text(
        file_path
    )

    resume_text_lower = resume_text.lower()


    # Get required skills
    required_skills = JOB_SKILLS.get(
        job_role,
        []
    )


    # Find matched and missing skills
    matched_skills = []

    missing_skills = []


    for skill in required_skills:

        if skill.lower() in resume_text_lower:

            matched_skills.append(skill)

        else:

            missing_skills.append(skill)


    # Calculate match score
    if len(required_skills) > 0:

        score = int(
            len(matched_skills)
            / len(required_skills)
            * 100
        )

    else:

        score = 0


    # Recommendation
    if score >= 70:

        recommendation = (
            "Strong candidate for this role."
        )

        status = "RECOMMENDED"

    elif score >= 40:

        recommendation = (
            "Candidate needs improvement "
            "in some required skills."
        )

        status = "CONSIDER"

    else:

        recommendation = (
            "Candidate does not match "
            "the required skills."
        )

        status = "NOT RECOMMENDED"


    # --------------------------------------------------
    # Save Screening Result To Database
    # --------------------------------------------------

    screening = ScreeningHistory(

        user_id=current_user.id,

        filename=filename,

        job_role=job_role,

        experience=experience,

        score=score,

        status=status,

        matched_skills=", ".join(
            matched_skills
        ),

        missing_skills=", ".join(
            missing_skills
        )
    )

    db.session.add(screening)

    db.session.commit()


    # --------------------------------------------------
    # Show Result
    # --------------------------------------------------

    return render_template(

        "result.html",

        filename=filename,

        job_role=job_role,

        experience=experience,

        score=score,

        matched_skills=matched_skills,

        missing_skills=missing_skills,

        recommendation=recommendation,

        status=status
    )


# --------------------------------------------------
# Create Database Tables
# --------------------------------------------------

with app.app_context():

    db.create_all()


# --------------------------------------------------
# Run Application
# --------------------------------------------------

if __name__ == "__main__":

    app.run(debug=True)