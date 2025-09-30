# timesplit_game.py — TimeSplit (Dragoncito Edition) + SQLite/SQLAlchemy
# - Carreras & Fútbol
# - Power-ups: TURBO, ESCUDO, FIREBALL, FREEZE, DRAGON
# - Splits en ms
# - Guarda sesión y splits en SQLite (SQLAlchemy)
# - Ranking desde SQLite (mejor puntaje por jugador)
# - Export CSV/XLSX por sesión
#
# Controles:
# Menú: ↑/↓ navega · ENTER elegir · 1..6 personaje · M mute · ESC salir
# Juego: ENTER nueva · ESPACIO pausa · R reiniciar · TAB cambia modo · L vuelta/periodo
# Guardado/Export: S guardar · E CSV · X Excel · U sync API
# Ajustes: [ y ] tick (50–1000 ms) · - y + duración (modo)
# Carreras: ↑/↓ velocidad
# Fútbol: Flechas moverse · F chutar

import os, json, csv, time, uuid, random, re
import pygame as pg
import requests
from dataclasses import dataclass
from typing import List, Dict

# ---------- SQLAlchemy (SQLite) ----------
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text, ForeignKey, UniqueConstraint, select, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DB_FILE = "timesplit.sqlite"
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

class GameSessionORM(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)           # uid
    player = Column(String, nullable=False)
    mode = Column(String, nullable=False)           # "carreras" | "futbol"
    started_at = Column(Integer, nullable=False)    # epoch ms
    duration_ms = Column(Integer, nullable=False)
    total_score = Column(Float, nullable=False)
    splits = relationship("SplitORM", cascade="all, delete-orphan", back_populates="session")

class SplitORM(Base):
    __tablename__ = "splits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    t_ms = Column(Integer, nullable=False)
    lap = Column(Integer, nullable=False)
    score = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
    session = relationship("GameSessionORM", back_populates="splits")
    __table_args__ = (UniqueConstraint('session_id','id', name='uix_session_id_id'),)

def orm_init_db():
    Base.metadata.create_all(engine)

def orm_upsert_session_with_splits(payload: Dict):
    """
    Inserta/actualiza la sesión (por id) y *reemplaza* todos sus splits:
    - si existe, borra los splits anteriores y reescribe
    - si no existe, crea la sesión con sus splits
    """
    with SessionLocal() as db:
        sid = payload["id"]
        ses = db.get(GameSessionORM, sid)
        if not ses:
            ses = GameSessionORM(
                id=sid,
                player=payload["player"],
                mode=payload["mode"],
                started_at=int(payload["startedAt"]),
                duration_ms=int(payload["durationMs"]),
                total_score=float(payload["totalScore"])
            )
            db.add(ses)
        else:
            ses.player = payload["player"]
            ses.mode = payload["mode"]
            ses.started_at = int(payload["startedAt"])
            ses.duration_ms = int(payload["durationMs"])
            ses.total_score = float(payload["totalScore"])
            # borrar splits previos
            ses.splits.clear()

        for sp in payload.get("splits", []):
            ses.splits.append(SplitORM(
                session_id=sid,
                t_ms=int(sp["t"]),
                lap=int(sp["lap"]),
                score=float(sp["score"]),
                note=sp.get("note")
            ))
        db.commit()

def orm_leaderboard_best_by_player(mode: str, limit: int = 10) -> List[Dict]:
    """
    Devuelve [{player, best_score}] ordenado desc, mejor total_score por jugador para 'mode'.
    """
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

# ---------- Pygame / Juego ----------
WIDTH, HEIGHT = 960, 540
FPS = 60
ASSETS_DIR = "assets"

def uid(prefix="s"):
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def fmt_ms(ms: int) -> str:
    s = ms // 1000
    mm = s // 60
    ss = s % 60
    cs = (ms % 1000) // 10
    return f"{mm:02d}:{ss:02d}.{cs:02d}"

def safe_filename(text: str) -> str:
    import re
    name = re.sub(r'[\\/:*?"<>|]+', "_", text)
    return name.strip().strip(".")

@dataclass
class Split:
    t: int
    score: float
    lap: int
    note: str | None = None

class Session:
    def __init__(self, player: str, mode: str):
        self.id = uid()
        self.player = player or "Jugador/a"
        self.mode = mode
        self.startedAt = int(time.time()*1000)
        self.totalScore = 0.0
        self.durationMs = 0
        self.splits: List[Split] = []

# ---- Export por sesión (CSV/XLSX) ----
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

def export_csv(payload: dict) -> str:
    rows = [["player","mode","startedAt","durationMs","totalScore","t(ms)","lap","score","note"]]
    for sp in payload["splits"]:
        rows.append([
            payload["player"], payload["mode"],
            time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(payload["startedAt"]/1000)),
            str(payload["durationMs"]),
            str(payload["totalScore"]),
            str(sp["t"]), str(sp["lap"]), str(sp["score"]), sp.get("note") or ""
        ])
    player_safe = safe_filename(payload['player'])
    fname = f"timesplit_{payload['mode']}_{player_safe}_{payload['startedAt']}.csv"
    with open(fname, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    return fname

def export_xlsx(payload: dict, participants: List[dict]) -> str:
    wb = Workbook()
    ws1 = wb.active; ws1.title = "Resumen"
    ws1.append(["Campo", "Valor"])
    ws1.append(["Jugador", payload["player"]])
    ws1.append(["Modo", payload["mode"]])
    ws1.append(["Inicio", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(payload["startedAt"]/1000))])
    ws1.append(["Duración (ms)", payload["durationMs"]])
    ws1.append(["Puntaje total", payload["totalScore"]])
    ws1.append([])
    ws1.append(["Participante","Rol","Marca"])
    for p in participants:
        ws1.append([p["name"], p["role"], p["mark"]])
    for col in range(1, 5):
        ws1.column_dimensions[get_column_letter(col)].width = 22

    ws2 = wb.create_sheet("Splits")
    ws2.append(["t (ms)", "lap/periodo", "score", "note"])
    for sp in payload["splits"]:
        ws2.append([sp["t"], sp["lap"], sp["score"], sp.get("note") or ""])
    for col in range(1, 5):
        ws2.column_dimensions[get_column_letter(col)].width = 18

    player_safe = safe_filename(payload['player'])
    fname = f"timesplit_{payload['mode']}_{player_safe}_{payload['startedAt']}.xlsx"
    wb.save(fname)
    return fname

# ---- Opcional: Sync API ----
def sync_to_api(payload: dict, api_url: str) -> tuple[bool, str]:
    try:
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("TSR_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key
        r = requests.post(api_url, json=payload, headers=headers, timeout=10)
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

# ---- Recursos gráficos/sonoros ----
def load_img(name, scale=None):
    path = os.path.join(ASSETS_DIR, name)
    try:
        img = pg.image.load(path).convert_alpha()
        if scale:
            img = pg.transform.smoothscale(img, scale)
        return img
    except Exception:
        return None

def load_snd(name, volume=0.6):
    if not pg.mixer.get_init():
        return None
    # admite .ogg o .wav alternadamente
    for candidate in (name, os.path.splitext(name)[0] + ".wav", os.path.splitext(name)[0] + ".ogg"):
        path = os.path.join(ASSETS_DIR, candidate)
        if os.path.exists(path):
            try:
                snd = pg.mixer.Sound(path)
                snd.set_volume(volume)
                return snd
            except Exception:
                continue
    return None

# ---- Constantes de juego ----
CHARACTERS = [
    {"name":"Aqua",  "color": ( 60,200,255)},
    {"name":"Lime",  "color": ( 80,220,120)},
    {"name":"Rose",  "color": (235, 80,140)},
    {"name":"Gold",  "color": (245,200, 40)},
    {"name":"Violet","color": (170, 95,255)},
    {"name":"Dragoncito","color": (100,200,100)},  # usa assets/dragon.png si existe
]
BOT_NAMES_RACE = ["Bot-Alpha","Bot-Bravo","Bot-Charlie","Bot-Delta","Bot-Echo"]
BOT_NAMES_FOOT = ["Rival-1","Rival-2","Rival-3","Compi-1","Compi-2"]

PU_TURBO   = "TURBO"
PU_SHIELD  = "ESCUDO"
PU_FIRE    = "FIREBALL"
PU_FREEZE  = "FREEZE"
PU_DRAGON  = "DRAGON"

class Game:
    def __init__(self):
        # DB ready
        orm_init_db()

        # Pygame
        pg.init()
        pg.display.set_caption("TimeSplit — Dragoncito Edition (SQLite)")
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        self.clock = pg.time.Clock()
        self.font = pg.font.SysFont("consolas,arial", 18)
        self.big = pg.font.SysFont("consolas,arial", 28, bold=True)

        # Audio
        self.muted = False
        try:
            pg.mixer.init()
        except Exception:
            pass
        self.snd_pick  = load_snd("s_pick.ogg", 0.7)  or load_snd("s_pick.wav", 0.7)
        self.snd_shoot = load_snd("s_shoot.ogg", 0.7) or load_snd("s_shoot.wav", 0.7)
        self.snd_goal  = load_snd("s_goal.ogg", 0.8)  or load_snd("s_goal.wav", 0.8)
        self.music_current = None

        # Estados
        self.screen_state = "menu"
        self.player_name = "Jugador/a"
        self.mode = "carreras"
        self.tick_ms = 200
        self.target_duration_s = 60
        self.half_duration_s = 45
        self.api_url = os.getenv("TSR_API") or "http://localhost:3000/api/sessions"

        self.running = False
        self.elapsed_ms = 0
        self.score = 0.0
        self.lap = 1
        self.enemy_score = 0
        self.last_tick = 0
        self.session: Session | None = None
        self.last_saved_payload: dict | None = None
        self.message = ""
        self.message_ttl = 0

        # Personajes
        self.char_idx = 5  # arranco con Dragoncito 💚 por tu pedido
        self.player_color = CHARACTERS[self.char_idx]["color"]
        self.player_label = CHARACTERS[self.char_idx]["name"]

        # Sprites
        self.img_car_player = load_img("car_player.png", (64,32))
        self.img_car_bot    = load_img("car_bot.png",    (64,32))

        self.img_player     = load_img("player_ball.png", (22,22))
        self.img_npc_ally   = load_img("npc_ally.png",    (18,18))
        self.img_npc_enemy  = load_img("npc_enemy.png",   (16,16))
        self.img_ball       = load_img("ball.png",        (12,12))

        self.img_pu_turbo   = load_img("pu_turbo.png",  (20,20))
        self.img_pu_shield  = load_img("pu_shield.png", (20,20))
        self.img_pu_fire    = load_img("pu_fire.png",   (18,18))
        self.img_pu_freeze  = load_img("pu_freeze.png", (18,18))

        # 👉 imagen del Dragoncito (usada en fútbol y como adorno en autos)
        self.img_dragon     = load_img("dragon.png", (48,48))

        # Carreras
        self.speed = 20.0
        self.cars: list[dict] = []
        self._init_race_bots()

        # Fútbol
        self.player_pos = pg.Vector2(120, HEIGHT/2)
        self.ball_pos = pg.Vector2(WIDTH/2, HEIGHT/2)
        self.ball_vel = pg.Vector2(0,0)
        self.npcs: list[dict] = []
        self._init_football_npcs()

        # Power-ups
        self.powerups: list[dict] = []
        self.active_pu: dict[str, dict] = {}
        self.next_pu_spawn_ms = 4000

        # Menú
        self.menu_idx = 0
        self.menu_items = ["Jugar: Carreras", "Jugar: Fútbol", "Cambiar Personaje", "Salir"]

    # -------- Música --------
    def music_play(self, filename, vol=0.45):
        if not pg.mixer.get_init() or self.muted:
            return
        for candidate in (filename, os.path.splitext(filename)[0] + ".wav", os.path.splitext(filename)[0] + ".ogg"):
            path = os.path.join(ASSETS_DIR, candidate)
            if os.path.exists(path):
                if self.music_current == candidate:
                    return
                try:
                    pg.mixer.music.load(path)
                    pg.mixer.music.set_volume(vol)
                    pg.mixer.music.play(-1)
                    self.music_current = candidate
                    return
                except Exception:
                    continue
        self.music_current = None

    def music_stop(self):
        try: pg.mixer.music.stop()
        except Exception: pass
        self.music_current = None

    # -------- UI helpers --------
    def play(self, sound):
        if self.muted or not sound: return
        try: sound.play()
        except: pass

    def info(self, text, ttl=120):
        self.message = text
        self.message_ttl = ttl
        print(text)

    # -------- Inicialización --------
    def _init_race_bots(self):
        import random
        self.cars = []
        lanes = [HEIGHT*0.30, HEIGHT*0.38, HEIGHT*0.46, HEIGHT*0.54, HEIGHT*0.62]
        random.shuffle(lanes)
        self.cars.append({
            "name": f"{self.player_label} ({self.player_name})",
            "color": self.player_color,
            "x": 60, "y": lanes[0], "speed": self.speed, "dist": 0.0, "is_player": True
        })
        for i in range(1, min(5, len(lanes))):
            self.cars.append({
                "name": BOT_NAMES_RACE[i-1],
                "color": (180,180,200) if i%2==0 else (200,150,80),
                "x": random.randint(20, 180),
                "y": lanes[i],
                "speed": random.uniform(12, 28),
                "dist": 0.0,
                "is_player": False
            })

    def _init_football_npcs(self):
        import random
        self.npcs = []
        for i in range(3):
            self.npcs.append({
                "name": BOT_NAMES_FOOT[i],
                "color": (210,80,80),
                "pos": pg.Vector2(random.randint(WIDTH//2+40, WIDTH-60), random.randint(60, HEIGHT-60)),
                "role": "rival"
            })
        for i in range(2):
            self.npcs.append({
                "name": BOT_NAMES_FOOT[3+i],
                "color": (80,180,250),
                "pos": pg.Vector2(random.randint(60, WIDTH//2-60), random.randint(60, HEIGHT-60)),
                "role": "ally"
            })

    # -------- Sesión --------
    def start_session(self):
        self.session = Session(self.player_name, self.mode)
        self.running = True
        self.elapsed_ms = 0
        self.score = 0.0
        self.lap = 1
        self.enemy_score = 0
        self.last_tick = 0
        self.powerups.clear()
        self.active_pu.clear()
        self.next_pu_spawn_ms = 2500
        self.player_pos.update(120, HEIGHT/2)
        self.ball_pos.update(WIDTH/2, HEIGHT/2)
        self.ball_vel.update(0,0)
        self._init_race_bots()
        self._init_football_npcs()
        self.info("Sesión iniciada")
        if self.mode == "carreras":
            self.music_play("music_race.ogg", 0.45)
        else:
            self.music_play("music_football.ogg", 0.45)

    def finish_session(self):
        if not self.session: return
        self.running = False
        limit = self.get_limit_ms()
        self.session.totalScore = round(self.score, 2)
        self.session.durationMs = max(self.elapsed_ms, limit)
        payload = {
            "id": self.session.id,
            "player": self.session.player,
            "mode": self.session.mode,
            "startedAt": self.session.startedAt,
            "durationMs": self.session.durationMs,
            "totalScore": self.session.totalScore,
            "splits": [{"t": s.t, "score": s.score, "lap": s.lap, "note": s.note} for s in self.session.splits],
        }
        self.last_saved_payload = payload

        # Guardar en SQLite (upsert sesión + reemplazo completo de splits)
        try:
            orm_upsert_session_with_splits(payload)
            self.info("Guardado en SQLite (timesplit.sqlite)")
        except Exception as e:
            self.info(f"Error al guardar en SQLite: {e}")

    def reset(self):
        self.running = False
        self.elapsed_ms = 0
        self.score = 0.0
        self.lap = 1
        self.enemy_score = 0
        self.last_tick = 0
        self.session = None
        self.powerups.clear()
        self.active_pu.clear()
        self._init_race_bots()
        self._init_football_npcs()
        self.info("Reiniciado")

    def get_limit_ms(self):
        return int(self.target_duration_s*1000) if self.mode=="carreras" else int(self.half_duration_s*2*1000)

    # -------- Power-ups --------
    def spawn_powerup(self):
        import random
        if random.random() < 0.10:
            ptype = PU_DRAGON
        else:
            ptype = random.choice([PU_TURBO, PU_SHIELD] if self.mode=="carreras" else [PU_FIRE, PU_FREEZE])
        if self.mode == "carreras":
            x = random.randint(80, WIDTH-80)
            y = random.choice([HEIGHT*0.30, HEIGHT*0.38, HEIGHT*0.46, HEIGHT*0.54, HEIGHT*0.62])
        else:
            x = random.randint(60, WIDTH-60)
            y = random.randint(60, HEIGHT-60)
        self.powerups.append({"type": ptype, "pos": pg.Vector2(x, y), "active": True})

    def pickup_powerup(self, ptype: str):
        if not self.session: return
        if ptype == PU_DRAGON:
            until = self.elapsed_ms + 10000
            label = "POWERUP_DRAGON"
            self.info("¡Dragoncito activado!", ttl=120)
        else:
            until = self.elapsed_ms + (7000 if ptype in (PU_TURBO, PU_FREEZE) else 6000)
            label = f"POWERUP_{ptype}"
        self.active_pu[ptype] = {"until": until}
        self.session.splits.append(Split(self.elapsed_ms, self.score, self.lap, label))
        self.play(self.snd_pick)

    def is_pu_active(self, ptype: str) -> bool:
        x = self.active_pu.get(ptype)
        return bool(x and self.elapsed_ms <= x["until"])

    def update_powerups(self, dt_ms: int):
        if self.elapsed_ms >= self.next_pu_spawn_ms:
            self.spawn_powerup()
            self.next_pu_spawn_ms += random.randint(4000, 7000)
        if self.mode == "carreras":
            player_car = self.cars[0]
            ppos = pg.Vector2(player_car["x"] % (WIDTH+80) - 40, player_car["y"])
            for pu in self.powerups:
                if not pu["active"]: continue
                if ppos.distance_to(pu["pos"]) < 40:
                    pu["active"] = False
                    self.pickup_powerup(pu["type"])
        else:
            for pu in self.powerups:
                if not pu["active"]: continue
                if self.player_pos.distance_to(pu["pos"]) < 28:
                    pu["active"] = False
                    self.pickup_powerup(pu["type"])
        for k in list(self.active_pu.keys()):
            if self.elapsed_ms > self.active_pu[k]["until"]:
                del self.active_pu[k]

    # -------- Lógica --------
    def step_carreras(self, dt_ms: int):
        shield = self.is_pu_active(PU_SHIELD) or self.is_pu_active(PU_DRAGON)
        for car in self.cars:
            if car["is_player"]:
                base = self.speed
                boost = 0.60 if self.is_pu_active(PU_TURBO) else 0.0
                if self.is_pu_active(PU_DRAGON):
                    boost = 1.20
                car["speed"] = base * (1.0 + boost)
            else:
                car["speed"] += random.uniform(-0.6, 0.6)
                car["speed"] = max(10, min(32, car["speed"]))
            car["x"] += car["speed"] * (dt_ms/28.0)
            fr = 0.995 if shield else 0.985
            car["dist"] = car["dist"]*fr + car["speed"] * (dt_ms/1000.0)
            if car["x"] > WIDTH + 40:
                car["x"] = -40
        self.score = self.cars[0]["dist"]

    def step_futbol(self, dt_ms: int):
        dt = dt_ms/16.0
        frozen = self.is_pu_active(PU_FREEZE)
        for npc in self.npcs:
            jitter = pg.Vector2(random.uniform(-1.2,1.2), random.uniform(-1.2,1.2))
            speed = 2.5 * (0.4 if frozen else 1.0)
            npc["pos"] += jitter * speed
            npc["pos"].x = max(20, min(WIDTH-20, npc["pos"].x))
            npc["pos"].y = max(20, min(HEIGHT-20, npc["pos"].y))

        self.ball_vel *= 0.993
        self.ball_pos += self.ball_vel * dt
        if self.ball_pos.y < 12 or self.ball_pos.y > HEIGHT-12:
            self.ball_vel.y *= -1
            self.ball_pos.y = max(12, min(HEIGHT-12, self.ball_pos.y))
        if self.ball_pos.x < 12 or self.ball_pos.x > WIDTH-12:
            self.ball_vel.x *= -1
            self.ball_pos.x = max(12, min(WIDTH-12, self.ball_pos.x))

        goal_top, goal_bot = HEIGHT*0.35, HEIGHT*0.65
        if self.ball_pos.x <= 8 and goal_top <= self.ball_pos.y <= goal_bot:
            self.enemy_score += 1
            self.register_event("GOAL EN CONTRA")
            self.ball_pos.update(WIDTH/2, HEIGHT/2); self.ball_vel.update(0,0)
            self.play(self.snd_goal)
        if self.ball_pos.x >= WIDTH-8 and goal_top <= self.ball_pos.y <= goal_bot:
            self.score += 1
            self.register_event("GOAL A FAVOR")
            self.ball_pos.update(WIDTH/2, HEIGHT/2); self.ball_vel.update(0,0)
            self.play(self.snd_goal)

    def shoot(self):
        diff = self.ball_pos - self.player_pos
        dist = diff.length() or 1
        if dist < 40:
            power = 10 + random.random()*8
            if self.is_pu_active(PU_FIRE):
                power *= 1.6
            if self.is_pu_active(PU_DRAGON):
                power *= 2.0
            v = diff.normalize() * (power*20)
            self.ball_vel += v
            self.register_event("SHOT")
            self.play(self.snd_shoot)

    def register_event(self, note: str):
        if not self.session: return
        self.session.splits.append(Split(self.elapsed_ms, self.score, self.lap, note))

    def maybe_split(self, dt_ms: int):
        if not self.session: return
        if self.elapsed_ms - self.last_tick + dt_ms >= self.tick_ms:
            self.last_tick = self.elapsed_ms + dt_ms
            self.session.splits.append(Split(self.elapsed_ms + dt_ms, self.score, self.lap, None))

    # -------- Export helpers --------
    def participants_summary(self) -> List[dict]:
        if self.mode == "carreras":
            arr = sorted(self.cars, key=lambda c: c["dist"], reverse=True)
            return [{"name": c["name"], "role": "player" if c["is_player"] else "bot", "mark": round(c["dist"],2)} for c in arr]
        else:
            return [
                {"name": f"{self.player_label} ({self.player_name})", "role":"player", "mark": int(self.score)},
                {"name": "Rivales", "role":"bot", "mark": int(self.enemy_score)},
            ]

    # -------- Dibujo --------
    def draw(self):
        s = self.screen
        s.fill((8,12,20))

        if self.screen_state == "menu":
            self.draw_menu()
            pg.display.flip()
            return

        if self.mode == "carreras":
            pg.draw.rect(s,(35,35,35),(0, HEIGHT*0.25, WIDTH, HEIGHT*0.5))
            for x in range(0, WIDTH, 40):
                pg.draw.rect(s,(240,240,240),(x, HEIGHT*0.5-2, 20, 4))
            pg.draw.rect(s,(220,30,70),(WIDTH-10, HEIGHT*0.25, 10, HEIGHT*0.5))
            for car in self.cars:
                x = car["x"] % (WIDTH+80) - 40
                y = car["y"] - 16
                if car["is_player"] and self.img_car_player:
                    s.blit(self.img_car_player, (x, y))
                    # adorno dragon si personaje seleccionado es Dragoncito
                    if self.player_label == "Dragoncito" and self.img_dragon:
                        s.blit(self.img_dragon, (x-2, y-26))
                elif (not car["is_player"]) and self.img_car_bot:
                    s.blit(self.img_car_bot, (x, y))
                else:
                    pg.draw.rect(s, car["color"], (x, y, 44, 32), border_radius=6)
            for pu in self.powerups:
                if not pu["active"]: continue
                pos = (int(pu["pos"].x), int(pu["pos"].y))
                if pu["type"]==PU_TURBO and self.img_pu_turbo:
                    s.blit(self.img_pu_turbo, (pos[0]-10, pos[1]-10))
                elif pu["type"]==PU_SHIELD and self.img_pu_shield:
                    s.blit(self.img_pu_shield, (pos[0]-10, pos[1]-10))
                elif pu["type"]==PU_DRAGON and self.img_dragon:
                    small = pg.transform.smoothscale(self.img_dragon, (24,24))
                    s.blit(small, (pos[0]-12, pos[1]-12))
                else:
                    color = (255,200,60) if pu["type"]==PU_TURBO else (120,200,255)
                    if pu["type"]==PU_DRAGON: color = (255,215,100)
                    pg.draw.circle(s, color, pos, 10)
        else:
            pg.draw.rect(s,(10,120,60),(0,0,WIDTH,HEIGHT))
            pg.draw.rect(s,(255,255,255),(6,6,WIDTH-12,HEIGHT-12),2)
            pg.draw.line(s,(255,255,255),(WIDTH/2,6),(WIDTH/2,HEIGHT-6),2)
            pg.draw.circle(s,(255,255,255),(WIDTH//2, HEIGHT//2), 40, 2)
            goal_top, goal_bot = HEIGHT*0.35, HEIGHT*0.65
            pg.draw.rect(s,(255,255,255),(0, goal_top, 6, goal_bot-goal_top),2)
            pg.draw.rect(s,(255,255,255),(WIDTH-6, goal_top, 6, goal_bot-goal_top),2)
            # jugador con dragon.png si existe y el personaje es Dragoncito
            if self.player_label == "Dragoncito" and self.img_dragon:
                s.blit(self.img_dragon, (int(self.player_pos.x)-24, int(self.player_pos.y)-24))
            elif self.img_player:
                s.blit(self.img_player, (int(self.player_pos.x)-11, int(self.player_pos.y)-11))
            else:
                pg.draw.circle(s, self.player_color, (int(self.player_pos.x), int(self.player_pos.y)), 10)
            for npc in self.npcs:
                pos = (int(npc["pos"].x), int(npc["pos"].y))
                if npc["role"] == "ally" and self.img_npc_ally:
                    s.blit(self.img_npc_ally, (pos[0]-9, pos[1]-9))
                elif npc["role"] == "rival" and self.img_npc_enemy:
                    s.blit(self.img_npc_enemy, (pos[0]-8, pos[1]-8))
                else:
                    pg.draw.circle(s, npc["color"], pos, 9 if npc["role"]=="ally" else 7)
            if self.img_ball:
                s.blit(self.img_ball, (int(self.ball_pos.x)-6, int(self.ball_pos.y)-6))
            else:
                pg.draw.circle(s,(255,255,255),(int(self.ball_pos.x), int(self.ball_pos.y)), 6)
            for pu in self.powerups:
                if not pu["active"]: continue
                pos = (int(pu["pos"].x), int(pu["pos"].y))
                if pu["type"]==PU_FIRE and self.img_pu_fire:
                    s.blit(self.img_pu_fire, (pos[0]-9, pos[1]-9))
                elif pu["type"]==PU_FREEZE and self.img_pu_freeze:
                    s.blit(self.img_pu_freeze, (pos[0]-9, pos[1]-9))
                elif pu["type"]==PU_DRAGON and self.img_dragon:
                    small = pg.transform.smoothscale(self.img_dragon, (22,22))
                    s.blit(small, (pos[0]-11, pos[1]-11))
                else:
                    color = (255,120,60) if pu["type"]==PU_FIRE else (120,220,255)
                    if pu["type"]==PU_DRAGON: color = (255,215,100)
                    pg.draw.circle(s, color, pos, 9, 2)

        # HUD
        mode_label = "Vuelta" if self.mode=="carreras" else "Periodo"
        top = [
            f"Personaje: {self.player_label}  (1..6)   Modo: {self.mode.upper()}   Tick: {self.tick_ms}ms   [M] Mutear",
            f"Tiempo: {fmt_ms(self.elapsed_ms)}   Puntaje: {round(self.score,2)}   {mode_label}: {self.lap}",
            f"Duración: {self.target_duration_s}s" if self.mode=="carreras" else f"Duración por periodo: {self.half_duration_s}s   Rivales: {self.enemy_score}",
            "ENTER=Nueva  ESPACIO=Pausa  R=Reiniciar  L=+Vuelta/Periodo  S=Guardar  E=CSV  X=Excel  U=Sync  TAB=Cambiar modo  ESC=Menú",
            ("Carreras: ↑/↓ velocidad  |  Powerups: TURBO/ESCUDO/DRAGON" if self.mode=="carreras"
             else "Fútbol: Flechas moverte, F=chutar  |  Powerups: FIREBALL/FREEZE/DRAGON"),
        ]
        for i, line in enumerate(top):
            s.blit(self.font.render(line, True, (230,235,245)), (14, 10 + i*20))

        pu_txt = " | ".join([f"{k} {max(0,(v['until']-self.elapsed_ms)//1000)}s" for k,v in self.active_pu.items()])
        if pu_txt:
            s.blit(self.font.render("Activos: " + pu_txt, True, (255,220,120)), (14, 10 + len(top)*20))

        if self.message_ttl > 0:
            s.blit(self.big.render(self.message, True, (255,230,90)), (14, HEIGHT-40))
            self.message_ttl -= 1

        self.draw_ranking_from_db()
        pg.display.flip()

    def draw_ranking_from_db(self):
        arr = orm_leaderboard_best_by_player(self.mode, 10)
        x0, y0 = WIDTH-360, 120
        box = pg.Rect(x0-16, y0-16, 340, 260)
        pg.draw.rect(self.screen, (25,25,40), box, border_radius=12)
        pg.draw.rect(self.screen, (70,70,90), box, 2, border_radius=12)
        title = self.big.render("Ranking (SQLite) Top 10", True, (240,240,255))
        self.screen.blit(title, (x0, y0-12))
        for i, s in enumerate(arr):
            line = f"{i+1:>2}  {s['player']:<12}  {s['best_score']:.2f}"
            txt = self.font.render(line, True, (220,220,235))
            self.screen.blit(txt, (x0, y0+24 + i*22))

    # -------- Menú --------
    def draw_menu(self):
        s = self.screen
        s.fill((10, 14, 28))
        self.music_play("music_menu.ogg", 0.5)
        title = self.big.render("TimeSplit — Menú Principal (Dragoncito + SQLite)", True, (240,240,255))
        s.blit(title, (WIDTH//2 - title.get_width()//2, 60))
        for i, it in enumerate(self.menu_items):
            is_sel = (i == self.menu_idx)
            r = pg.Rect(WIDTH//2 - 200, 150 + i*60, 400, 46)
            pg.draw.rect(s, (40,50,80), r, border_radius=10)
            if is_sel:
                pg.draw.rect(s, (120,160,255), r, 3, border_radius=10)
            txt = self.font.render(it, True, (230,235,245))
            s.blit(txt, (r.x + 16, r.y + 12))
        sub = self.font.render(f"Personaje actual: {self.player_label}  (1..6 para cambiar)", True, (200,210,230))
        s.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT - 100))
        help_txt = self.font.render("↑/↓ Navegar  |  ENTER Elegir  |  M Mutear  |  ESC Salir", True, (200,210,230))
        s.blit(help_txt, (WIDTH//2 - help_txt.get_width()//2, HEIGHT - 60))

    def menu_input(self, e: pg.event.Event):
        if e.type == pg.KEYDOWN:
            if e.key == pg.K_DOWN:
                self.menu_idx = (self.menu_idx + 1) % len(self.menu_items)
            elif e.key == pg.K_UP:
                self.menu_idx = (self.menu_idx - 1) % len(self.menu_items)
            elif e.key in (pg.K_1, pg.K_2, pg.K_3, pg.K_4, pg.K_5, pg.K_6):
                self.char_idx = {pg.K_1:0, pg.K_2:1, pg.K_3:2, pg.K_4:3, pg.K_5:4, pg.K_6:5}[e.key]
                self.player_color = CHARACTERS[self.char_idx]["color"]
                self.player_label = CHARACTERS[self.char_idx]["name"]
            elif e.key == pg.K_RETURN:
                choice = self.menu_items[self.menu_idx]
                if "Carreras" in choice:
                    self.mode = "carreras"; self.screen_state = "game"; self.start_session()
                elif "Fútbol" in choice or "Futbol" in choice:
                    self.mode = "futbol"; self.screen_state = "game"; self.start_session()
                elif "Personaje" in choice:
                    self.char_idx = (self.char_idx + 1) % len(CHARACTERS)
                    self.player_color = CHARACTERS[self.char_idx]["color"]
                    self.player_label = CHARACTERS[self.char_idx]["name"]
                elif "Salir" in choice:
                    pg.event.post(pg.event.Event(pg.QUIT))

    # -------- Input --------
    def handle_input(self):
        keys = pg.key.get_pressed()
        if self.screen_state == "menu":
            return
        if self.mode == "carreras":
            if keys[pg.K_UP]: self.speed = min(200, self.speed + 0.30)
            if keys[pg.K_DOWN]: self.speed = max(0,   self.speed - 0.30)
        else:
            if keys[pg.K_UP]:    self.player_pos.y = max(20, self.player_pos.y - 4)
            if keys[pg.K_DOWN]:  self.player_pos.y = min(HEIGHT-20, self.player_pos.y + 4)
            if keys[pg.K_LEFT]:  self.player_pos.x = max(20, self.player_pos.x - 4)
            if keys[pg.K_RIGHT]: self.player_pos.x = min(WIDTH-20, self.player_pos.x + 4)

    def process_events(self) -> bool:
        for e in pg.event.get():
            if e.type == pg.QUIT:
                return False
            if self.screen_state == "menu":
                self.menu_input(e)
                if e.type == pg.KEYDOWN:
                    if e.key == pg.K_m:
                        self.muted = not self.muted
                        if self.muted: self.music_stop()
                        else: self.music_play("music_menu.ogg", 0.5)
                    if e.key == pg.K_ESCAPE:
                        return False
                continue

            if e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    self.screen_state = "menu"; self.running = False
                    self.music_play("music_menu.ogg", 0.5)
                elif e.key == pg.K_TAB:
                    self.mode = "futbol" if self.mode == "carreras" else "carreras"
                    self.info(f"Modo: {self.mode}")
                elif e.key == pg.K_RETURN:
                    self.start_session()
                elif e.key == pg.K_SPACE:
                    self.running = not self.running
                    self.info("Reanudar" if self.running else "Pausa")
                elif e.key == pg.K_r:
                    self.reset()
                elif e.key == pg.K_l:
                    self.lap = self.lap + 1 if self.mode=="carreras" else min(2, self.lap+1)
                    if self.session:
                        self.session.splits.append(Split(self.elapsed_ms, self.score, self.lap, "NEXT"))
                elif e.key == pg.K_s:
                    if self.session: self.finish_session()
                elif e.key == pg.K_e:
                    if self.last_saved_payload:
                        fname = export_csv(self.last_saved_payload); self.info(f"CSV: {fname}")
                    else:
                        self.info("No hay sesión guardada aún")
                elif e.key == pg.K_x:
                    if self.last_saved_payload:
                        fname = export_xlsx(self.last_saved_payload, self.participants_summary()); self.info(f"Excel: {fname}")
                    else:
                        self.info("No hay sesión guardada para Excel")
                elif e.key == pg.K_u:
                    if self.last_saved_payload:
                        ok, txt = sync_to_api(self.last_saved_payload, self.api_url)
                        self.info("¡Sincronizado!" if ok else f"Error sync: {txt[:120]}")
                    else:
                        self.info("No hay sesión guardada para subir")
                elif e.key == pg.K_f and self.mode == "futbol":
                    self.shoot()
                elif e.key in (pg.K_1, pg.K_2, pg.K_3, pg.K_4, pg.K_5, pg.K_6):
                    self.char_idx = {pg.K_1:0, pg.K_2:1, pg.K_3:2, pg.K_4:3, pg.K_5:4, pg.K_6:5}[e.key]
                    self.player_color = CHARACTERS[self.char_idx]["color"]
                    self.player_label = CHARACTERS[self.char_idx]["name"]
                    for c in self.cars:
                        if c["is_player"]:
                            c["color"] = self.player_color
                            c["name"]  = f"{self.player_label} ({self.player_name})"
                    self.info(f"Personaje: {self.player_label}")
                elif e.key == pg.K_LEFTBRACKET:     # [
                    self.tick_ms = max(50,  self.tick_ms - 50); self.info(f"tick {self.tick_ms}ms")
                elif e.key == pg.K_RIGHTBRACKET:    # ]
                    self.tick_ms = min(1000, self.tick_ms + 50); self.info(f"tick {self.tick_ms}ms")
                elif e.key == pg.K_MINUS:
                    if self.mode == "carreras":
                        self.target_duration_s = max(10, self.target_duration_s-5); self.info(f"duración {self.target_duration_s}s")
                    else:
                        self.half_duration_s = max(15, self.half_duration_s-5); self.info(f"periodo {self.half_duration_s}s")
                elif e.key in (pg.K_EQUALS, pg.K_PLUS):
                    if self.mode == "carreras":
                        self.target_duration_s = min(180, self.target_duration_s+5); self.info(f"duración {self.target_duration_s}s")
                    else:
                        self.half_duration_s = min(120, self.half_duration_s+5); self.info(f"periodo {self.half_duration_s}s")
                elif e.key == pg.K_m:
                    self.muted = not self.muted
                    if self.muted:
                        self.music_stop()
                    else:
                        self.music_play("music_race.ogg" if self.mode=="carreras" else "music_football.ogg", 0.45)
        return True

    # -------- Bucle --------
    def run(self):
        last = pg.time.get_ticks()
        while True:
            if not self.process_events():
                break
            self.handle_input()
            now = pg.time.get_ticks()
            dt = now - last
            last = now

            if self.screen_state == "game" and self.running and self.session:
                self.elapsed_ms += dt
                self.update_powerups(dt)
                if self.mode == "carreras":
                    self.step_carreras(dt)
                else:
                    self.step_futbol(dt)
                self.maybe_split(dt)
                if self.elapsed_ms >= self.get_limit_ms():
                    self.finish_session()

            self.draw()
            self.clock.tick(FPS)

if __name__ == "__main__":
    Game().run()
