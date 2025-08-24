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
    created_at: datetime

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DailyRewardResponse(BaseModel):
    success: bool
    message: str
    coins_earned: Optional[int] = None
    new_balance: Optional[int] = None
    next_reward_in: Optional[int] = None  # hours

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
    
    # Return user without password hash
    return UserResponse(**user.dict())

@api_router.post("/auth/login")
async def login(login_data: UserLogin):
    user_doc = await db.users.find_one({"email": login_data.email.lower()})
    if not user_doc or not verify_password(login_data.password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = User(**user_doc)
    access_token = create_access_token({"user_id": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(**user.dict())
    }

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
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

@api_router.get("/transactions", response_model=List[Transaction])
async def get_user_transactions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    transactions = await db.transactions.find(
        {"user_id": current_user.id}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(length=limit)
    
    return [Transaction(**tx) for tx in transactions]

@api_router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard_endpoint(limit: int = 10):
    return await get_leaderboard(limit)

# Admin routes
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
            "key": "task_completed",
            "description": "Task completion reward",
            "points": 5,
            "penalty": False,
            "active": True
        },
        {
            "key": "referral_bonus",
            "description": "Referral bonus",
            "points": 25,
            "penalty": False,
            "active": True
        }
    ]
    
    for rule_data in rules:
        existing_rule = await db.reward_rules.find_one({"key": rule_data["key"]})
        if not existing_rule:
            rule = RewardRule(id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), **rule_data)
            await db.reward_rules.insert_one(rule.dict())
    
    return {"message": "Database initialized successfully"}

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