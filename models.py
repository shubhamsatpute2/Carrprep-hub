from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Float, Date, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    hashed_password = Column(String(255), nullable=False)
    disabled = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    resumes = relationship("Resume", back_populates="owner")
    progress = relationship("UserProgress", back_populates="user", uselist=False)


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    
    # Personal Info
    name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(50))
    address = Column(String(255))
    linkedin = Column(String(255))
    github = Column(String(255))
    portfolio = Column(String(255))

    # Education & Experience
    education = Column(Text)        # store as JSON/text (e.g., [{"degree":"B.Tech", "year":"2023"}])
    experience = Column(Text)       # store as JSON/text (e.g., [{"company":"ABC", "role":"Dev", "years":"2"}])

    # Projects & Skills
    projects = Column(Text)         # JSON/text with multiple projects
    certifications = Column(Text)   # JSON/text with list of certifications
    skills = Column(Text)           # e.g., "Python, SQL, React"
    summary = Column(Text)

    # Achievements
    awards = Column(Text)           # scholarships, hackathons, etc.
    publications = Column(Text)     # research papers, blogs

    # Preferences
    languages = Column(Text)        # e.g., "English, Hindi"
    interests = Column(Text)        # hobbies or interests

    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="resumes")


class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    resume_completed = Column(Boolean, default=False)
    interviews_taken = Column(Integer, default=0)
    practice_score = Column(Float, default=0.0)

    user = relationship("User", back_populates="progress")

class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    notification_type = Column(String(50))  # e.g., "progress_email_sent"
    message = Column(Text)
    username = Column(String(100))
    user_email = Column(String(100))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)