

# 🎮 TimeSplit Game — Glicko-2 Ranking System 🐉

**TimeSplit** es un videojuego desarrollado en **Python (Pygame)** que funciona como **generador de datos competitivos**.
Cada partida produce eventos temporales (*splits*) y un resultado final que se utiliza para actualizar un **ranking competitivo basado en Glicko-2**, persistido en **PostgreSQL** mediante **SQLAlchemy**.

Este proyecto integra **juego + base de datos + modelo matemático de ranking**, cumpliendo con requisitos académicos de modelado, persistencia y análisis.

---

## ✨ Características principales

* 🎮 Modos de juego:

  * **Carreras**
  * **Fútbol**
* ⏱️ Registro de **splits** en fracciones de tiempo configurables (50–1000 ms)
* 🐉 Personaje especial **Dragoncito** (con sprite opcional)
* 🧠 Sistema de ranking **Glicko-2 real**:

  * Rating
  * Rating Deviation (RD)
  * Volatilidad
* 🗄️ Persistencia en **PostgreSQL** (o SQLite fallback)
* 📦 Guardado de:

  * Jugadores
  * Sesiones de juego
  * Splits / eventos
  * Partidas (matches)
* 📤 Exportación a **CSV** y **Excel**
* 🏆 Ranking visual dentro del juego

---

## 🗂️ Estructura del proyecto

```
.
├── timesplit_game.py
├── requirements.txt
├── .env
├── assets/
│   ├── dragon.png        # opcional
│   ├── s_pick.wav        # opcional
│   ├── s_shoot.wav       # opcional
│   └── s_goal.wav        # opcional
```

---

## 🧰 Requisitos

* Python **3.10+**
* PostgreSQL (recomendado)
* Windows / macOS / Linux

---

## 📦 Instalación

### 1️⃣ Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
```

### 2️⃣ Crear entorno virtual

**Windows**

```bat
py -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3️⃣ Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuración del entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto:

```env
DATABASE_URL=postgresql://USUARIO:PASSWORD@HOST:5432/DBNAME
TSR_PLAYER=Jugador/a
```

### 🔹 Importante

* Si **no existe** `DATABASE_URL`, el sistema usará **SQLite local** automáticamente (`timesplit.sqlite`).
* Para evaluación formal se recomienda **PostgreSQL**.

---

## ▶️ Ejecución

```bash
python timesplit_game.py
```

Al iniciar:

* Se crean automáticamente todas las tablas necesarias.
* El juego queda listo para registrar partidas.

---

## 🎮 Controles

### Menú

* `↑ / ↓` → navegar
* `ENTER` → seleccionar
* `1..6` → elegir personaje
* `M` → mute
* `ESC` → salir

### En partida

* `ENTER` → nueva sesión
* `ESPACIO` → pausar
* `TAB` → cambiar modo
* `R` → reiniciar
* `L` → vuelta / periodo
* `[` `]` → ajustar tick de split
* `S` → **guardar sesión + actualizar Glicko-2**
* `E` → exportar CSV
* `X` → exportar Excel

### Carreras

* `↑ / ↓` → velocidad

### Fútbol

* Flechas → mover
* `F` → chutar

---

## 🗄️ Modelo de datos (resumen)

Tablas creadas automáticamente:

* `organizations`
* `players`
* `game_sessions`
* `splits`
* `matches`

Cada **partida del juego** genera:

1. Una sesión (`game_sessions`)
2. Múltiples splits (`splits`)
3. Un match (`matches`)
4. Actualización de **Glicko-2** en `players`

---

## 📊 Consultas útiles

### Ranking Glicko-2

```sql
SELECT name, rating, rd, vol
FROM players
ORDER BY rating DESC
LIMIT 10;
```

### Últimas sesiones

```sql
SELECT player_name, mode, total_score, duration_ms
FROM game_sessions
ORDER BY started_at DESC
LIMIT 10;
```

---

## 🐉 Dragoncito

Para usar sprite personalizado:

1. Crear carpeta `assets/`
2. Agregar:

   ```
   assets/dragon.png
   ```

Si no existe, el personaje se renderiza como figura simple.

---

## 🧠 Enfoque académico

Este proyecto demuestra:

* Integración **juego → datos → ranking matemático**
* Uso correcto de **Glicko-2**
* Persistencia relacional con **SQLAlchemy**
* Diseño reproducible y evaluable

> El videojuego actúa como generador de eventos competitivos que alimentan un sistema de ranking Glicko-2 persistente.


