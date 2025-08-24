from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'vitacoin_rewards')]

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer()

# Create the main app
app = FastAPI(title="Vitacoin Rewards Platform")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(json.dumps(message))
            except:
                self.disconnect(user_id)
    
    async def broadcast_leaderboard(self, leaderboard: list):
        message = {"type": "leaderboard_update", "data": leaderboard}
        disconnected = []
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_text(json.dumps(message))
            except:
                disconnected.append(user_id)
        
        for user_id in disconnected:
            self.disconnect(user_id)

manager = ConnectionManager()

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: EmailStr
    password_hash: str = ""
    role: str = "user"  # "user" or "admin"
    coins: int = 0
    badges: List[str] = []
    last_daily_reward: Optional[datetime] = None
    completed_tasks: List[str] = []  # List of completed task IDs
    task_progress: Dict[str, Dict[str, Any]] = {}  # Track task progress
    activity_log: List[Dict[str, Any]] = []  # Track user activities
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    coins: int
    badges: List[str]
    last_daily_reward: Optional[datetime]
    completed_tasks: List[str]
    task_progress: Dict[str, Dict[str, Any]]
    created_at: datetime

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    category: str  # "daily", "weekly", "achievement", "special"
    coins_reward: int
    difficulty: str = "easy"  # "easy", "medium", "hard"
    requirements: Dict[str, Any] = {}  # Task requirements and activities
    active: bool = True
    max_completions: Optional[int] = None  # None for unlimited
    completion_count: int = 0
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TaskWithProgress(BaseModel):
    id: str
    title: str
    description: str
    category: str
    coins_reward: int
    difficulty: str
    requirements: Dict[str, Any]
    active: bool
    max_completions: Optional[int]
    completion_count: int
    expires_at: Optional[datetime]
    created_at: datetime
    progress: Dict[str, Any] = {}  # User's progress on this task
    can_claim: bool = False  # Whether user can claim this task
    is_completed: bool = False  # Whether user has completed this task

class TaskCreate(BaseModel):
    title: str
    description: str
    category: str
    coins_reward: int
    difficulty: str = "easy"
    requirements: Dict[str, Any] = {}
    max_completions: Optional[int] = None
    expires_at: Optional[datetime] = None

class TaskCompletion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    task_id: str
    coins_earned: int
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RewardRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key: str
    description: str
    points: int
    penalty: bool = False
    active: bool = True
    cooldown_hours: Optional[int] = None
    daily_cap: Optional[int] = None
    per_user_cap: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Transaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    amount: int
    type: str  # "credit" or "debit"
    rule_key: str
    description: str
    task_id: Optional[str] = None  # Reference to task if applicable
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DailyRewardResponse(BaseModel):
    success: bool
    message: str
    coins_earned: Optional[int] = None
    new_balance: Optional[int] = None
    next_reward_in: Optional[int] = None  # hours

class TaskCompletionResponse(BaseModel):
    success: bool
    message: str
    coins_earned: Optional[int] = None
    new_balance: Optional[int] = None

class ActivityLogEntry(BaseModel):
    action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = {}

class LeaderboardEntry(BaseModel):
    id: str
    name: str
    coins: int
    rank: int

# Auth utilities
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_doc = await db.users.find_one({"id": user_id})
    if user_doc is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user_doc)

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Helper functions
async def log_user_activity(user_id: str, action: str, details: Dict[str, Any] = {}):
    """Log user activity for task progress tracking"""
    activity = ActivityLogEntry(action=action, details=details)
    await db.users.update_one(
        {"id": user_id},
        {"$push": {"activity_log": activity.dict()}}
    )

async def check_task_requirements(user: User, task: Task) -> Dict[str, Any]:
    """Check if user has met task requirements and return progress"""
    progress = user.task_progress.get(task.id, {})
    requirements = task.requirements
    can_claim = False
    
    # Check different types of requirements
    if task.title == "First Login":
        # Automatically completed on login
        can_claim = True
        progress = {"status": "completed", "description": "You've logged in! Ready to claim."}
    
    elif task.title == "Profile Explorer":
        # Check if user has viewed profile/transactions
        viewed_profile = any(
            activity.get("action") == "viewed_profile" 
            for activity in user.activity_log[-20:]  # Check recent activities
        )
        viewed_transactions = any(
            activity.get("action") == "viewed_transactions" 
            for activity in user.activity_log[-20:]
        )
        
        if viewed_profile and viewed_transactions:
            can_claim = True
            progress = {"status": "completed", "description": "You've explored your profile and transactions!"}
        else:
            needed = []
            if not viewed_profile:
                needed.append("View your profile")
            if not viewed_transactions:
                needed.append("Check your transaction history")
            progress = {
                "status": "in_progress", 
                "description": f"Complete these actions: {', '.join(needed)}",
                "viewed_profile": viewed_profile,
                "viewed_transactions": viewed_transactions
            }
    
    elif task.title == "Social Butterfly":
        # Check if user has viewed leaderboard
        viewed_leaderboard = any(
            activity.get("action") == "viewed_leaderboard" 
            for activity in user.activity_log[-20:]
        )
        
        if viewed_leaderboard:
            can_claim = True
            progress = {"status": "completed", "description": "You've checked out the competition!"}
        else:
            progress = {
                "status": "in_progress", 
                "description": "Visit the leaderboard to see other players"
            }
    
    elif task.title == "Community Member":
        # Welcome bonus - always claimable for new users
        can_claim = True
        progress = {"status": "completed", "description": "Welcome to Vitacoin! Claim your bonus."}
    
    elif task.title == "Coin Collector":
        # Check if user has 100+ coins
        if user.coins >= 100:
            can_claim = True
            progress = {"status": "completed", "description": f"You have {user.coins} coins! Achievement unlocked."}
        else:
            remaining = 100 - user.coins
            progress = {
                "status": "in_progress", 
                "description": f"Collect {remaining} more coins to unlock this achievement",
                "current_coins": user.coins,
                "target_coins": 100
            }
    
    elif task.title == "Task Master":
        # Check if user has completed 3 tasks today
        today = datetime.now(timezone.utc).date()
        completed_today = 0
        for activity in user.activity_log:
            if (activity.get("action") == "task_completed" and 
                datetime.fromisoformat(activity["timestamp"].replace("Z", "+00:00")).date() == today):
                completed_today += 1
        
        if completed_today >= 3:
            can_claim = True
            progress = {"status": "completed", "description": f"You've completed {completed_today} tasks today!"}
        else:
            progress = {
                "status": "in_progress", 
                "description": f"Complete {3 - completed_today} more tasks today ({completed_today}/3)",
                "completed_today": completed_today,
                "target": 3
            }
    
    else:
        # Default: task is claimable
        can_claim = True
        progress = {"status": "completed", "description": "Task ready to claim!"}
    
    return {"progress": progress, "can_claim": can_claim}

async def get_leaderboard(limit: int = 10) -> List[LeaderboardEntry]:
    pipeline = [
        {"$sort": {"coins": -1}},
        {"$limit": limit},
        {"$project": {"id": 1, "name": 1, "coins": 1}}
    ]
    
    results = await db.users.aggregate(pipeline).to_list(length=limit)
    leaderboard = []
    for i, user in enumerate(results):
        leaderboard.append(LeaderboardEntry(
            id=user["id"],
            name=user["name"],
            coins=user["coins"],
            rank=i + 1
        ))
    
    return leaderboard

async def broadcast_leaderboard_update():
    leaderboard = await get_leaderboard()
    await manager.broadcast_leaderboard([entry.dict() for entry in leaderboard])

# Routes
@api_router.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        name=user_data.name,
        email=user_data.email.lower(),
        password_hash=hash_password(user_data.password)
    )
    
    await db.users.insert_one(user.dict())
    
    # Log registration activity
    await log_user_activity(user.id, "user_registered", {"email": user.email})
    
    # Return user without password hash
    return UserResponse(**user.dict())

@api_router.post("/auth/login")
async def login(login_data: UserLogin):
    user_doc = await db.users.find_one({"email": login_data.email.lower()})
    if not user_doc or not verify_password(login_data.password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = User(**user_doc)
    access_token = create_access_token({"user_id": user.id})
    
    # Log login activity
    await log_user_activity(user.id, "user_login")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user.dict())
    }

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    # Log profile view activity
    await log_user_activity(current_user.id, "viewed_profile")
    return UserResponse(**current_user.dict())

@api_router.post("/rewards/daily", response_model=DailyRewardResponse)
async def claim_daily_reward(current_user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    
    # Check if user can claim daily reward
    if current_user.last_daily_reward:
        # Ensure timezone compatibility for datetime comparison
        last_reward = current_user.last_daily_reward
        if last_reward.tzinfo is None:
            # Convert naive datetime to UTC timezone-aware
            last_reward = last_reward.replace(tzinfo=timezone.utc)
        
        time_since_last = now - last_reward
        if time_since_last < timedelta(hours=24):
            hours_remaining = 24 - int(time_since_last.total_seconds() / 3600)
            return DailyRewardResponse(
                success=False,
                message=f"Daily reward already claimed. Next reward in {hours_remaining} hours.",
                next_reward_in=hours_remaining
            )
    
    # Get daily reward rule
    rule_doc = await db.reward_rules.find_one({"key": "daily_login", "active": True})
    if not rule_doc:
        raise HTTPException(status_code=404, detail="Daily reward rule not found")
    
    rule = RewardRule(**rule_doc)
    
    # Create transaction
    transaction = Transaction(
        user_id=current_user.id,
        amount=rule.points,
        type="credit",
        rule_key=rule.key,
        description=rule.description
    )
    
    # Update user coins and last reward time
    new_coins = current_user.coins + rule.points
    await db.users.update_one(
        {"id": current_user.id},
        {
            "$set": {
                "coins": new_coins,
                "last_daily_reward": now
            }
        }
    )
    
    # Save transaction
    await db.transactions.insert_one(transaction.dict())
    
    # Log activity
    await log_user_activity(current_user.id, "daily_reward_claimed", {"coins": rule.points})
    
    # Send real-time update
    await manager.send_personal_message({
        "type": "balance_update",
        "data": {
            "coins": new_coins,
            "delta": rule.points,
            "source": "Daily Reward"
        }
    }, current_user.id)
    
    # Update leaderboard
    await broadcast_leaderboard_update()
    
    return DailyRewardResponse(
        success=True,
        message=f"Daily reward claimed! +{rule.points} coins",
        coins_earned=rule.points,
        new_balance=new_coins
    )

# Task Management Routes
@api_router.get("/tasks", response_model=List[TaskWithProgress])
async def get_available_tasks(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get available tasks with user progress"""
    query = {"active": True}
    
    if category:
        query["category"] = category
    if difficulty:
        query["difficulty"] = difficulty
    
    # Filter out expired tasks
    now = datetime.now(timezone.utc)
    query["$or"] = [
        {"expires_at": None},
        {"expires_at": {"$gt": now}}
    ]
    
    tasks = await db.tasks.find(query).to_list(length=None)
    
    # Add progress and completion status for each task
    tasks_with_progress = []
    for task_doc in tasks:
        task = Task(**task_doc)
        
        # Skip completed tasks
        if task.id in current_user.completed_tasks:
            task_with_progress = TaskWithProgress(
                **task.dict(),
                progress={"status": "completed", "description": "Task already completed!"},
                can_claim=False,
                is_completed=True
            )
        else:
            # Check requirements and progress
            req_check = await check_task_requirements(current_user, task)
            task_with_progress = TaskWithProgress(
                **task.dict(),
                progress=req_check["progress"],
                can_claim=req_check["can_claim"],
                is_completed=False
            )
        
        tasks_with_progress.append(task_with_progress)
    
    return tasks_with_progress

@api_router.post("/tasks/{task_id}/claim", response_model=TaskCompletionResponse)
async def claim_task_reward(task_id: str, current_user: User = Depends(get_current_user)):
    """Claim reward for a completed task"""
    # Get the task
    task_doc = await db.tasks.find_one({"id": task_id, "active": True})
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found or inactive")
    
    task = Task(**task_doc)
    
    # Check if task is expired
    now = datetime.now(timezone.utc)
    if task.expires_at and task.expires_at < now:
        raise HTTPException(status_code=400, detail="Task has expired")
    
    # Check if user already completed this task
    if task_id in current_user.completed_tasks:
        raise HTTPException(status_code=400, detail="Task already completed")
    
    # Check if user can claim this task
    req_check = await check_task_requirements(current_user, task)
    if not req_check["can_claim"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Task requirements not met: {req_check['progress'].get('description', 'Requirements not fulfilled')}"
        )
    
    # Check max completions
    if task.max_completions and task.completion_count >= task.max_completions:
        raise HTTPException(status_code=400, detail="Task completion limit reached")
    
    # Create task completion record
    completion = TaskCompletion(
        user_id=current_user.id,
        task_id=task_id,
        coins_earned=task.coins_reward
    )
    
    # Create transaction
    transaction = Transaction(
        user_id=current_user.id,
        amount=task.coins_reward,
        type="credit",
        rule_key=f"task_{task.category}",
        description=f"Task completed: {task.title}",
        task_id=task_id
    )
    
    # Update user coins and completed tasks
    new_coins = current_user.coins + task.coins_reward
    completed_tasks = current_user.completed_tasks + [task_id]
    
    await db.users.update_one(
        {"id": current_user.id},
        {
            "$set": {
                "coins": new_coins,
                "completed_tasks": completed_tasks
            }
        }
    )
    
    # Update task completion count
    await db.tasks.update_one(
        {"id": task_id},
        {"$inc": {"completion_count": 1}}
    )
    
    # Save completion and transaction records
    await db.task_completions.insert_one(completion.dict())
    await db.transactions.insert_one(transaction.dict())
    
    # Log activity
    await log_user_activity(current_user.id, "task_completed", {
        "task_id": task_id,
        "task_title": task.title,
        "coins_earned": task.coins_reward
    })
    
    # Send real-time update
    await manager.send_personal_message({
        "type": "balance_update",
        "data": {
            "coins": new_coins,
            "delta": task.coins_reward,
            "source": f"Task: {task.title}"
        }
    }, current_user.id)
    
    await manager.send_personal_message({
        "type": "task_completed",
        "data": {
            "task_id": task_id,
            "task_title": task.title,
            "coins_earned": task.coins_reward
        }
    }, current_user.id)
    
    # Update leaderboard
    await broadcast_leaderboard_update()
    
    return TaskCompletionResponse(
        success=True,
        message=f"Task '{task.title}' completed! +{task.coins_reward} coins",
        coins_earned=task.coins_reward,
        new_balance=new_coins
    )

# Activity tracking endpoints
@api_router.post("/activities/view-transactions")
async def track_view_transactions(current_user: User = Depends(get_current_user)):
    """Track when user views transaction history"""
    await log_user_activity(current_user.id, "viewed_transactions")
    return {"success": True, "message": "Activity tracked"}

@api_router.post("/activities/view-leaderboard")
async def track_view_leaderboard(current_user: User = Depends(get_current_user)):
    """Track when user views leaderboard"""
    await log_user_activity(current_user.id, "viewed_leaderboard")
    return {"success": True, "message": "Activity tracked"}

@api_router.get("/tasks/completed", response_model=List[TaskCompletion])
async def get_completed_tasks(current_user: User = Depends(get_current_user)):
    """Get user's completed tasks"""
    completions = await db.task_completions.find(
        {"user_id": current_user.id}
    ).sort("completed_at", -1).to_list(length=None)
    
    return [TaskCompletion(**completion) for completion in completions]

@api_router.get("/transactions", response_model=List[Transaction])
async def get_user_transactions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    # Track activity
    await log_user_activity(current_user.id, "viewed_transactions")
    
    transactions = await db.transactions.find(
        {"user_id": current_user.id}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(length=limit)
    
    return [Transaction(**tx) for tx in transactions]

@api_router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard_endpoint(limit: int = 10, current_user: User = Depends(get_current_user)):
    # Track activity
    await log_user_activity(current_user.id, "viewed_leaderboard")
    
    return await get_leaderboard(limit)

# Admin routes (keeping existing ones)
@api_router.get("/admin/users", response_model=List[UserResponse])
async def get_all_users(admin_user: User = Depends(require_admin)):
    users = await db.users.find().to_list(length=None)
    return [UserResponse(**user) for user in users]

@api_router.get("/admin/rules", response_model=List[RewardRule])
async def get_reward_rules(admin_user: User = Depends(require_admin)):
    rules = await db.reward_rules.find().to_list(length=None)
    return [RewardRule(**rule) for rule in rules]

@api_router.post("/admin/rules", response_model=RewardRule)
async def create_reward_rule(rule_data: RewardRule, admin_user: User = Depends(require_admin)):
    # Check if rule key already exists
    existing_rule = await db.reward_rules.find_one({"key": rule_data.key})
    if existing_rule:
        raise HTTPException(status_code=400, detail="Rule key already exists")
    
    await db.reward_rules.insert_one(rule_data.dict())
    return rule_data

# Admin Task Management
@api_router.get("/admin/tasks", response_model=List[Task])
async def get_all_tasks(admin_user: User = Depends(require_admin)):
    """Get all tasks for admin management"""
    tasks = await db.tasks.find().sort("created_at", -1).to_list(length=None)
    return [Task(**task) for task in tasks]

@api_router.post("/admin/tasks", response_model=Task)
async def create_task(task_data: TaskCreate, admin_user: User = Depends(require_admin)):
    """Create a new task"""
    task = Task(**task_data.dict())
    await db.tasks.insert_one(task.dict())
    return task

@api_router.put("/admin/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, task_data: TaskCreate, admin_user: User = Depends(require_admin)):
    """Update an existing task"""
    task_doc = await db.tasks.find_one({"id": task_id})
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    
    updated_data = task_data.dict()
    await db.tasks.update_one({"id": task_id}, {"$set": updated_data})
    
    updated_task = await db.tasks.find_one({"id": task_id})
    return Task(**updated_task)

@api_router.delete("/admin/tasks/{task_id}")
async def delete_task(task_id: str, admin_user: User = Depends(require_admin)):
    """Delete a task"""
    result = await db.tasks.delete_one({"id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}

@api_router.get("/admin/task-completions", response_model=List[TaskCompletion])
async def get_all_task_completions(admin_user: User = Depends(require_admin)):
    """Get all task completions for admin analytics"""
    completions = await db.task_completions.find().sort("completed_at", -1).to_list(length=100)
    return [TaskCompletion(**completion) for completion in completions]

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)

# Initialize database with default data
@api_router.post("/admin/init-db")
async def initialize_database():
    # Create default admin user
    admin_exists = await db.users.find_one({"email": "admin@vitacoin.com"})
    if not admin_exists:
        admin_user = User(
            name="Admin",
            email="admin@vitacoin.com",
            password_hash=hash_password("admin123"),
            role="admin",
            coins=1000
        )
        await db.users.insert_one(admin_user.dict())
    
    # Create default reward rules
    rules = [
        {
            "key": "daily_login",
            "description": "Daily login reward",
            "points": 10,
            "penalty": False,
            "active": True,
            "cooldown_hours": 24
        },
        {
            "key": "task_daily",
            "description": "Daily task completion",
            "points": 5,
            "penalty": False,
            "active": True
        },
        {
            "key": "task_weekly",
            "description": "Weekly task completion",
            "points": 25,
            "penalty": False,
            "active": True
        },
        {
            "key": "task_achievement",
            "description": "Achievement task completion",
            "points": 50,
            "penalty": False,
            "active": True
        }
    ]
    
    for rule_data in rules:
        existing_rule = await db.reward_rules.find_one({"key": rule_data["key"]})
        if not existing_rule:
            rule = RewardRule(id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), **rule_data)
            await db.reward_rules.insert_one(rule.dict())
    
    # Create enhanced tasks with specific requirements
    default_tasks = [
        {
            "title": "First Login",
            "description": "Welcome! Complete your first login to earn coins.",
            "category": "daily",
            "coins_reward": 5,
            "difficulty": "easy",
            "requirements": {"action": "login", "description": "Simply log in to complete this task"}
        },
        {
            "title": "Profile Explorer",
            "description": "Explore your profile and check your transaction history.",
            "category": "daily",
            "coins_reward": 10,
            "difficulty": "easy",
            "requirements": {
                "actions": ["view_profile", "view_transactions"],
                "description": "Visit your profile and check your transaction history"
            }
        },
        {
            "title": "Social Butterfly",
            "description": "Check out the leaderboard and see how you rank against other players.",
            "category": "daily",
            "coins_reward": 15,
            "difficulty": "easy",
            "requirements": {
                "action": "view_leaderboard",
                "description": "Visit the leaderboard to see top players"
            }
        },
        {
            "title": "Task Master",
            "description": "Show your dedication by completing 3 different tasks in one day.",
            "category": "weekly",
            "coins_reward": 50,
            "difficulty": "medium",
            "requirements": {
                "action": "complete_tasks",
                "count": 3,
                "timeframe": "daily",
                "description": "Complete 3 different tasks in one day"
            }
        },
        {
            "title": "Coin Collector",
            "description": "Accumulate 100 total coins to unlock this achievement.",
            "category": "achievement",
            "coins_reward": 25,
            "difficulty": "medium",
            "requirements": {
                "action": "accumulate_coins",
                "target": 100,
                "description": "Earn 100 total coins through various activities"
            }
        },
        {
            "title": "Leaderboard Climber",
            "description": "Reach the top 3 positions on the leaderboard.",
            "category": "achievement",
            "coins_reward": 100,
            "difficulty": "hard",
            "requirements": {
                "action": "reach_leaderboard_position",
                "position": 3,
                "description": "Climb to the top 3 on the leaderboard"
            }
        },
        {
            "title": "Weekly Warrior",
            "description": "Complete your daily login for 7 consecutive days.",
            "category": "weekly",
            "coins_reward": 75,
            "difficulty": "medium",
            "requirements": {
                "action": "consecutive_logins",
                "days": 7,
                "description": "Log in daily for 7 consecutive days"
            }
        },
        {
            "title": "Community Member",
            "description": "Welcome to the Vitacoin community! Claim your welcome bonus.",
            "category": "special",
            "coins_reward": 20,
            "difficulty": "easy",
            "requirements": {
                "action": "welcome_bonus",
                "description": "Welcome bonus for joining the community"
            }
        }
    ]
    
    for task_data in default_tasks:
        existing_task = await db.tasks.find_one({"title": task_data["title"]})
        if not existing_task:
            task = Task(id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), **task_data)
            await db.tasks.insert_one(task.dict())
    
    return {"message": "Database initialized successfully with enhanced task system"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()