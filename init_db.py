# init_db.py — Inicializa timesplit.sqlite con SQLAlchemy
# Uso:
#   python init_db.py                -> crea tablas si no existen
#   python init_db.py --seed         -> crea tablas + inserta 1 sesión de ejemplo con splits
#   python init_db.py --db otra.sqlite  -> usa otro archivo de BD

import argparse, time, uuid, random
from sqlalchemy import create_engine, Column, Integer, Float, String, Text, ForeignKey, select, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

def uid(prefix="s"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

Base = declarative_base()

class GameSessionORM(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)           # uid
    player = Column(String, nullable=False)
    mode = Column(String, nullable=False)           # 'carreras' | 'futbol'
    started_at = Column(Integer, nullable=False)    # epoch ms
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

def create_db(db_file: str):
    engine = create_engine(f"sqlite:///{db_file}", future=True)
    Base.metadata.create_all(engine)
    return engine

def seed_example(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as db:
        sid = uid()
        now = int(time.time()*1000)
        # Sesión de ejemplo en modo 'carreras'
        ses = GameSessionORM(
            id=sid,
            player="DemoPlayer",
            mode="carreras",
            started_at=now,
            duration_ms=90_000,
            total_score=round(random.uniform(300, 900), 2),
        )
        db.add(ses)
        # Splits cada 200ms (solo como demo)
        t = 0
        score = 0.0
        for k in range(40):
            t += 200
            score += random.uniform(3, 20)
            ses.splits.append(SplitORM(session_id=sid, t_ms=t, lap=1 + k//20, score=round(score,2),
                                       note=random.choice([None, "", "SHOT", "POWERUP_TURBO"])))
        db.commit()
        print(f"✅ Sembrada sesión demo: {sid} con {len(ses.splits)} splits")

def main():
    parser = argparse.ArgumentParser(description="Inicializa timesplit.sqlite (SQLAlchemy)")
    parser.add_argument("--db", default="timesplit.sqlite", help="Ruta del archivo SQLite (por defecto: timesplit.sqlite)")
    parser.add_argument("--seed", action="store_true", help="Sembrar una sesión de ejemplo con splits")
    args = parser.parse_args()

    engine = create_db(args.db)
    print(f"✅ Tablas creadas/verificadas en {args.db}")

    if args.seed:
        seed_example(engine)

    # Mostrar un resumen rápido
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as db:
        total_sessions = db.execute(select(func.count()).select_from(GameSessionORM)).scalar_one()
        total_splits = db.execute(select(func.count()).select_from(SplitORM)).scalar_one()
        print(f"📊 Resumen: {total_sessions} sesiones, {total_splits} splits")

if __name__ == "__main__":
    main()
