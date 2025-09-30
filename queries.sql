-- queries.sql — consultas útiles para timesplit.sqlite

-- 1) Estructura
PRAGMA table_info(sessions);
PRAGMA table_info(splits);

-- 2) Últimas 10 sesiones (todas)
SELECT id, player, mode, started_at, duration_ms, total_score
FROM sessions
ORDER BY started_at DESC
LIMIT 10;

-- 3) Leaderboard por modo (mejor puntaje por jugador)
-- (cambia 'carreras' por 'futbol' si quieres)
SELECT player, MAX(total_score) AS best_score
FROM sessions
WHERE mode = 'carreras'
GROUP BY player
ORDER BY best_score DESC
LIMIT 10;

-- 4) Splits de una sesión específica (reemplaza por tu id)
-- Ejemplo: s_ab12cd34
SELECT s.id AS split_id, s.session_id, s.t_ms, s.lap, s.score, s.note
FROM splits s
WHERE s.session_id = 's_ab12cd34'
ORDER BY s.t_ms ASC;

-- 5) Sesiones de un jugador (con su mejor por modo)
SELECT mode, MAX(total_score) AS best_score
FROM sessions
WHERE player = 'Jugador/a'
GROUP BY mode;

-- 6) Join sesiones + total de splits registrados por sesión
SELECT ses.id, ses.player, ses.mode, ses.total_score,
       COUNT(sp.id) AS num_splits
FROM sessions ses
LEFT JOIN splits sp ON sp.session_id = ses.id
GROUP BY ses.id
ORDER BY ses.started_at DESC
LIMIT 20;
