import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"), future=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class Rating(Base):
    __tablename__ = "ratings"
    player_id = Column(Integer, ForeignKey("players.id"), primary_key=True)
    mu = Column(Float, default=1500)
    phi = Column(Float, default=350)
    sigma = Column(Float, default=0.06)

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    played_at = Column(DateTime)
    player_id = Column(Integer)
    opponent_id = Column(Integer)
    score = Column(Float)

class RatingHistory(Base):
    __tablename__ = "rating_history"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer)
    player_id = Column(Integer)
    mu_before = Column(Float)
    mu_after = Column(Float)
    phi_before = Column(Float)
    phi_after = Column(Float)
