
import os
import time
from io import BytesIO
from xml.sax.saxutils import escape
from functools import wraps

from flask import (
    Flask, render_template, request, make_response,
    redirect, url_for, session, flash
)
from dotenv import load_dotenv
from google import genai

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from models import db, User, Resume


# -------------------- APP CONFIGURATION --------------------

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "FLASK_SECRET_KEY",
    "change-this-secret-key-before-deployment"
)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///resume_builder.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# -------------------- GEMINI CONFIGURATION --------------------

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")


def generate_ai_summary(prompt):
    """Generate AI content and retry temporary Gemini errors."""

    if not client:
        raise ValueError("GEMINI_API_KEY was not found in the environment.")

    last_error = None

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )

            if response.text:
                return response.text.strip()

            raise ValueError("Gemini returned an empty response.")

        except Exception as error:
            last_error = error
            error_text = str(error).lower()

            temporary_error = any(
                marker in error_text
                for marker in [
                    "503", "unavailable", "high demand",
                    "429", "resource_exhausted", "500",
                    "502", "504", "timeout", "temporarily"
                ]
            )

            if not temporary_error or attempt == 2:
                raise

            wait_seconds = 2 ** (attempt + 1)

            print(
                f"Gemini temporary error. "
                f"Attempt {attempt + 1}/3. "
                f"Retrying in {wait_seconds}s."
            )

            time.sleep(wait_seconds)

    raise last_error


# -------------------- LOGIN REQUIRED --------------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


# -------------------- RESUME HELPERS --------------------

def get_resume_data(form):
    return {
        "name": form.get("name", "").strip(),
        "email": form.get("email", "").strip(),
        "phone": form.get("phone", "").strip(),
        "linkedin": form.get("linkedin", "").strip(),
        "summary": form.get("summary", "").strip(),
        "education": form.get("education", "").strip(),
        "skills": form.get("skills", "").strip(),
        "projects": form.get("projects", "").strip()
    }


def resume_to_dict(record):
    return {
        "name": record.name,
        "email": record.email,
        "phone": record.phone or "",
        "linkedin": record.linkedin or "",
        "summary": record.summary or "",
        "education": record.education or "",
        "skills": record.skills or "",
        "projects": record.projects or ""
    }


def save_resume_record(data, user_id, resume_id=None):
    record = None

    if resume_id:
        record = Resume.query.filter_by(
            id=resume_id,
            user_id=user_id
        ).first()

    if record is None:
        record = Resume(user_id=user_id)

    record.title = data["name"] or "My Resume"
    record.name = data["name"]
    record.email = data["email"]
    record.phone = data["phone"]
    record.linkedin = data["linkedin"]
    record.summary = data["summary"]
    record.education = data["education"]
    record.skills = data["skills"]
    record.projects = data["projects"]

    db.session.add(record)
    db.session.commit()

    return record


def get_form_resume_id():
    raw_id = request.form.get("resume_id", "").strip()

    if raw_id.isdigit():
        return int(raw_id)

    return None


def get_selected_template():
    template_name = request.form.get(
        "template", "modern"
    ).strip().lower()

    if template_name not in ("modern", "classic", "minimal"):
        template_name = "modern"

    return template_name


# -------------------- HOME --------------------

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


# -------------------- SIGNUP --------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please complete all required fields.")
            return render_template("signup.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return render_template("signup.html")

        if User.query.filter_by(email=email).first():
            flash("An account with this email address already exists.")
            return render_template("signup.html")

        user = User(name=name, email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Your account has been created successfully. Please log in.")
        return redirect(url_for("login"))

    return render_template("signup.html")


# -------------------- LOGIN --------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            session["user_name"] = user.name

            return redirect(url_for("dashboard"))

        flash("Invalid email address or password.")

    return render_template("login.html")


# -------------------- LOGOUT --------------------

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.")

    return redirect(url_for("login"))


# -------------------- DASHBOARD --------------------

@app.route("/dashboard")
@login_required
def dashboard():
    user_resumes = Resume.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Resume.id.desc()).all()

    return render_template(
        "dashboard.html",
        resumes=user_resumes,
        user_name=session.get("user_name", "")
    )


# -------------------- CREATE / SAVE RESUME --------------------

@app.route("/resume", methods=["GET", "POST"])
@login_required
def resume():
    if request.method == "POST":
        data = get_resume_data(request.form)
        resume_id = get_form_resume_id()
        template_name = get_selected_template()

        record = save_resume_record(
            data,
            session["user_id"],
            resume_id
        )

        return render_template(
            "resume.html",
            resume_data=data,
            submitted=True,
            ai_message="Resume saved to the database successfully.",
            saved_resume_id=record.id,
            selected_template=template_name,
            project_name="",
            project_technologies="",
            project_features=""
        )

    return render_template(
        "resume.html",
        resume_data=None,
        submitted=False,
        ai_message="",
        saved_resume_id=None,
        selected_template="modern",
        project_name="",
        project_technologies="",
        project_features=""
    )


# -------------------- EDIT RESUME --------------------

@app.route("/edit-resume/<int:resume_id>")
@login_required
def edit_resume(resume_id):
    record = Resume.query.filter_by(
        id=resume_id,
        user_id=session["user_id"]
    ).first_or_404()

    return render_template(
        "resume.html",
        resume_data=resume_to_dict(record),
        submitted=True,
        ai_message="",
        saved_resume_id=record.id,
        selected_template="modern",
        project_name="",
        project_technologies="",
        project_features=""
    )


# -------------------- DELETE RESUME --------------------

@app.route("/delete-resume/<int:resume_id>", methods=["POST"])
@login_required
def delete_resume(resume_id):
    record = Resume.query.filter_by(
        id=resume_id,
        user_id=session["user_id"]
    ).first_or_404()

    db.session.delete(record)
    db.session.commit()

    flash("Resume deleted successfully.")

    return redirect(url_for("dashboard"))


# -------------------- AI SUMMARY --------------------

@app.route("/improve-summary", methods=["POST"])
@login_required
def improve_summary():
    data = get_resume_data(request.form)
    resume_id = get_form_resume_id()
    template_name = get_selected_template()

    if not client:
        message = "GEMINI_API_KEY is missing. Please check your environment configuration."

    elif not data["summary"] and not data["skills"]:
        message = "Please enter your skills or professional summary first."

    else:
        prompt = f"""
You are a professional resume-writing assistant.

Write a concise, professional summary for a fresher
applying for an entry-level job.

Use only the information supplied below.
Do not invent degrees, experience, skills or achievements.
Use clear professional English.
Return only the final resume summary.

Education:
{data["education"]}

Skills:
{data["skills"]}

Projects:
{data["projects"]}

Existing summary:
{data["summary"]}
"""

        try:
            improved_summary = generate_ai_summary(prompt)
            data["summary"] = improved_summary

            record = save_resume_record(
                data,
                session["user_id"],
                resume_id
            )

            resume_id = record.id

            message = (
                "AI summary improved and saved to the database successfully."
            )

        except Exception as error:
            print("Gemini API error:", repr(error))
            error_text = str(error).lower()

            if any(
                marker in error_text
                for marker in [
                    "503", "unavailable", "high demand",
                    "500", "502", "504"
                ]
            ):
                message = (
                    "The Gemini server is temporarily busy. "
                    "Please try again in a few minutes."
                )

            elif any(
                marker in error_text
                for marker in ["429", "resource_exhausted", "quota"]
            ):
                message = (
                    "The Gemini API quota or request limit may have been reached. "
                    "Please check your quota in Google AI Studio."
                )

            elif any(
                marker in error_text
                for marker in [
                    "401", "403", "api key",
                    "unauthorized", "permission denied"
                ]
            ):
                message = "Please check your Gemini API key and permissions."

            elif "404" in error_text or "not found" in error_text:
                message = (
                    "The Gemini model is unavailable. "
                    "Please check the GEMINI_MODEL configuration."
                )

            else:
                message = (
                    "The AI summary could not be generated. "
                    "Please check the application logs for details."
                )

    return render_template(
        "resume.html",
        resume_data=data,
        submitted=True,
        ai_message=message,
        saved_resume_id=resume_id,
        selected_template=template_name,
        project_name="",
        project_technologies="",
        project_features=""
    )


# -------------------- AI PROJECT DESCRIPTION GENERATOR --------------------

@app.route("/generate-project-description", methods=["POST"])
@login_required
def generate_project_description():
    data = get_resume_data(request.form)
    resume_id = get_form_resume_id()
    template_name = get_selected_template()

    project_name = request.form.get("project_name", "").strip()
    project_technologies = request.form.get(
        "project_technologies", ""
    ).strip()
    project_features = request.form.get(
        "project_features", ""
    ).strip()

    message = ""

    if not client:
        message = "GEMINI_API_KEY is missing. Please check your environment configuration."

    elif not project_name:
        message = "Please enter the project name first."

    elif not project_technologies:
        message = "Please enter the technologies used in the project."

    elif not project_features:
        message = "Please enter the project features or details."

    else:
        prompt = f"""
You are a professional resume-writing assistant.

Create a concise, professional project description for a fresher's
resume. Use 2 to 4 bullet points.

Project name:
{project_name}

Technologies used:
{project_technologies}

Features and details provided by the user:
{project_features}

Rules:
- Use professional English.
- Focus on implementation, functionality and technologies.
- Do not invent metrics, users, results or features.
- Do not claim experience or achievements not supplied by the user.
- Keep the wording suitable for an entry-level job resume.
- Return only the project name and description.
"""

        try:
            generated_description = generate_ai_summary(prompt)

            existing_projects = data["projects"].strip()

            if existing_projects:
                data["projects"] = (
                    existing_projects
                    + "\n\n"
                    + generated_description
                )
            else:
                data["projects"] = generated_description

            record = save_resume_record(
                data,
                session["user_id"],
                resume_id
            )

            resume_id = record.id

            message = (
                "AI project description generated and saved "
                "to the resume database successfully."
            )

        except Exception as error:
            print("Gemini project description error:", repr(error))
            error_text = str(error).lower()

            if any(
                marker in error_text
                for marker in [
                    "503", "unavailable", "high demand",
                    "500", "502", "504"
                ]
            ):
                message = (
                    "The Gemini server is temporarily busy. "
                    "Please try again later."
                )

            elif any(
                marker in error_text
                for marker in ["429", "resource_exhausted", "quota"]
            ):
                message = "Please check your Gemini API quota."

            elif any(
                marker in error_text
                for marker in [
                    "401", "403", "api key", "unauthorized",
                    "permission denied"
                ]
            ):
                message = "Please check your Gemini API key and permissions."

            elif "404" in error_text or "not found" in error_text:
                message = (
                    "The Gemini model is unavailable. "
                    "Please check the GEMINI_MODEL configuration."
                )

            else:
                message = (
                    "The project description could not be generated. "
                    "Please check the application logs for details."
                )

    return render_template(
        "resume.html",
        resume_data=data,
        submitted=True,
        ai_message=message,
        saved_resume_id=resume_id,
        selected_template=template_name,
        project_name=project_name,
        project_technologies=project_technologies,
        project_features=project_features
    )


# -------------------- DOWNLOAD PDF --------------------

@app.route("/download-pdf", methods=["POST"])
@login_required
def download_pdf():
    data = get_resume_data(request.form)

    if not data["name"] or not data["email"]:
        return "Please enter your name and email first.", 400

    template_name = get_selected_template()

    # A resume ID must belong to the logged-in user.
    resume_id = get_form_resume_id()

    if resume_id:
        record = Resume.query.filter_by(
            id=resume_id,
            user_id=session["user_id"]
        ).first()

        if record is None:
            return "Resume not found.", 404

    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch
    )

    styles = getSampleStyleSheet()

    if template_name == "classic":
        primary_color = colors.HexColor("#222222")
        name_font = "Times-Bold"
        body_font = "Times-Roman"
        name_size = 22
        section_size = 13
        body_size = 10
        body_leading = 14

    elif template_name == "minimal":
        primary_color = colors.HexColor("#111111")
        name_font = "Helvetica-Bold"
        body_font = "Helvetica"
        name_size = 21
        section_size = 11
        body_size = 9.5
        body_leading = 13

    else:
        primary_color = colors.HexColor("#1D4ED8")
        name_font = "Helvetica-Bold"
        body_font = "Helvetica"
        name_size = 23
        section_size = 13
        body_size = 10
        body_leading = 14

    name_style = styles["Title"]
    name_style.fontName = name_font
    name_style.fontSize = name_size
    name_style.leading = name_size + 5
    name_style.textColor = primary_color

    section_style = styles["Heading2"]
    section_style.fontName = "Helvetica-Bold"
    section_style.fontSize = section_size
    section_style.leading = section_size + 3
    section_style.textColor = primary_color

    body_style = styles["BodyText"]
    body_style.fontName = body_font
    body_style.fontSize = body_size
    body_style.leading = body_leading

    content = [
        Paragraph(escape(data["name"]), name_style),
        Spacer(1, 8)
    ]

    contact = " | ".join(
        value for value in [
            data["email"],
            data["phone"],
            data["linkedin"]
        ] if value
    )

    if contact:
        contact_style = styles["BodyText"]
        contact_style.fontName = body_font
        contact_style.textColor = colors.HexColor("#475569")

        content.append(
            Paragraph(escape(contact), contact_style)
        )
        content.append(Spacer(1, 8))

    sections = [
        ("Professional Summary", data["summary"]),
        ("Education", data["education"]),
        ("Technical Skills", data["skills"]),
        ("Projects", data["projects"])
    ]

    for title, section_text in sections:
        if section_text:
            content.append(Spacer(1, 12))
            content.append(
                Paragraph(escape(title), section_style)
            )

            safe_text = escape(section_text).replace("\n", "<br/>")

            content.append(
                Paragraph(safe_text, body_style)
            )

    pdf.build(content)

    response = make_response(buffer.getvalue())
    buffer.close()

    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        'attachment; filename="My_Resume.pdf"'
    )

    return response


# -------------------- RUN APP --------------------

if __name__ == "__main__":
    app.run(debug=True)