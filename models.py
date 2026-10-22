
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    resumes = db.relationship(
        "Resume",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False, default="My Resume")
    name = db.Column(db.String(150), nullable=False, default="")
    email = db.Column(db.String(150), nullable=False, default="")
    phone = db.Column(db.String(50), default="")
    linkedin = db.Column(db.String(250), default="")
    summary = db.Column(db.Text, default="")
    education = db.Column(db.Text, default="")
    skills = db.Column(db.Text, default="")
    projects = db.Column(db.Text, default="")

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )
