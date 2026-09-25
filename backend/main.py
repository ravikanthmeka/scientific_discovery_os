from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import sqlite3
from datetime import datetime, timedelta
import jwt
import bcrypt
from sqlalchemy.orm import Session
from typing import List, Optional

from agents import AgentManager, close_global_mcp
from langchain_aws import ChatBedrock
import database
import database_models
import billing

# Initialize Database Tables
database_models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()
app.include_router(billing.router, prefix="/api/billing")

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Configuration
SECRET_KEY = "super_secret_discovery_key_for_dev_only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Pydantic Models
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    dob: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str
    token: Optional[str] = None

class SimulationRequest(BaseModel):
    code: str

class BranchRequest(BaseModel):
    domain: str
    query: str
    hypothesis: dict
    token: str

@app.on_event("startup")
async def startup_event():
    print("Starting Scientific Discovery OS Backend...")

@app.on_event("shutdown")
async def shutdown_event():
    await close_global_mcp()

@app.post("/register")
async def register(req: RegisterRequest, db: Session = Depends(database.get_db)):
    if not req.email or not req.password or not req.name:
        raise HTTPException(status_code=400, detail="Email, password, and name are required")
    
    existing_user = db.query(database_models.User).filter(database_models.User.email == req.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(req.password)
    new_user = database_models.User(email=req.email, name=req.name, dob=req.dob, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User registered successfully"}

@app.post("/login")
async def login(req: LoginRequest, db: Session = Depends(database.get_db)):
    user = db.query(database_models.User).filter(database_models.User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # Track Session
    new_session = database_models.Session(user_id=user.id, token=access_token)
    db.add(new_session)
    db.commit()
    
    return {"message": "Login successful", "token": access_token}

@app.get("/history")
async def get_history(token: str, db: Session = Depends(database.get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    history = db.query(database_models.QueryHistory).filter(database_models.QueryHistory.user_id == user_id).order_by(database_models.QueryHistory.created_at.desc()).all()
    
    return [
        {
            "id": h.id,
            "domain": h.domain,
            "query": h.query,
            "status": h.status,
            "created_at": h.created_at.isoformat()
        }
        for h in history
    ]

@app.get("/history/{query_id}/artifacts")
async def get_query_artifacts(query_id: int, token: str, db: Session = Depends(database.get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    query_record = db.query(database_models.QueryHistory).filter(
        database_models.QueryHistory.id == query_id,
        database_models.QueryHistory.user_id == user_id
    ).first()
    
    if not query_record:
        raise HTTPException(status_code=404, detail="Query not found")
        
    artifacts = db.query(database_models.QueryArtifact).filter(
        database_models.QueryArtifact.query_id == query_id
    ).order_by(database_models.QueryArtifact.created_at.asc()).all()
    
    return {
        "artifacts": [
            {
                "agent_id": a.agent_id,
                "agent_name": a.agent_name,
                "content": a.content,
                "created_at": a.created_at.isoformat()
            }
            for a in artifacts
        ]
    }

@app.get("/stats/ingestion")
async def get_ingestion_stats(db: Session = Depends(database.get_db)):
    try:
        count = db.query(database_models.LiteratureChunk.paper_id).distinct().count()
        if count == 0:
            return {"stats": []}
        return {"stats": [{"category": "Dynamic Cache", "count": count}]}
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {"stats": []}

@app.get("/stats/papers")
async def get_ingested_papers(db: Session = Depends(database.get_db)):
    try:
        # Get unique papers from chunks
        chunks = db.query(
            database_models.LiteratureChunk.paper_id,
            database_models.LiteratureChunk.title
        ).distinct(database_models.LiteratureChunk.paper_id).all()
        
        if not chunks:
            return {"papers": {}}
            
        papers = []
        for c in chunks:
            papers.append({
                "id": c.paper_id,
                "title": c.title,
                "authors": "Dynamic"
            })
            
        return {"papers": {"Dynamic Cache": papers}}
    except Exception as e:
        print(f"Error fetching papers: {e}")
        return {"papers": {}}

@app.post("/chat")
async def chat_endpoint(req: ChatRequest, db: Session = Depends(database.get_db)):
    try:
        user = None
        if req.token:
            try:
                user = billing.get_current_user(req.token, db)
            except Exception:
                pass
                
        if user and user.subscription_tier == "FREE" and user.tokens_used >= 1000:
            raise HTTPException(status_code=402, detail="Payment Required: Free token limit reached. Please upgrade to Pro.")

        llm = ChatBedrock(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            max_tokens=4096,
            temperature=0.1,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        system_prompt = "You are the AI assistant for the Scientific Discovery OS. Answer queries regarding research and system state clearly and concisely."
        messages = [("system", system_prompt), ("human", req.message)]
        response = llm.invoke(messages)
        
        # Track usage
        tokens_used = response.response_metadata.get("usage", {}).get("total_tokens", 0)
        if user and tokens_used > 0:
            billing.report_usage(user, tokens_used, db)
            
        return {"reply": response.content}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Chat error: {e}")
        return {"reply": f"Sorry, I encountered an error: {str(e)}"}

import subprocess
import base64
import tempfile
import sys

@app.post("/simulate")
async def run_simulation_endpoint(req: SimulationRequest):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "sim.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(req.code)
            
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr
                
            img_data = None
            img_path = os.path.join(tmpdir, "simulation_output.png")
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                    
            return {
                "success": result.returncode == 0,
                "output": output,
                "image": img_data
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "Simulation timed out after 60 seconds.", "image": None}
    except Exception as e:
        return {"success": False, "output": f"Error running simulation: {str(e)}", "image": None}

@app.post("/api/branch")
async def branch_mission(req: BranchRequest, db: Session = Depends(database.get_db)):
    try:
        user_id = None
        if req.token:
            try:
                payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                user = db.query(database_models.User).filter(database_models.User.id == user_id).first()
                if user and user.subscription_tier == "FREE" and user.tokens_used >= 1000:
                    raise HTTPException(status_code=402, detail="Payment Required: Free token limit reached. Please upgrade to Pro.")
            except jwt.PyJWTError:
                pass
                
        # Generate simulation directly
        agent_manager = AgentManager(websocket=None, db_session=db, user_id=user_id)
        # We don't have expert context handy so we'll pass a default
        sim_artifact = await agent_manager.run_simulation(
            domain=req.domain,
            query=req.query,
            selected_hypothesis=req.hypothesis,
            context="Branched from past session."
        )
        return {"artifact": sim_artifact}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/discovery")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(database.get_db)):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            mission_config = json.loads(data)
            
            domain = mission_config.get("domain", "Unknown")
            query = mission_config.get("query", "")
            token = mission_config.get("token", "")
            
            # Authenticate User via Token
            user_id = None
            session_id = None
            if token:
                try:
                    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                    user_id = payload.get("sub")
                    user = db.query(database_models.User).filter(database_models.User.id == user_id).first()
                    if user and user.subscription_tier == "FREE" and user.tokens_used >= 1000:
                        await websocket.send_json({
                            "agent_id": "SYSTEM",
                            "status": "Error",
                            "log": "Payment Required: Free token limit reached. Please upgrade to Pro.",
                            "artifact": ""
                        })
                        continue
                    # Find active session
                    active_session = db.query(database_models.Session).filter(database_models.Session.token == token).first()
                    if active_session:
                        session_id = active_session.id
                except jwt.PyJWTError:
                    pass
            
            # Log Query History to DB
            query_record = None
            if user_id:
                query_record = database_models.QueryHistory(
                    user_id=user_id,
                    session_id=session_id,
                    domain=domain,
                    query=query,
                    status="Started"
                )
                db.add(query_record)
                db.commit()
                db.refresh(query_record)
            
            print(f"Received mission for domain: {domain}, query: {query}")
            
            if query_record:
                query_record.status = "In Progress"
                db.commit()
                
            agent_manager = AgentManager(websocket, db_session=db, query_id=query_record.id if query_record else None, user_id=user_id)
            await agent_manager.execute_mission(domain, query)
            
            if query_record:
                query_record.status = "Completed"
                db.commit()
            
            await websocket.send_json({
                "agent_id": "SYSTEM",
                "status": "Completed",
                "log": f"Mission [{query}] completed successfully in domain [{domain}].",
                "artifact": ""
            })
            
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error in websocket connection: {e}")
        try:
            await websocket.send_json({
                "agent_id": "SYSTEM",
                "status": "Error",
                "log": f"An error occurred: {str(e)}",
                "artifact": ""
            })
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
