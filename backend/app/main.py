from contextlib import asynccontextmanager
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .config import get_settings
from .database import SessionLocal, engine, get_session
from .diagnostics import run_diagnostics
from .models import Agent, Base, Branch, Device, DeviceStatusLog, ServiceHeartbeat, Ticket, VlanProfile
from .monitor import poll_all_devices, poll_device
from .notifications import escalate_unacknowledged
from .passive import start_passive_listeners
from .realtime import manager
from .reports import monthly_report
from .schemas import AgentCreate, AgentView, BranchCreate, DeviceCreate, DeviceView, LoginRequest, VlanProfileCreate
from .security import issue_token, require_access, verify_token

scheduler = AsyncIOScheduler()

async def record_heartbeat():
    async with SessionLocal() as session:
        session.add(ServiceHeartbeat())
        await session.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    scheduler.add_job(poll_all_devices, "interval", seconds=get_settings().poll_interval_seconds, id="poll-all", replace_existing=True)
    scheduler.add_job(escalate_unacknowledged, "interval", minutes=5, id="escalate-tickets", replace_existing=True)
    scheduler.add_job(record_heartbeat, "interval", seconds=get_settings().heartbeat_interval_seconds, id="heartbeat", replace_existing=True)
    scheduler.start()
    listeners = await start_passive_listeners()
    yield
    scheduler.shutdown(wait=False)
    for listener in listeners:
        listener.close()

app = FastAPI(title="OIC NetRadar", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health(): return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

@app.post("/api/auth/token")
async def login(payload: LoginRequest):
    settings = get_settings()
    if payload.username != settings.admin_username or payload.password != settings.admin_password:
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": issue_token(payload.username), "token_type": "bearer"}

@app.get("/api/branches", dependencies=[Depends(require_access)])
async def list_branches(session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(select(Branch).order_by(Branch.name))).all())

@app.post("/api/branches", status_code=201, dependencies=[Depends(require_access)])
async def add_branch(payload: BranchCreate, session: AsyncSession = Depends(get_session)):
    if await session.scalar(select(Branch).where(Branch.name == payload.name)):
        raise HTTPException(409, "Branch name already exists")
    branch = Branch(**payload.model_dump()); session.add(branch); await session.commit(); await session.refresh(branch)
    return branch

@app.get("/api/vlan-profiles", dependencies=[Depends(require_access)])
async def list_vlan_profiles(session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(select(VlanProfile).order_by(VlanProfile.vlan_id))).all())

@app.post("/api/vlan-profiles", status_code=201, dependencies=[Depends(require_access)])
async def add_vlan_profile(payload: VlanProfileCreate, session: AsyncSession = Depends(get_session)):
    if await session.scalar(select(VlanProfile).where(VlanProfile.vlan_id == payload.vlan_id)):
        raise HTTPException(409, "VLAN profile already exists")
    profile = VlanProfile(**payload.model_dump()); session.add(profile); await session.commit(); await session.refresh(profile)
    return profile

@app.get("/api/devices", response_model=list[DeviceView], dependencies=[Depends(require_access)])
async def list_devices(session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(select(Device).order_by(Device.hostname))).all())

@app.post("/api/devices", response_model=DeviceView, status_code=201, dependencies=[Depends(require_access)])
async def add_device(payload: DeviceCreate, session: AsyncSession = Depends(get_session)):
    if await session.scalar(select(Device).where(Device.ip_address == payload.ip_address)):
        raise HTTPException(409, "A device with this assigned static IP already exists")
    device = Device(**payload.model_dump())
    session.add(device); await session.commit(); await session.refresh(device)
    return device

@app.get("/api/agents", response_model=list[AgentView], dependencies=[Depends(require_access)])
async def list_agents(session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(select(Agent).order_by(Agent.full_name))).all())

@app.post("/api/agents", response_model=AgentView, status_code=201, dependencies=[Depends(require_access)])
async def add_agent(payload: AgentCreate, session: AsyncSession = Depends(get_session)):
    agent = Agent(**payload.model_dump())
    session.add(agent); await session.commit(); await session.refresh(agent)
    return agent

@app.get("/api/tickets", dependencies=[Depends(require_access)])
async def list_tickets(session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(select(Ticket).order_by(Ticket.opened_at.desc()).limit(100))).all())

@app.post("/api/tickets/{ticket_id}/acknowledge", dependencies=[Depends(require_access)])
async def acknowledge_ticket(ticket_id: str, session: AsyncSession = Depends(get_session)):
    ticket = await session.get(Ticket, ticket_id)
    if not ticket: raise HTTPException(404, "Ticket not found")
    if ticket.status == "OPEN":
        ticket.status, ticket.acknowledged_at = "ACKNOWLEDGED", datetime.now(timezone.utc)
        await session.commit()
    return {"id": ticket.id, "status": ticket.status}

@app.post("/api/devices/{device_id}/poll", dependencies=[Depends(require_access)])
async def poll_now(device_id: str, session: AsyncSession = Depends(get_session)):
    if not await session.get(Device, device_id): raise HTTPException(404, "Device not found")
    await poll_device(device_id)
    return {"accepted": True}

@app.get("/api/devices/{device_id}/history", dependencies=[Depends(require_access)])
async def history(device_id: str, session: AsyncSession = Depends(get_session)):
    return list((await session.scalars(select(DeviceStatusLog).where(DeviceStatusLog.device_id == device_id).order_by(DeviceStatusLog.recorded_at.desc()).limit(100))).all())

@app.get("/api/diagnostics/{ip_address}", dependencies=[Depends(require_access)])
async def diagnostics(ip_address: str): return await run_diagnostics(ip_address)

@app.get("/api/reports/monthly.pdf", dependencies=[Depends(require_access)])
async def report(session: AsyncSession = Depends(get_session)):
    return Response(await monthly_report(session), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=netradar-monthly-report.pdf"})

@app.websocket("/ws/live")
async def live_updates(websocket: WebSocket):
    if get_settings().auth_required:
        try:
            verify_token(websocket.query_params.get("token", ""))
        except HTTPException:
            await websocket.close(code=1008)
            return
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
