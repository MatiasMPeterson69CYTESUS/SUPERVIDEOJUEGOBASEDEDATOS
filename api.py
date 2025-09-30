# api.py — FastAPI para consultar timesplit.sqlite
# Endpoints:
#   GET /health
#   GET /sessions?limit=20
#   GET /sessions/{session_id}
#   GET /splits?session_id=...
#   GET /leaderboard?mode=carreras&limit=10

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import create_engine, Column, Integer, Float, String, Text, ForeignKey, select, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_FILE = os.getenv("TS_DB_FILE", "timesplit.sqlite")
if not os.path.exists(DB_FILE):
    raise RuntimeError(f"No se encontró {DB_FILE}. Debe estar en la carpeta del juego.")

engine = create_engine(f"sqlite:///{DB_FILE}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class GameSessionORM(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    player = Column(String, nullable=False)
    mode = Column(String, nullable=False)       # 'carreras' | 'futbol'
    started_at = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=False)
    total_score = Column(Float, nullable=False)
    splits = relationship("SplitORM", back_populates="session", cascade="all, delete-orphan")

class SplitORM(Base):
    __tablename__ = "splits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    t_ms = Column(Integer, nullable=False)
    lap = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
    session = relationship("GameSessionORM", back_populates="splits")

app = FastAPI(title="TimeSplit API", version="1.0.0")

# CORS abierto (ajusta origins si lo necesitas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True, "db": DB_FILE}

@app.get("/sessions")
def list_sessions(limit: int = Query(20, ge=1, le=100)):
    with SessionLocal() as db:
        stmt = (
            select(GameSessionORM.id, GameSessionORM.player, GameSessionORM.mode,
                   GameSessionORM.started_at, GameSessionORM.duration_ms, GameSessionORM.total_score)
            .order_by(GameSessionORM.started_at.desc())
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        return [
            {
                "id": r[0], "player": r[1], "mode": r[2],
                "started_at": r[3], "duration_ms": r[4], "total_score": r[5],
            }
            for r in rows
        ]

@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    with SessionLocal() as db:
        ses = db.get(GameSessionORM, session_id)
        if not ses:
            raise HTTPException(404, detail="session not found")
        return {
            "id": ses.id,
            "player": ses.player,
            "mode": ses.mode,
            "started_at": ses.started_at,
            "duration_ms": ses.duration_ms,
            "total_score": ses.total_score,
            "splits": [
                {"id": sp.id, "t_ms": sp.t_ms, "lap": sp.lap, "score": sp.score, "note": sp.note}
                for sp in db.query(SplitORM).filter(SplitORM.session_id == ses.id).order_by(SplitORM.t_ms.asc()).all()
            ],
        }

@app.get("/splits")
def list_splits(session_id: str = Query(...)):
    with SessionLocal() as db:
        rows = db.query(SplitORM).filter(SplitORM.session_id == session_id).order_by(SplitORM.t_ms.asc()).all()
        return [{"id": sp.id, "session_id": sp.session_id, "t_ms": sp.t_ms, "lap": sp.lap, "score": sp.score, "note": sp.note} for sp in rows]

@app.get("/leaderboard")
def leaderboard(mode: str = Query("carreras"), limit: int = Query(10, ge=1, le=100)):
    with SessionLocal() as db:
        stmt = (
            select(GameSessionORM.player, func.max(GameSessionORM.total_score).label("best"))
            .where(GameSessionORM.mode == mode)
            .group_by(GameSessionORM.player)
            .order_by(func.max(GameSessionORM.total_score).desc())
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        return [{"player": r[0], "best_score": float(r[1])} for r in rows]
