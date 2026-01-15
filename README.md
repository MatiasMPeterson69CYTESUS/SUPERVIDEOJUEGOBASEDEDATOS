🎮 TimeSplit — Dragoncito Edition
PostgreSQL + Glicko-2 Ranking System

TimeSplit es un videojuego desarrollado en Python (pygame) que integra un sistema de ranking Glicko-2 persistente sobre PostgreSQL, permitiendo registrar partidas, sesiones y eventos del juego, y posteriormente responder consultas SQL avanzadas para análisis estadístico y ranking competitivo.

Este proyecto fue desarrollado como parte de un trabajo académico de Bases de Datos, cumpliendo con requerimientos de persistencia, modelado relacional y consultas analíticas.

🚀 Características principales

🎮 Juego interactivo en Python (pygame)

🐉 Personaje jugable “Dragoncito”

🏁 Modos de juego:

Carreras

Fútbol

🧠 Sistema de ranking Glicko-2

Rating

Rating Deviation (RD)

Volatilidad (vol)

🗄️ Persistencia completa en PostgreSQL

📊 Consultas SQL para informes:

Top 10 ranking

Historial de partidas

Variaciones de rating

Estadísticas por organización

Winrate por jugador

Distribución por modo de juego

🔁 Fallback automático a SQLite si PostgreSQL no está disponible

📦 Entorno reproducible con venv + requirements.txt

🧱 Arquitectura del proyecto
🐍 Backend / Juego (Python)

timesplit_game.py
Archivo principal del juego.
Incluye:

Lógica del juego (pygame)

Integración con base de datos vía SQLAlchemy

Cálculo y actualización de Glicko-2

Pantalla de ranking Top 10

🗄️ Base de Datos (PostgreSQL)

El juego genera y utiliza las siguientes tablas:

organizations
Agrupa jugadores por club/organización.

players
Guarda los parámetros Glicko-2:

rating

rd

vol

gender

org_id

matches


Registra cada enfrentamiento:

modo (carreras / fútbol)

jugadores

scores

ganador

timestamp (played_at en epoch ms)

game_sessions
Representa una sesión de juego completa.

splits
Eventos temporales dentro de una sesión (telemetría).

match_player_stats
Tabla clave para el informe:

rating_before / rating_after

rd_before / rd_after

vol_before / vol_after

outcome
Permite calcular variaciones de ranking por partida.

⚙️ Instalación y ejecución (Ubuntu)

1️⃣ Clonar el repositorio


git clone https://github.com/tu-usuario/timesplit.git


cd timesplit



2️⃣ Crear entorno virtual


python3 -m venv venv


source venv/bin/activate


3️⃣ Instalar dependencias

pip install -r requirements.txt



4️⃣ Configurar variables de entorno



Crear archivo .env en la raíz del proyecto:



DATABASE_URL=postgresql://usuario:password@localhost:5432/timesplit


TSR_PLAYER=Jugador/a




⚠️ Si PostgreSQL no está disponible, el juego usará SQLite automáticamente.



5️⃣ Ejecutar el juego


python timesplit_game.py


🧠 Ranking Glicko-2



El sistema Glicko-2 se aplica después de cada match y actualiza:



Rating

RD

Volatilidad

El ranking se puede:

📊 Consultar vía SQL

🎮 Visualizar directamente en el juego desde
“Ver Ranking (Glicko-2)”

📊 Consultas SQL (Informe)

El modelo de datos permite responder consultas como:

Top 10 jugadores por ranking global

Historial de partidas por jugador

Cambios de rating por match

Variación de rating en el último mes

Estadísticas por organización

Ranking femenino

Winrate por jugador

Distribución de rating por modo de juego

Todas las consultas se basan exclusivamente en Glicko-2.



📁 Estructura del proyecto

timesplit/
│
├── timesplit_game.py
├── requirements.txt
├── .env
├── assets/
│   └── dragon.png
├── venv/
└── README.md



🎓 Contexto académico

Proyecto desarrollado para una asignatura de Bases de Datos, cumpliendo con:

Modelado relacional

Persistencia real

Uso de PostgreSQL

❤️ Créditos

Desarrollado por Sebastian Acuña Concha y Matias Peterson Solis
Dragoncito Edition 🐉✨

Consultas SQL analíticas

Integración completa con una aplicación real
