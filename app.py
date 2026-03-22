from fastapi import FastAPI, HTTPException, Depends, status, Body, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
from jose import JWTError, jwt
import bcrypt
from datetime import datetime, timedelta
import random
import json
import logging
from gemini_runner import run
from email_service import send_progress_email, send_welcome_email
from resume_generator import generate_resume_docx, generate_resume_pdf

# load environment variables from .env (email_service already does this, but
# we need it here for Google API keys)
from dotenv import load_dotenv
load_dotenv()

import os
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, engine, Base
from models import User as UserModel, Resume as ResumeModel, UserProgress as UserProgressModel, AdminNotification as AdminNotificationModel
from sqlalchemy import func

app = FastAPI(title="CareerPrep Hub API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database tables on startup
@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# JWT
SECRET_KEY = "b2b23ef4c58772f96fc831d3a5147ad2ff8b62239ed773607f43e6a4ae8a4c9a"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# Pydantic Schemas
class User(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    is_admin: Optional[bool] = False


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class Resume(BaseModel):
    # Personal Info
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None

    education: List[dict]   # [{"degree": "B.Tech", "institution": "XYZ Univ", "year": "2023"}]
    experience: List[dict]  # [{"company": "ABC", "role": "Dev", "years": "2"}]

    projects: Optional[List[dict]] = None  # [{"title": "AI Chatbot", "description": "..."}]
    certifications: Optional[List[str]] = None
    skills: List[str]
    summary: Optional[str] = None

    awards: Optional[List[str]] = None
    publications: Optional[List[str]] = None

    languages: Optional[List[str]] = None
    interests: Optional[List[str]] = None

class InterviewQuestion(BaseModel):
    question: str
    answer: Optional[str] = None


class PracticeQuestion(BaseModel):
    id: int
    question: str
    options: List[str]
    correct_answer: str
    category: str


class PracticeAnswer(BaseModel):
    question_id: int
    selected_option: str


class UserProgress(BaseModel):
    user_id: str
    resume_completed: bool = False
    interviews_taken: int = 0
    practice_score: int = 0


class ChatbotRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None


def verify_password(plain_password, hashed_password):
    """Verify password using bcrypt directly with 72-byte limit."""
    try:
        # Truncate password to 72 bytes of UTF-8 encoded data
        password_bytes = plain_password.encode('utf-8')[:72]
        
        # Handle hashed_password as string or bytes
        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode('utf-8')
        else:
            hashed_bytes = hashed_password
            
        # Verify password using bcrypt
        is_valid = bcrypt.checkpw(password_bytes, hashed_bytes)
        
        if not is_valid:
            logger.debug(f"Password verification failed for bcrypt check")
        
        return is_valid
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        logger.error(f"Hash format: {type(hashed_password)}, Hash value: {str(hashed_password)[:50] if hashed_password else 'None'}")
        return False


def get_password_hash(password):
    """Hash password using bcrypt directly with 72-byte limit."""
    # Truncate password to 72 bytes of UTF-8 encoded data (bcrypt hard limit)
    password_bytes = password.encode('utf-8')[:72]
    # Generate salt and hash (rounds=12 for security)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(UserModel).where(UserModel.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, username: str, password: str):
    user = await get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = await get_user_by_username(db, token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: UserModel = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_admin_user(current_user: UserModel = Depends(get_current_active_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


INTERVIEW_QUESTIONS = [
    {"id": 1, "question": "Tell me about yourself.", "type": "general"},
    {"id": 2, "question": "What are your strengths and weaknesses?", "type": "general"},
    {"id": 3, "question": "Why do you want to work for our company?", "type": "general"},
    {"id": 4, "question": "Describe a challenging project you worked on.", "type": "technical"},
    {"id": 5, "question": "How do you handle tight deadlines?", "type": "behavioral"},
    {"id": 6, "question": "What are your salary expectations?", "type": "general"},
    {"id": 7, "question": "What motivates you?", "type": "general"},
    {"id": 8, "question": "Explain the concept of normalization in databases.", "type": "technical"},
    {"id": 9, "question": "How do you prioritize tasks during a project?", "type": "behavioral"},
    {"id": 10, "question": "Describe a time you showed leadership.", "type": "behavioral"},
    {"id": 11, "question": "What is your greatest professional achievement?", "type": "general"},
    {"id": 12, "question": "Explain the difference between SQL and NoSQL databases.", "type": "technical"},
    {"id": 13, "question": "How do you stay updated with new technology trends?", "type": "general"},
    {"id": 14, "question": "Describe a conflict you had at work and how you resolved it.", "type": "behavioral"},
    {"id": 15, "question": "What is ACID property in database transactions?", "type": "technical"},
    {"id": 16, "question": "How do you handle pressure at work?", "type": "behavioral"},
    {"id": 17, "question": "Explain the difference between procedural and object-oriented programming.", "type": "technical"},
    {"id": 18, "question": "Why should we hire you?", "type": "general"},
    {"id": 19, "question": "What is a deadlock in DBMS?", "type": "technical"},
    {"id": 20, "question": "Describe a time you failed and what you learned from it.", "type": "behavioral"},
    {"id": 21, "question": "What programming languages are you proficient in?", "type": "technical"},
    {"id": 22, "question": "How do you handle feedback?", "type": "behavioral"},
    {"id": 23, "question": "Explain indexing and its importance in databases.", "type": "technical"},
    {"id": 24, "question": "Describe your ideal work environment.", "type": "general"},
    {"id": 25, "question": "What is your approach to team collaboration?", "type": "behavioral"},
    {"id": 26, "question": "Explain the difference between DELETE and TRUNCATE commands.", "type": "technical"},
    {"id": 27, "question": "How do you deal with ambiguity in requirements?", "type": "behavioral"},
    {"id": 28, "question": "What is the difference between inner join and outer join?", "type": "technical"},
    {"id": 29, "question": "Where do you see yourself in five years?", "type": "general"},
    {"id": 30, "question": "Explain the function of primary key and foreign key.", "type": "technical"},
    {"id": 31, "question": "Describe a situation where you took initiative.", "type": "behavioral"},
    {"id": 32, "question": "What is the difference between clustered and non-clustered indexes?", "type": "technical"},
    {"id": 33, "question": "How do you manage work-life balance?", "type": "general"},
    {"id": 34, "question": "What are transactions in DBMS?", "type": "technical"},
    {"id": 35, "question": "Tell me about a time you adapted to change.", "type": "behavioral"},
    {"id": 36, "question": "How would you optimize a slow-running query?", "type": "technical"},
    {"id": 37, "question": "What are your hobbies?", "type": "general"},
    {"id": 38, "question": "How do you ensure data security in a database?", "type": "technical"},
    {"id": 39, "question": "Tell me about a time you worked under a difficult manager.", "type": "behavioral"},
    {"id": 40, "question": "What is your experience with software development methodologies?", "type": "technical"},
    {"id": 41, "question": "How do you approach learning a new skill?", "type": "general"},
    {"id": 42, "question": "Explain ACID properties with examples.", "type": "technical"},
    {"id": 43, "question": "Give an example of how you handled a conflict in a team.", "type": "behavioral"},
    {"id": 44, "question": "What is data normalization? Why is it important?", "type": "technical"},
    {"id": 45, "question": "Tell me about a time you had to meet a tight deadline.", "type": "behavioral"},
    {"id": 46, "question": "What are views in SQL?", "type": "technical"},
    {"id": 47, "question": "How do you motivate yourself and others?", "type": "general"},
    {"id": 48, "question": "Explain referential integrity.", "type": "technical"},
    {"id": 49, "question": "Describe a time when you had to persuade someone.", "type": "behavioral"},
    {"id": 50, "question": "What is indexing in databases?", "type": "technical"},
    {"id": 51, "question": "What skills set you apart from other candidates?", "type": "general"},
    {"id": 52, "question": "What is the difference between DELETE, DROP, and TRUNCATE?", "type": "technical"},
    {"id": 53, "question": "How do you approach problem-solving?", "type": "general"},
    {"id": 54, "question": "What are stored procedures?", "type": "technical"},
    {"id": 55, "question": "Describe your communication style.", "type": "general"},
    {"id": 56, "question": "Explain the concept of database sharding.", "type": "technical"},
    {"id": 57, "question": "Tell me about a time you led a successful project.", "type": "behavioral"},
    {"id": 58, "question": "What is a deadlock and how do you prevent it?", "type": "technical"},
    {"id": 59, "question": "How do you handle multiple priorities?", "type": "behavioral"},
    {"id": 60, "question": "What is a transaction log?", "type": "technical"},
    {"id": 61, "question": "Describe a time when you made a mistake and how you handled it.", "type": "behavioral"},
    {"id": 62, "question": "What is database partitioning?", "type": "technical"},
    {"id": 63, "question": "What are your career goals?", "type": "general"},
    {"id": 64, "question": "Explain the difference between NoSQL and SQL databases.", "type": "technical"},
    {"id": 65, "question": "How do you handle criticism?", "type": "behavioral"},
    {"id": 66, "question": "Explain database replication.", "type": "technical"},
    {"id": 67, "question": "What is your preferred working style?", "type": "general"},
    {"id": 68, "question": "Describe a difficult bug you fixed.", "type": "technical"},
    {"id": 69, "question": "Tell me about a time you helped a colleague.", "type": "behavioral"},
    {"id": 70, "question": "What is indexing and how does it improve query performance?", "type": "technical"}
]

PRACTICE_QUESTIONS = [
    {"id": 1, "question": "What is the time complexity of binary search?", "options": ["O(n)", "O(log n)", "O(n²)", "O(1)"], "correct_answer": "O(log n)", "category": "Technical"},
    {"id": 2, "question": "Which HTTP method is used to update a resource?", "options": ["GET", "POST", "PUT", "DELETE"], "correct_answer": "PUT", "category": "Technical"},
    {"id": 3, "question": "What does SQL stand for?", "options": ["Structured Query Language", "Simple Query Language", "Standard Query Language", "System Query Language"], "correct_answer": "Structured Query Language", "category": "Technical"},
    {"id": 4, "question": "Which operator is used to access members of a structure in C?", "options": [".", "->", "&", "*"], "correct_answer": ".", "category": "Technical"},
    {"id": 5, "question": "Which sorting algorithm has the best average-case performance?", "options": ["Bubble Sort", "Insertion Sort", "Merge Sort", "Selection Sort"], "correct_answer": "Merge Sort", "category": "Technical"},
    {"id": 6, "question": "Which protocol is used for secure HTTP connections?", "options": ["FTP", "SMTP", "HTTPS", "HTTP"], "correct_answer": "HTTPS", "category": "Technical"},
    {"id": 7, "question": "What does OOP stand for?", "options": ["Object Oriented Programming", "Out Of Process", "Optimum Output Programming", "Order Of Precedence"], "correct_answer": "Object Oriented Programming", "category": "Technical"},
    {"id": 8, "question": "Which layer in OSI model is responsible for data encryption?", "options": ["Network", "Session", "Presentation", "Application"], "correct_answer": "Presentation", "category": "Technical"},
    {"id": 9, "question": "Which of the following is not a primitive data type in Java?", "options": ["int", "float", "boolean", "String"], "correct_answer": "String", "category": "Technical"},
    {"id": 10, "question": "What is the default port for HTTP?", "options": ["21", "25", "80", "443"], "correct_answer": "80", "category": "Technical"},

    {"id": 11, "question": "In Python, what does the 'len' function do?", "options": ["Returns length", "Returns sum", "Returns max", "Returns min"], "correct_answer": "Returns length", "category": "Technical"},
    {"id": 12, "question": "Which algorithm is used in Database indexing?", "options": ["Bubble Sort", "B+ Tree", "Quick Sort", "DFS"], "correct_answer": "B+ Tree", "category": "Technical"},
    {"id": 13, "question": "Which logic gate outputs 1 only when both inputs are 1?", "options": ["OR", "NOR", "AND", "NOT"], "correct_answer": "AND", "category": "Technical"},
    {"id": 14, "question": "Which method is used to create an object in Java?", "options": ["object()", "new()", "create()", "init()"], "correct_answer": "new()", "category": "Technical"},
    {"id": 15, "question": "Which keyword is used to inherit a class in C++?", "options": ["extends", "implements", "inherit", "public"], "correct_answer": "public", "category": "Technical"},
    {"id": 16, "question": "Which IP address class is reserved for multicast?", "options": ["A", "B", "C", "D"], "correct_answer": "D", "category": "Technical"},
    {"id": 17, "question": "Which HTML tag is used to display a picture?", "options": ["<img>", "<picture>", "<src>", "<image>"], "correct_answer": "<img>", "category": "Technical"},
    {"id": 18, "question": "What is the maximum value of a signed 8-bit integer?", "options": ["255", "128", "127", "256"], "correct_answer": "127", "category": "Technical"},
    {"id": 19, "question": "Which structure is used to implement LIFO?", "options": ["Queue", "Stack", "Array", "Linked List"], "correct_answer": "Stack", "category": "Technical"},
    {"id": 20, "question": "What is the main purpose of DNS?", "options": ["IP addressing", "Domain resolution", "Email routing", "Web hosting"], "correct_answer": "Domain resolution", "category": "Technical"},

    {"id": 21, "question": "What is 15% of 200?", "options": ["25", "30", "35", "40"], "correct_answer": "30", "category": "Aptitude"},
    {"id": 22, "question": "If a car travels 60 km in 1.5 hours, what is its average speed?", "options": ["50 km/h", "40 km/h", "45 km/h", "60 km/h"], "correct_answer": "40 km/h", "category": "Aptitude"},
    {"id": 23, "question": "Find the next number: 1, 4, 9, 16, ?", "options": ["25", "36", "49", "64"], "correct_answer": "25", "category": "Aptitude"},
    {"id": 24, "question": "What is the smallest prime number?", "options": ["0", "1", "2", "3"], "correct_answer": "2", "category": "Aptitude"},
    {"id": 25, "question": "If 3x = 12, x=?", "options": ["2", "3", "4", "6"], "correct_answer": "4", "category": "Aptitude"},
    {"id": 26, "question": "What is the square root of 625?", "options": ["15", "20", "25", "30"], "correct_answer": "25", "category": "Aptitude"},
    {"id": 27, "question": "If the ratio of boys to girls is 3:2 and there are 30 boys, how many girls?", "options": ["10", "15", "20", "25"], "correct_answer": "20", "category": "Aptitude"},
    {"id": 28, "question": "If the selling price is ₹500 and profit is 20%, what is the cost price?", "options": ["₹400", "₹415", "₹425", "₹450"], "correct_answer": "₹415", "category": "Aptitude"},
    {"id": 29, "question": "What is the area of a circle with radius 7?", "options": ["49π", "14π", "21π", "22π"], "correct_answer": "49π", "category": "Aptitude"},
    {"id": 30, "question": "Which is the largest: 7/8, 15/16, 31/32, 63/64?", "options": ["7/8", "15/16", "31/32", "63/64"], "correct_answer": "63/64", "category": "Aptitude"},

    {"id": 31, "question": "A train at 60 km/h crosses a pole in 30 seconds. Its length?", "options": ["1500m", "900m", "500m", "300m"], "correct_answer": "500m", "category": "Aptitude"},
    {"id": 32, "question": "Find LCM of 12 and 18.", "options": ["36", "72", "24", "18"], "correct_answer": "36", "category": "Aptitude"},
    {"id": 33, "question": "Which number is not divisible by 3: 14, 18, 21, 27?", "options": ["14", "18", "21", "27"], "correct_answer": "14", "category": "Aptitude"},
    {"id": 34, "question": "If a=2, b=3, what is a^b?", "options": ["5", "6", "8", "9"], "correct_answer": "8", "category": "Aptitude"},
    {"id": 35, "question": "What is the value of x in: 2x + 5 = 15?", "options": ["5", "10", "15", "20"], "correct_answer": "5", "category": "Aptitude"},
    {"id": 36, "question": "The next term in the sequence 2, 6, 18, 54, ?", "options": ["108", "162", "216", "324"], "correct_answer": "162", "category": "Aptitude"},
    {"id": 37, "question": "If Simple Interest on ₹1000 for 2 years is ₹240, what is rate %?", "options": ["8%", "10%", "12%", "15%"], "correct_answer": "12%", "category": "Aptitude"},
    {"id": 38, "question": "What is 40% of 80?", "options": ["32", "36", "40", "48"], "correct_answer": "32", "category": "Aptitude"},
    {"id": 39, "question": "A bag has 3 red and 2 green balls. Probability of red?", "options": ["1/5", "2/5", "3/5", "4/5"], "correct_answer": "3/5", "category": "Aptitude"},
    {"id": 40, "question": "If 4 workers construct a wall in 6 days, how many days for 2 workers?", "options": ["9", "10", "11", "12"], "correct_answer": "12", "category": "Aptitude"},

    {"id": 41, "question": "If the cost price is ₹250 and selling price is ₹200, the loss percent?", "options": ["10%", "15%", "20%", "25%"], "correct_answer": "20%", "category": "Aptitude"},
    {"id": 42, "question": "In a team meeting, you disagree with a colleague's approach. What do you do?", "options": ["Stay silent", "Argue publicly", "Discuss privately later", "Present alternative respectfully"], "correct_answer": "Present alternative respectfully", "category": "HR"},
    {"id": 43, "question": "What would you do if you disagreed with a manager's decision?", "options": ["Accept blindly", "Discuss openly", "Complain to HR", "Ignore"], "correct_answer": "Discuss openly", "category": "HR"},
    {"id": 44, "question": "How do you handle tight deadlines?", "options": ["Avoid", "Prioritize work", "Delegate", "Delay"], "correct_answer": "Prioritize work", "category": "HR"},
    {"id": 45, "question": "Describe a time when you resolved a conflict in your team.", "options": ["Stay neutral", "Mediate and find common ground", "Take sides", "Ignore"], "correct_answer": "Mediate and find common ground", "category": "HR"},
    {"id": 46, "question": "If you notice unethical behavior at work, what should you do?", "options": ["Ignore", "Confront immediately", "Report as per policy", "Discuss with peers"], "correct_answer": "Report as per policy", "category": "HR"},
    {"id": 47, "question": "What do you do when assigned tasks are unclear?", "options": ["Guess and proceed", "Seek clarification", "Wait for instructions", "Ask colleagues"], "correct_answer": "Seek clarification", "category": "HR"},
    {"id": 48, "question": "How would you adapt to organizational change?", "options": ["Resist", "Ignore", "Learn and embrace", "Complain"], "correct_answer": "Learn and embrace", "category": "HR"},
    {"id": 49, "question": "Tell me about a time your expectations were exceeded.", "options": ["Feel grateful", "Complain", "Do nothing", "Appreciate and learn"], "correct_answer": "Appreciate and learn", "category": "HR"},
    {"id": 50, "question": "In a merger situation, what is vital for HR?", "options": ["Resist change", "Communicate and assess culture", "Ignore differences", "Push new rules"], "correct_answer": "Communicate and assess culture", "category": "HR"},

    {"id": 51, "question": "How do you promote diversity at work?", "options": ["Ignore", "Implement inclusive practices", "Avoid minorities", "Focus on productivity only"], "correct_answer": "Implement inclusive practices", "category": "HR"},
    {"id": 52, "question": "What is your response to setbacks at work?", "options": ["Give up", "Blame others", "Re-assess and solve", "Ignore"], "correct_answer": "Re-assess and solve", "category": "HR"},
    {"id": 53, "question": "If a project deadline is missed, what should you do?", "options": ["Blame team", "Take responsibility", "Hide mistake", "Deny"], "correct_answer": "Take responsibility", "category": "HR"},
    {"id": 54, "question": "If a coworker is struggling, how do you help?", "options": ["Ignore", "Offer assistance", "Report to manager", "Avoid"], "correct_answer": "Offer assistance", "category": "HR"},
    {"id": 55, "question": "How do you handle feedback?", "options": ["Reject", "Ignore", "Accept and improve", "Dispute"], "correct_answer": "Accept and improve", "category": "HR"},
    {"id": 56, "question": "In stressful situations, how do you react?", "options": ["Panic", "Stay calm", "Complain", "Avoid work"], "correct_answer": "Stay calm", "category": "HR"},
    {"id": 57, "question": "If you need to learn a new skill for a project, what do you do?", "options": ["Refuse", "Research and learn", "Complain", "Ignore"], "correct_answer": "Research and learn", "category": "HR"},
    {"id": 58, "question": "What should you do if you make a mistake at work?", "options": ["Hide it", "Admit and correct", "Blame others", "Ignore"], "correct_answer": "Admit and correct", "category": "HR"},
    {"id": 59, "question": "How do you prepare for career growth?", "options": ["Wait for opportunities", "Seek feedback", "Avoid change", "Complain"], "correct_answer": "Seek feedback", "category": "HR"},
    {"id": 60, "question": "For communicating clearly, what's most important?", "options": ["Being vague", "Active listening", "Ignoring feedback", "Monologue"], "correct_answer": "Active listening", "category": "HR"},

    {"id": 61, "question": "Which data structure uses FIFO?", "options": ["Stack", "Queue", "Tree", "Graph"], "correct_answer": "Queue", "category": "Technical"},
    {"id": 62, "question": "What is the extension of a Python file?", "options": [".pyt", ".py", ".pt", ".python"], "correct_answer": ".py", "category": "Technical"},
    {"id": 63, "question": "What does HTML stand for?", "options": ["Hyper Trainer Marking Language", "Hyper Text Markup Language", "Hyper Text Marketing Language", "Hyperlink Text Markup Language"], "correct_answer": "Hyper Text Markup Language", "category": "Technical"},
    {"id": 64, "question": "Which planet is known as the Red Planet?", "options": ["Earth", "Mars", "Jupiter", "Venus"], "correct_answer": "Mars", "category": "Aptitude"},
    {"id": 65, "question": "Which number is a perfect square: 16, 18, 20, 22?", "options": ["16", "18", "20", "22"], "correct_answer": "16", "category": "Aptitude"},
    {"id": 66, "question": "If an item costs ₹150 and is sold for ₹200, what is the profit percent?", "options": ["25%", "30%", "33%", "40%"], "correct_answer": "33%", "category": "Aptitude"},
    {"id": 67, "question": "The probability of getting heads in a coin toss is?", "options": ["1/2", "1/3", "1/4", "1"], "correct_answer": "1/2", "category": "Aptitude"},
    {"id": 68, "question": "Which function finds minimum value in Excel?", "options": ["MIN()", "MAX()", "AVERAGE()", "COUNT()"], "correct_answer": "MIN()", "category": "Technical"},
    {"id": 69, "question": "Which SQL keyword sorts the result?", "options": ["SORT", "ORDER BY", "GROUP BY", "SELECT"], "correct_answer": "ORDER BY", "category": "Technical"},
    {"id": 70, "question": "A triangle with sides 3, 4, 5 is called?", "options": ["Equilateral", "Isosceles", "Right-angled", "Obtuse"], "correct_answer": "Right-angled", "category": "Aptitude"},
    
    {"id": 71, "question": "If 5x = 20, then x=?", "options": ["2", "3", "4", "5"], "correct_answer": "4", "category": "Aptitude"},
    {"id": 72, "question": "In Java, which keyword is used to create an object?", "options": ["object", "class", "new", "create"], "correct_answer": "new", "category": "Technical"},
    {"id": 73, "question": "What does RAM stand for?", "options": ["Random Access Memory", "Rarely Accessed Memory", "Read And Modify", "Read Access Module"], "correct_answer": "Random Access Memory", "category": "Technical"},
    {"id": 74, "question": "Which symbol is used for comments in Python?", "options": ["//", "#", "<!--", ";"], "correct_answer": "#", "category": "Technical"},
    {"id": 75, "question": "If a bike travels 18 km in 45 minutes, speed is?", "options": ["24 km/h", "36 km/h", "18 km/h", "30 km/h"], "correct_answer": "24 km/h", "category": "Aptitude"},
    {"id": 76, "question": "Which gas do plants absorb from air?", "options": ["Carbon dioxide", "Oxygen", "Nitrogen", "Hydrogen"], "correct_answer": "Carbon dioxide", "category": "Aptitude"},
    {"id": 77, "question": "A leap year has how many days?", "options": ["364", "365", "366", "367"], "correct_answer": "366", "category": "Aptitude"},
    {"id": 78, "question": "Which keyword is used to define a function in Python?", "options": ["function", "def", "fun", "define"], "correct_answer": "def", "category": "Technical"},
    {"id": 79, "question": "Which data structure is used in BFS traversal?", "options": ["Stack", "Queue", "Tree", "Graph"], "correct_answer": "Queue", "category": "Technical"},
    {"id": 80, "question": "What is the cube root of 64?", "options": ["2", "4", "6", "8"], "correct_answer": "4", "category": "Aptitude"},
    
    {"id": 81, "question": "Which is a binary number: 101, 256, 1A2, 999?", "options": ["101", "256", "1A2", "999"], "correct_answer": "101", "category": "Technical"},
    {"id": 82, "question": "What is the value of π (pi) up to two decimal places?", "options": ["3.12", "3.14", "3.16", "3.18"], "correct_answer": "3.14", "category": "Aptitude"},
    {"id": 83, "question": "Which HTML tag is used for a hyperlink?", "options": ["<link>", "<a>", "<href>", "<hyper>"], "correct_answer": "<a>", "category": "Technical"},
    {"id": 84, "question": "Which is not an example of an operating system: Linux, Windows, Oracle, MacOS?", "options": ["Linux", "Windows", "Oracle", "MacOS"], "correct_answer": "Oracle", "category": "Technical"},
    {"id": 85, "question": "What is the boiling point of water?", "options": ["80°C", "90°C", "100°C", "120°C"], "correct_answer": "100°C", "category": "Aptitude"},
    {"id": 86, "question": "Which is the largest organ in the human body?", "options": ["Heart", "Liver", "Skin", "Brain"], "correct_answer": "Skin", "category": "Aptitude"},
    {"id": 87, "question": "In a meeting, someone interrupts you frequently. What do you do?", "options": ["Ignore and continue", "Confront angrily", "Request to speak after", "Leave the meeting"], "correct_answer": "Request to speak after", "category": "HR"},
    {"id": 88, "question": "If a team misses a project deadline, you should?", "options": ["Blame team", "Find root cause", "Ignore", "Punish team"], "correct_answer": "Find root cause", "category": "HR"},
    {"id": 89, "question": "Which color is created by mixing red and white?", "options": ["Pink", "Orange", "Purple", "Brown"], "correct_answer": "Pink", "category": "Aptitude"},
    {"id": 90, "question": "Which Indian festival is known as the festival of lights?", "options": ["Holi", "Diwali", "Eid", "Christmas"], "correct_answer": "Diwali", "category": "Aptitude"},
    
    {"id": 91, "question": "If a supervisor gives you unclear instructions, you should?", "options": ["Assume and proceed", "Seek clarification", "Complain to HR", "Ignore task"], "correct_answer": "Seek clarification", "category": "HR"},
    {"id": 92, "question": "You receive critical feedback. What will you do?", "options": ["Ignore", "Get defensive", "Evaluate and improve", "Retaliate"], "correct_answer": "Evaluate and improve", "category": "HR"},
    {"id": 93, "question": "Which shape has 5 sides?", "options": ["Triangle", "Square", "Pentagon", "Hexagon"], "correct_answer": "Pentagon", "category": "Aptitude"},
    {"id": 94, "question": "Which programming language is known for web development?", "options": ["Python", "Java", "JavaScript", "C++"], "correct_answer": "JavaScript", "category": "Technical"},
    {"id": 95, "question": "How many degrees in a right angle?", "options": ["45", "60", "90", "180"], "correct_answer": "90", "category": "Aptitude"},
    {"id": 96, "question": "What should you do if your team faces a conflict?", "options": ["Avoid it", "Mediate and resolve", "Ignore issue", "Take sides"], "correct_answer": "Mediate and resolve", "category": "HR"},
    {"id": 97, "question": "How many continents are there in the world?", "options": ["5", "6", "7", "8"], "correct_answer": "7", "category": "Aptitude"},
    {"id": 98, "question": "What does URL stand for?", "options": ["Uniform Resource Locator", "Unified Reference Link", "Universal Refresh Link", "Useful Resource Locator"], "correct_answer": "Uniform Resource Locator", "category": "Technical"},
    {"id": 99, "question": "If rainfall in June was 120 mm and in July 150 mm, what is the increase?", "options": ["30 mm", "40 mm", "50 mm", "60 mm"], "correct_answer": "30 mm", "category": "Aptitude"},
    {"id": 100, "question": "Which HR practice fosters open communication?", "options": ["Encouraging silence", "Open-door policy", "Centralised decision", "Rigid hierarchy"], "correct_answer": "Open-door policy", "category": "HR"}
]

@app.post("/api/auth/register", status_code=201)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        existing_user = await get_user_by_username(db, user.username)
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")

        result = await db.execute(select(UserModel).where(UserModel.email == user.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = get_password_hash(user.password)
        new_user = UserModel(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            hashed_password=hashed_password,
            disabled=False,
        )
        db.add(new_user)
        await db.flush()
        
        # init progress
        progress = UserProgressModel(user_id=new_user.id, resume_completed=False)
        db.add(progress)
        await db.commit()

        # Send welcome email (non-blocking)
        send_welcome_email(new_user.email, new_user.full_name or new_user.username)

        return {"message": "User registered successfully", "user_id": new_user.id}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback
        error_detail = f"{str(e)}: {traceback.format_exc()}"
        raise HTTPException(status_code=400, detail=error_detail)


@app.post("/api/auth/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/auth/me", response_model=User)
async def read_users_me(current_user: UserModel = Depends(get_current_active_user)):
    return current_user


@app.get("/api/user/resumes")
async def get_user_resumes(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a list of resumes belonging to the authenticated user"""
    try:
        result = await db.execute(
            select(ResumeModel).where(ResumeModel.owner_id == current_user.id)
        )
        resumes = result.scalars().all()
        # return minimal info for the summary component
        return [
            {
                "id": r.id,
                "name": r.name,
                "email": r.email,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in resumes
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching resumes: {str(e)}")


@app.post("/api/auth/logout")
async def logout(current_user: UserModel = Depends(get_current_active_user)):
    return {"message": "Successfully logged out"}


@app.get("/api/user/preview-progress-email")
async def preview_progress_email_endpoint(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview what the progress email would look like"""
    try:
        # Get user's progress
        progress_result = await db.execute(
            select(UserProgressModel).where(UserProgressModel.user_id == current_user.id)
        )
        progress = progress_result.scalar_one_or_none()
        
        # Get user's resumes
        resumes_result = await db.execute(
            select(ResumeModel).where(ResumeModel.owner_id == current_user.id)
        )
        resumes = resumes_result.scalars().all()
        
        # Format resume data
        resumes_data = [
            {
                "name": resume.name or "Untitled Resume",
                "email": resume.email or "N/A",
                "created_at": resume.created_at.strftime("%B %d, %Y") if resume.created_at else "N/A",
            }
            for resume in resumes
        ]
        
        # Import to get the HTML content function
        from email_service import create_progress_email_html
        
        # Generate HTML content
        html_content = create_progress_email_html(
            user_name=current_user.full_name or current_user.username,
            resumes_count=len(resumes),
            interviews_taken=progress.interviews_taken if progress else 0,
            practice_score=progress.practice_score if progress else 0.0,
            resumes=resumes_data,
        )
        
        return {
            "preview": True,
            "recipient_email": current_user.email,
            "subject": f"📊 Your CareerPrep Hub Progress Update - {current_user.full_name or current_user.username}!",
            "html_content": html_content,
            "metadata": {
                "resumes_count": len(resumes),
                "interviews_taken": progress.interviews_taken if progress else 0,
                "practice_score": progress.practice_score if progress else 0.0,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating preview: {str(e)}")


@app.post("/api/user/send-progress-email")
async def send_progress_email_endpoint(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Send user's progress summary and resumes to their email"""
    try:
        # Get user's progress
        progress_result = await db.execute(
            select(UserProgressModel).where(UserProgressModel.user_id == current_user.id)
        )
        progress = progress_result.scalar_one_or_none()
        
        # Get user's resumes
        resumes_result = await db.execute(
            select(ResumeModel).where(ResumeModel.owner_id == current_user.id)
        )
        resumes = resumes_result.scalars().all()
        
        # Format resume data
        resumes_data = [
            {
                "name": resume.name or "Untitled Resume",
                "email": resume.email or "N/A",
                "created_at": resume.created_at.strftime("%B %d, %Y") if resume.created_at else "N/A",
            }
            for resume in resumes
        ]

        # make it clear when email config is missing
        import email_service
        if not email_service.SENDER_PASSWORD:
            raise HTTPException(
                status_code=400,
                detail="Email service is not configured. Please set SMTP credentials in environment.",
            )
        
        # Send email
        success = send_progress_email(
            recipient_email=current_user.email,
            user_name=current_user.full_name or current_user.username,
            resumes_count=len(resumes),
            interviews_taken=progress.interviews_taken if progress else 0,
            practice_score=progress.practice_score if progress else 0.0,
            resumes=resumes_data,
        )
        
        if success:
            # Create notification for admin
            try:
                notification = AdminNotificationModel(
                    user_id=current_user.id,
                    notification_type="progress_email_sent",
                    message=f"User {current_user.username} sent their progress email. Resumes: {len(resumes)}, Interviews: {progress.interviews_taken if progress else 0}, Practice Score: {progress.practice_score if progress else 0.0}%",
                    username=current_user.username,
                    user_email=current_user.email
                )
                db.add(notification)
                await db.commit()
            except Exception as notification_error:
                # Log but don't fail the email send if notification fails
                print(f"Failed to create admin notification: {str(notification_error)}")
            
            return {
                "message": "Progress email sent successfully",
                "email": current_user.email,
                "resumes_count": len(resumes),
                "interviews_taken": progress.interviews_taken if progress else 0,
                "practice_score": progress.practice_score if progress else 0.0,
            }
        else:
            # service returned false even though credentials were present
            raise HTTPException(
                status_code=500,
                detail="Failed to send email. Please check your SMTP configuration and logs.",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending email: {str(e)}")



# https://github.com/Sanket-2736/CareerPrepHub/blob/main/backend/app.py
@app.get("/api/resume/{resume_id}")
async def get_resume(
    resume_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ResumeModel).where(ResumeModel.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Helper function to safely parse JSON or return empty list
    def safe_json_parse(json_str):
        if not json_str:
            return []
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return [json_str] if json_str else []
    
    return {
        "resume": {
            "id": resume.id,
            "name": resume.name,
            "email": resume.email,
            "phone": resume.phone,
            "address": resume.address,
            "linkedin": resume.linkedin,
            "github": resume.github,
            "portfolio": resume.portfolio,
            "education": safe_json_parse(resume.education),
            "experience": safe_json_parse(resume.experience),
            "projects": safe_json_parse(resume.projects),
            "skills": resume.skills.split(",") if resume.skills else [],
            "summary": resume.summary,
            "certifications": safe_json_parse(resume.certifications),
            "awards": safe_json_parse(resume.awards),
            "publications": safe_json_parse(resume.publications),
            "languages": safe_json_parse(resume.languages),
            "interests": safe_json_parse(resume.interests),
        }
    }

@app.post("/api/resume/build")
async def build_resume(
    resume: Resume,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    new_resume = ResumeModel(
        name=resume.name,
        email=resume.email,
        phone=resume.phone,
        address=resume.address,
        linkedin=resume.linkedin,
        github=resume.github,
        portfolio=resume.portfolio,
        # Convert arrays to JSON strings for database storage
        education=json.dumps(resume.education),
        experience=json.dumps(resume.experience),
        projects=json.dumps(resume.projects) if resume.projects else None,
        certifications=json.dumps(resume.certifications) if resume.certifications else None,
        skills=",".join(resume.skills),
        summary=resume.summary,
        awards=json.dumps(resume.awards) if resume.awards else None,
        publications=json.dumps(resume.publications) if resume.publications else None,
        languages=json.dumps(resume.languages) if resume.languages else None,
        interests=json.dumps(resume.interests) if resume.interests else None,
        owner_id=current_user.id,
    )
    db.add(new_resume)
    await db.commit()
    await db.refresh(new_resume)

    # update progress
    result = await db.execute(
        select(UserProgressModel).where(UserProgressModel.user_id == current_user.id)
    )
    progress = result.scalar_one_or_none()
    if not progress:
        progress = UserProgressModel(user_id=current_user.id, resume_completed=True)
        db.add(progress)
    else:
        progress.resume_completed = True
    await db.commit()

    return {
        "message": "Resume created successfully",
        "resume_id": new_resume.id,
        "resume": resume.dict(),
    }

# ---------------- INTERVIEW ENDPOINTS ----------------

@app.get("/api/interview/questions")
async def get_interview_questions():
    """
    Returns a random set of 5 interview questions.
    """
    selected = random.sample(INTERVIEW_QUESTIONS, 5)
    return {"questions": selected}


class InterviewAnswerRequest(BaseModel):
    question: str
    answer: str
    user_id: Optional[str] = None


@app.post("/api/interview/answer")
async def evaluate_answer(payload: InterviewAnswerRequest):
    """
    Evaluate interview answer using Gemini.
    Expected output format: "score, feedback"
    Example: "8, Good answer with clear examples"
    """
    prompt = f"""
    You are an interview evaluator.
    Question: {payload.question}
    Candidate Answer: {payload.answer}

    Give a score from 0 to 10 (higher is better) and short feedback.
    Respond strictly in the format:
    score, feedback
    """

    try:
        response_text = run(prompt)
        print("🔍 Gemini raw response:", response_text)

        # Parse "score, feedback"
        parts = response_text.strip().split(",", 1)
        score = int(parts[0].strip()) if parts and parts[0].strip().isdigit() else 5
        feedback = parts[1].strip() if len(parts) > 1 else "No feedback provided."

        return {
            "score": score,
            "feedback": feedback,
            "suggestions": ["Work on providing more structured answers.", "Give specific examples."]
        }

    except Exception as e:
        print("❌ Error in Gemini evaluation:", str(e))
        import traceback
        traceback.print_exc()
        return {
            "score": 5,
            "feedback": "Error evaluating answer, please try again.",
            "suggestions": []
        }

@app.get("/api/practice/questions")
async def get_practice_questions():
    return {"questions": random.sample(PRACTICE_QUESTIONS, 20)}


@app.post("/api/chatbot/message")
async def chatbot_message(
    payload: ChatbotRequest,
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Handle chatbot messages for career help using Gemini AI.
    Requires authentication.
    """
    try:
        # Build conversation context
        context = """
        You are CareerBot, an AI career assistant for CareerPrepHub. You help users with:
        - Resume building and optimization
        - Job search strategies
        - Interview preparation
        - Career planning and development
        - Skill development recommendations
        - Industry insights and trends

        Be helpful, professional, and encouraging. Provide specific, actionable advice.
        Keep responses concise but informative.
        """

        # Include conversation history if provided
        conversation_text = ""
        if payload.conversation_history:
            for msg in payload.conversation_history[-5:]:  # Last 5 messages for context
                role = "User" if msg.get("role") == "user" else "Assistant"
                conversation_text += f"{role}: {msg.get('content', '')}\n"

        prompt = f"""{context}

        Previous conversation:
        {conversation_text}

        User: {payload.message}

        Respond as CareerBot with helpful career advice:"""

        response_text = run(prompt)

        return {
            "response": response_text,
            "timestamp": datetime.utcnow().isoformat(),
            "bot_name": "CareerBot"
        }

    except Exception as e:
        print("❌ Error in chatbot:", str(e))
        import traceback
        traceback.print_exc()
        return {
            "response": "I'm sorry, I'm having trouble processing your request right now. Please try again later.",
            "timestamp": datetime.utcnow().isoformat(),
            "bot_name": "CareerBot",
            "error": True
        }


class SubmitRequest(BaseModel):
    answers: List[PracticeAnswer]


@app.get("/api/practice/questions")
async def get_practice_questions():
    return {"questions": random.sample(PRACTICE_QUESTIONS, 20)}


@app.post("/api/practice/submit")
async def submit_answers(payload: SubmitRequest):
    score = 0
    results = []

    for ans in payload.answers:
        q = next((q for q in PRACTICE_QUESTIONS if q["id"] == ans.question_id), None)
        if not q:
            continue
        is_correct = ans.selected_option == q["correct_answer"]
        if is_correct:
            score += 1
        results.append({
            "question_id": q["id"],
            "question": q["question"],
            "selected": ans.selected_option,
            "correct_answer": q["correct_answer"],
            "is_correct": is_correct
        })

    total = len(payload.answers)
    percentage = (score / total * 100) if total > 0 else 0

    return {
        "score": score,
        "total": total,
        "percentage": round(percentage, 2),
        "results": results
    }

import json

@app.get("/api/resume/{resume_id}")
async def get_resume(
    resume_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ResumeModel).where(ResumeModel.id == resume_id))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if resume.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Helper function to safely parse JSON or return empty list
    def safe_json_parse(json_str):
        if not json_str:
            return []
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return [json_str] if json_str else []
    
    return {
        "resume": {
            "id": resume.id,
            "name": resume.name,
            "email": resume.email,
            "phone": resume.phone,
            "address": resume.address,
            "linkedin": resume.linkedin,
            "github": resume.github,
            "portfolio": resume.portfolio,
            "education": safe_json_parse(resume.education),
            "experience": safe_json_parse(resume.experience),
            "projects": safe_json_parse(resume.projects),
            "skills": resume.skills.split(",") if resume.skills else [],
            "summary": resume.summary,
            "certifications": safe_json_parse(resume.certifications),
            "awards": safe_json_parse(resume.awards),
            "publications": safe_json_parse(resume.publications),
            "languages": safe_json_parse(resume.languages),
            "interests": safe_json_parse(resume.interests),
        }
    }


@app.get("/api/resume/user/list")
async def get_user_resumes(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ResumeModel).where(ResumeModel.owner_id == current_user.id))
    resumes = result.scalars().all()
    return {
        "resumes": [
            {
                "id": r.id,
                "resume": {
                    "name": r.name,
                    "email": r.email,
                    "phone": r.phone,
                    "education": r.education,
                    "experience": r.experience,
                    "skills": r.skills.split(",") if r.skills else [],
                    "summary": r.summary,
                },
            }
            for r in resumes
        ]
    }


# Dashboard
@app.get("/api/dashboard/progress")
async def get_user_progress(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserProgressModel).where(UserProgressModel.user_id == current_user.id)
    )
    progress = result.scalar_one_or_none()
    if not progress:
        return {"progress": {"resume_completed": False, "interviews_taken": 0, "practice_score": 0}}
    return {
        "progress": {
            "resume_completed": progress.resume_completed,
            "interviews_taken": progress.interviews_taken,
            "practice_score": progress.practice_score,
        }
    }


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    total_resumes = (await db.execute(select(ResumeModel))).scalars().all()
    total_users = (await db.execute(select(UserModel))).scalars().all()
    total_progress = (await db.execute(select(UserProgressModel))).scalars().all()

    avg_practice_score = (
        sum(p.practice_score for p in total_progress) / max(1, len(total_users))
    )

    return {
        "total_resumes": len(total_resumes),
        "total_users": len(total_users),
        "avg_practice_score": round(avg_practice_score, 2),
    }


# Admin Endpoints
@app.get("/api/admin/stats")
async def get_admin_stats(
    current_user: UserModel = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get platform statistics for admin dashboard"""
    try:
        total_users_result = await db.execute(select(UserModel))
        total_users = len(total_users_result.scalars().all())
        
        total_resumes_result = await db.execute(select(ResumeModel))
        total_resumes = len(total_resumes_result.scalars().all())
        
        total_progress_result = await db.execute(select(UserProgressModel))
        all_progress = total_progress_result.scalars().all()
        
        # Calculate active users (those with interviews taken in recent activity)
        active_users = sum(1 for p in all_progress if p.interviews_taken > 0)
        
        # Calculate average practice score
        avg_practice_score = (
            sum(p.practice_score for p in all_progress) / max(1, total_users)
        ) if all_progress else 0
        
        # Calculate new users this week (we'll estimate based on total)
        new_users_week = max(0, total_users // 4)  # Estimate
        
        return {
            "total_users": total_users,
            "active_users_week": active_users,
            "total_resumes": total_resumes,
            "total_interviews": sum(p.interviews_taken for p in all_progress),
            "avg_practice_score": round(avg_practice_score, 2),
            "new_users_week": new_users_week,
            "last_activity": "Active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


@app.get("/api/admin/users")
async def get_all_users(
    current_user: UserModel = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of all users with their details"""
    try:
        result = await db.execute(select(UserModel))
        users = result.scalars().all()
        
        users_list = [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name or "N/A",
                "disabled": user.disabled,
                "is_admin": user.is_admin,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ]
        
        return users_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")


@app.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user by ID"""
    try:
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
        
        result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        user_to_delete = result.scalar_one_or_none()
        
        if not user_to_delete:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete associated resumes
        resume_result = await db.execute(
            select(ResumeModel).where(ResumeModel.owner_id == user_id)
        )
        resumes = resume_result.scalars().all()
        for resume in resumes:
            await db.delete(resume)
        
        # Delete associated progress
        progress_result = await db.execute(
            select(UserProgressModel).where(UserProgressModel.user_id == user_id)
        )
        progress = progress_result.scalar_one_or_none()
        if progress:
            await db.delete(progress)
        
        # Delete user
        await db.delete(user_to_delete)
        await db.commit()
        
        return {"message": f"User {user_id} deleted successfully"}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")


@app.get("/api/admin/resumes")
async def get_all_resumes(
    current_user: UserModel = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of all resumes with their details"""
    try:
        result = await db.execute(select(ResumeModel))
        resumes = result.scalars().all()
        
        # Get user information for each resume
        resumes_list = []
        for resume in resumes:
            user_result = await db.execute(
                select(UserModel).where(UserModel.id == resume.owner_id)
            )
            user = user_result.scalar_one_or_none()
            
            resumes_list.append({
                "id": resume.id,
                "name": resume.name,
                "email": resume.email,
                "user_id": resume.owner_id,
                "username": user.username if user else "N/A",
                "created_at": resume.created_at.isoformat() if resume.created_at else None,
            })
        
        return resumes_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching resumes: {str(e)}")


@app.get("/api/resume/{resume_id}/download")
async def download_resume(
    resume_id: int,
    format: str = Query("pdf", regex="^(pdf|docx)$"),
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Download resume in PDF or DOCX format"""
    try:
        # Get the resume
        result = await db.execute(select(ResumeModel).where(ResumeModel.id == resume_id))
        resume = result.scalar_one_or_none()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Check ownership
        if resume.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Helper function to safely parse JSON
        def safe_json_parse(json_str):
            if not json_str:
                return []
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, TypeError):
                return [json_str] if json_str else []
        
        # Prepare resume data for export
        resume_data = {
            "name": resume.name,
            "email": resume.email,
            "phone": resume.phone,
            "address": resume.address,
            "linkedin": resume.linkedin,
            "github": resume.github,
            "portfolio": resume.portfolio,
            "summary": resume.summary,
            "education": safe_json_parse(resume.education),
            "experience": safe_json_parse(resume.experience),
            "projects": safe_json_parse(resume.projects),
            "skills": resume.skills.split(",") if resume.skills else [],
            "certifications": safe_json_parse(resume.certifications),
            "awards": safe_json_parse(resume.awards),
            "publications": safe_json_parse(resume.publications),
            "languages": safe_json_parse(resume.languages),
            "interests": safe_json_parse(resume.interests),
        }
        
        # Generate the file based on format
        if format.lower() == "pdf":
            file_bytes = generate_resume_pdf(resume_data)
            media_type = "application/pdf"
            filename = f"{resume.name.replace(' ', '_')}.pdf"
        else:  # docx
            file_bytes = generate_resume_docx(resume_data)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"{resume.name.replace(' ', '_')}.docx"
        
        # Return file response with proper headers
        return StreamingResponse(
            iter([file_bytes.getvalue()]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating resume: {str(e)}")


@app.get("/api/admin/resume/{resume_id}/download")
async def admin_download_resume(
    resume_id: int,
    format: str = Query("pdf", regex="^(pdf|docx)$"),
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: Download any resume in PDF or DOCX format"""
    try:
        # Check if user is admin
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get the resume
        result = await db.execute(select(ResumeModel).where(ResumeModel.id == resume_id))
        resume = result.scalar_one_or_none()
        
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # Helper function to safely parse JSON
        def safe_json_parse(json_str):
            if not json_str:
                return []
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, TypeError):
                return [json_str] if json_str else []
        
        # Prepare resume data for export
        resume_data = {
            "name": resume.name,
            "email": resume.email,
            "phone": resume.phone,
            "address": resume.address,
            "linkedin": resume.linkedin,
            "github": resume.github,
            "portfolio": resume.portfolio,
            "summary": resume.summary,
            "education": safe_json_parse(resume.education),
            "experience": safe_json_parse(resume.experience),
            "projects": safe_json_parse(resume.projects),
            "skills": resume.skills.split(",") if resume.skills else [],
            "certifications": safe_json_parse(resume.certifications),
            "awards": safe_json_parse(resume.awards),
            "publications": safe_json_parse(resume.publications),
            "languages": safe_json_parse(resume.languages),
            "interests": safe_json_parse(resume.interests),
        }
        
        # Generate the file based on format
        if format.lower() == "pdf":
            file_bytes = generate_resume_pdf(resume_data)
            media_type = "application/pdf"
            filename = f"{resume.name.replace(' ', '_')}.pdf"
        else:  # docx
            file_bytes = generate_resume_docx(resume_data)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"{resume.name.replace(' ', '_')}.docx"
        
        # Return file response with proper headers
        return StreamingResponse(
            iter([file_bytes.getvalue()]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating resume: {str(e)}")


# ==================== ADMIN NOTIFICATIONS ENDPOINTS ====================

@app.get("/api/admin/notifications")
async def get_admin_notifications(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all admin notifications (unread first, then sorted by date)"""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can view notifications")
    
    try:
        # Get all notifications sorted by unread first, then by created_at descending
        result = await db.execute(
            select(AdminNotificationModel)
            .order_by(AdminNotificationModel.is_read, AdminNotificationModel.created_at.desc())
        )
        notifications = result.scalars().all()
        
        # Count unread notifications
        unread_result = await db.execute(
            select(func.count(AdminNotificationModel.id)).where(AdminNotificationModel.is_read == False)
        )
        unread_count = unread_result.scalar() or 0
        
        return {
            "notifications": [
                {
                    "id": n.id,
                    "user_id": n.user_id,
                    "notification_type": n.notification_type,
                    "message": n.message,
                    "username": n.username,
                    "user_email": n.user_email,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in notifications
            ],
            "unread_count": unread_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {str(e)}")


@app.put("/api/admin/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read"""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can manage notifications")
    
    try:
        # Get the notification
        result = await db.execute(
            select(AdminNotificationModel).where(AdminNotificationModel.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Update is_read flag
        notification.is_read = True
        await db.commit()
        
        return {
            "message": "Notification marked as read",
            "id": notification.id,
            "is_read": notification.is_read
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating notification: {str(e)}")


@app.delete("/api/admin/notifications/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification"""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can delete notifications")
    
    try:
        # Get the notification
        result = await db.execute(
            select(AdminNotificationModel).where(AdminNotificationModel.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Delete the notification
        await db.delete(notification)
        await db.commit()
        
        return {"message": "Notification deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting notification: {str(e)}")


# environment variables for job search
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")


@app.get("/api/jobs/search")
async def search_jobs(
    q: str,
    current_user: UserModel = Depends(get_current_active_user),
):
    """Perform a job search using Google's Custom Search JSON API.

    Requires GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables.  If not
    configured, the endpoint will return a 500 error.
    """
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        raise HTTPException(
            status_code=500,
            detail="Job search not configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID."
        )
    try:
        # log query for troubleshooting
        logger.info(f"Job search query: {q}")
        encoded = urllib.parse.quote_plus(q)
        url = (
            f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}"
            f"&cx={GOOGLE_CSE_ID}&q={encoded}"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            logger.error(f"Google API returned status {resp.status_code}")
            raise HTTPException(status_code=resp.status_code, detail="Google API error")
        data = resp.json()
        items = data.get("items", [])
        jobs = []
        for item in items:
            jobs.append({
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "link": item.get("link"),
            })
        logger.info(f"Job search returned {len(jobs)} items")
        return {"jobs": jobs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job search failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
