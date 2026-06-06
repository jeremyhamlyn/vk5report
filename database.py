"""SQLite database layer for VK5 Report."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'vk5report.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wspr_spots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_time   TEXT NOT NULL,
            tx_sign     TEXT NOT NULL,
            tx_lat      REAL,
            tx_lon      REAL,
            tx_loc      TEXT,
            rx_sign     TEXT NOT NULL,
            rx_lat      REAL,
            rx_lon      REAL,
            rx_loc      TEXT,
            frequency   INTEGER,
            band        INTEGER,
            power       INTEGER,
            snr         INTEGER,
            drift       INTEGER,
            distance    INTEGER,
            azimuth     INTEGER,
            fetched_at  TEXT NOT NULL,
            UNIQUE(spot_time, tx_sign, rx_sign, frequency)
        );
        CREATE INDEX IF NOT EXISTS idx_wspr_tx   ON wspr_spots(tx_sign);
        CREATE INDEX IF NOT EXISTS idx_wspr_time ON wspr_spots(spot_time);
        CREATE TABLE IF NOT EXISTS wspr_fetch_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at  TEXT NOT NULL,
            tx_sign     TEXT,
            record_count INTEGER,
            status      TEXT,
            message     TEXT
        );
        CREATE TABLE IF NOT EXISTS psk_spots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_time   TEXT NOT NULL,
            rx_sign     TEXT NOT NULL,
            rx_loc      TEXT,
            rx_lat      REAL,
            rx_lon      REAL,
            tx_sign     TEXT NOT NULL,
            tx_loc      TEXT,
            tx_lat      REAL,
            tx_lon      REAL,
            frequency   INTEGER,
            band        INTEGER,
            mode        TEXT,
            snr         INTEGER,
            dxcc        TEXT,
            region      TEXT,
            fetched_at  TEXT NOT NULL,
            UNIQUE(rx_sign, tx_sign, frequency, spot_time)
        );
        CREATE INDEX IF NOT EXISTS idx_psk_rx   ON psk_spots(rx_sign);
        CREATE INDEX IF NOT EXISTS idx_psk_time ON psk_spots(spot_time);
        CREATE TABLE IF NOT EXISTS psk_fetch_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at   TEXT NOT NULL,
            rx_sign      TEXT,
            record_count INTEGER,
            status       TEXT,
            message      TEXT
        );
    """)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            receiver_callsign   TEXT NOT NULL,
            receiver_locator    TEXT,
            receiver_lat        REAL,
            receiver_lon        REAL,
            sender_callsign     TEXT NOT NULL,
            sender_locator      TEXT,
            sender_lat          REAL,
            sender_lon          REAL,
            frequency           INTEGER,
            mode                TEXT,
            snr                 INTEGER,
            flow_start          INTEGER,
            first_seen          TEXT NOT NULL,
            last_seen           TEXT NOT NULL,
            UNIQUE(receiver_callsign, sender_callsign, frequency, flow_start)
        );

        CREATE TABLE IF NOT EXISTS fetch_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at  TEXT NOT NULL,
            record_count INTEGER,
            status      TEXT,
            message     TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_receiver ON reports(receiver_callsign);
        CREATE INDEX IF NOT EXISTS idx_sender   ON reports(sender_callsign);
        CREATE INDEX IF NOT EXISTS idx_last_seen ON reports(last_seen);
    """)
    conn.commit()
    conn.close()


def upsert_report(r):
    """Insert or update a reception report. r is a dict."""
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO reports
                (receiver_callsign, receiver_locator, receiver_lat, receiver_lon,
                 sender_callsign, sender_locator, sender_lat, sender_lon,
                 frequency, mode, snr, flow_start, first_seen, last_seen)
            VALUES
                (:receiver_callsign, :receiver_locator, :receiver_lat, :receiver_lon,
                 :sender_callsign, :sender_locator, :sender_lat, :sender_lon,
                 :frequency, :mode, :snr, :flow_start, :now, :now)
            ON CONFLICT(receiver_callsign, sender_callsign, frequency, flow_start)
            DO UPDATE SET
                last_seen        = :now,
                snr              = :snr,
                receiver_locator = COALESCE(:receiver_locator, receiver_locator),
                receiver_lat     = COALESCE(:receiver_lat,     receiver_lat),
                receiver_lon     = COALESCE(:receiver_lon,     receiver_lon),
                sender_locator   = COALESCE(:sender_locator,   sender_locator),
                sender_lat       = COALESCE(:sender_lat,       sender_lat),
                sender_lon       = COALESCE(:sender_lon,       sender_lon)
        """, {**r, 'now': now})
        conn.commit()
    finally:
        conn.close()


def log_fetch(count, status, message=''):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    conn.execute(
        "INSERT INTO fetch_log (fetched_at, record_count, status, message) VALUES (?,?,?,?)",
        (now, count, status, message)
    )
    conn.commit()
    conn.close()


def get_last_fetch():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM fetch_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_reports(limit=500, offset=0, receiver=None, sender=None, mode=None):
    conn = get_conn()
    where, params = [], []
    if receiver:
        where.append("receiver_callsign LIKE ?")
        params.append(f"%{receiver}%")
    if sender:
        where.append("sender_callsign LIKE ?")
        params.append(f"%{sender}%")
    if mode:
        where.append("mode = ?")
        params.append(mode)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM reports {clause} ORDER BY last_seen DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) FROM reports {clause}", params
    ).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_map_data():
    """Return data for the map: all unique VK5 receivers + their senders."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            receiver_callsign, receiver_locator, receiver_lat, receiver_lon,
            sender_callsign,   sender_locator,   sender_lat,   sender_lon,
            frequency, mode, snr, last_seen
        FROM reports
        WHERE receiver_lat IS NOT NULL
          AND receiver_lon IS NOT NULL
          AND sender_lat IS NOT NULL
          AND sender_lon IS NOT NULL
        ORDER BY last_seen DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    stats = {}
    stats['total_reports']   = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    stats['vk5_receivers']   = conn.execute(
        "SELECT COUNT(DISTINCT receiver_callsign) FROM reports").fetchone()[0]
    stats['unique_senders']  = conn.execute(
        "SELECT COUNT(DISTINCT sender_callsign) FROM reports").fetchone()[0]
    stats['modes']           = [dict(r) for r in conn.execute(
        "SELECT mode, COUNT(*) as cnt FROM reports GROUP BY mode ORDER BY cnt DESC").fetchall()]
    stats['top_receivers']   = [dict(r) for r in conn.execute(
        "SELECT receiver_callsign, COUNT(*) as cnt FROM reports "
        "GROUP BY receiver_callsign ORDER BY cnt DESC LIMIT 10").fetchall()]
    conn.close()
    return stats


def get_modes():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT mode FROM reports WHERE mode IS NOT NULL ORDER BY mode"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ── WSPR spot functions ────────────────────────────────────────────────────

def upsert_wspr_spot(s):
    """Insert or ignore a WSPR spot. s is a dict."""
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO wspr_spots
                (spot_time, tx_sign, tx_lat, tx_lon, tx_loc,
                 rx_sign, rx_lat, rx_lon, rx_loc,
                 frequency, band, power, snr, drift, distance, azimuth, fetched_at)
            VALUES
                (:spot_time, :tx_sign, :tx_lat, :tx_lon, :tx_loc,
                 :rx_sign, :rx_lat, :rx_lon, :rx_loc,
                 :frequency, :band, :power, :snr, :drift, :distance, :azimuth, :fetched_at)
        """, {**s, 'fetched_at': now})
        conn.commit()
    finally:
        conn.close()


def log_wspr_fetch(tx_sign, count, status, message=''):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    conn.execute(
        "INSERT INTO wspr_fetch_log (fetched_at, tx_sign, record_count, status, message) VALUES (?,?,?,?,?)",
        (now, tx_sign, count, status, message)
    )
    conn.commit()
    conn.close()


def get_last_wspr_fetch(tx_sign=None):
    conn = get_conn()
    if tx_sign:
        row = conn.execute(
            "SELECT * FROM wspr_fetch_log WHERE tx_sign=? ORDER BY id DESC LIMIT 1", (tx_sign,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM wspr_fetch_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_wspr_spots(rx_sign, minutes=10, limit=200):
    """Return WSPR spots heard by a given RX callsign in the last N minutes."""
    conn = get_conn()
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    rows = conn.execute(
        """SELECT * FROM wspr_spots
           WHERE rx_sign=? AND spot_time >= ?
           ORDER BY spot_time DESC LIMIT ?""",
        (rx_sign, cutoff, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_wspr_map_data(rx_signs, start_minutes=60, end_minutes=0):
    """Return WSPR spots heard by one or more rx_signs with valid tx lat/lon.
    start_minutes: how far back the window begins (older boundary).
    end_minutes:   how far back the window ends (0 = now)."""
    conn = get_conn()
    from datetime import timedelta
    now = datetime.utcnow()
    cutoff_from = (now - timedelta(minutes=start_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    cutoff_to   = (now - timedelta(minutes=end_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(rx_signs, str):
        rx_signs = [rx_signs]
    placeholders = ','.join('?' * len(rx_signs))
    rows = conn.execute(
        f"""SELECT * FROM wspr_spots
           WHERE rx_sign IN ({placeholders})
             AND spot_time >= ? AND spot_time <= ?
             AND tx_lat IS NOT NULL AND tx_lon IS NOT NULL
           ORDER BY spot_time DESC""",
        rx_signs + [cutoff_from, cutoff_to]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_wspr_snr_history(rx_sign, minutes=180):
    """Return SNR time-series for WSPR spots received by rx_sign, ordered oldest-first.
    For windows > 6 h, buckets into 10-min intervals (max SNR per bucket) to keep
    the point count manageable for charting."""
    from datetime import timedelta
    conn = get_conn()
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    if minutes <= 360:
        rows = conn.execute(
            """SELECT spot_time, snr, tx_sign, band FROM wspr_spots
               WHERE rx_sign=? AND spot_time>=? AND snr IS NOT NULL
               ORDER BY spot_time ASC""",
            (rx_sign, cutoff)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT
                 strftime('%Y-%m-%d %H:', spot_time) ||
                 printf('%02d', (CAST(strftime('%M', spot_time) AS INTEGER) / 10) * 10) || ':00' AS spot_time,
                 MAX(snr) AS snr, '' AS tx_sign, NULL AS band
               FROM wspr_spots
               WHERE rx_sign=? AND spot_time>=? AND snr IS NOT NULL
               GROUP BY strftime('%Y-%m-%d %H:%M', spot_time, 'start of minute',
                 printf('-%d minutes', CAST(strftime('%M', spot_time) AS INTEGER) % 10))
               ORDER BY spot_time ASC""",
            (rx_sign, cutoff)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_wspr_rx_stations():
    """Return all distinct rx_signs that have stored WSPR spots."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT rx_sign FROM wspr_spots ORDER BY rx_sign"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_wspr_stats(rx_sign):
    conn = get_conn()
    total   = conn.execute("SELECT COUNT(*) FROM wspr_spots WHERE rx_sign=?", (rx_sign,)).fetchone()[0]
    recent  = conn.execute(
        "SELECT COUNT(*) FROM wspr_spots WHERE rx_sign=? AND spot_time >= datetime('now','-10 minutes')",
        (rx_sign,)
    ).fetchone()[0]
    max_dist = conn.execute(
        "SELECT MAX(distance) FROM wspr_spots WHERE rx_sign=? AND spot_time >= datetime('now','-10 minutes')",
        (rx_sign,)
    ).fetchone()[0]
    conn.close()
    return {'total': total, 'recent_10min': recent, 'max_distance_km': max_dist}


# ── PSK spot functions (VK5ARG as receiver) ───────────────────────────────

# ── Repeater directory functions ──────────────────────────────────────────

def get_repeaters(mode_group=None, status=None):
    """Return repeater records, optionally filtered by mode_group and/or status."""
    conn = get_conn()
    where, params = [], []
    if mode_group:
        where.append("mode_group = ?")
        params.append(mode_group)
    if status:
        where.append("status = ?")
        params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM repeaters {clause} ORDER BY output_freq", params
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_repeater_modes():
    """Return list of distinct mode_groups in the repeaters table."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT mode_group FROM repeaters ORDER BY mode_group"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ─────────────────────────────────────────────────────────────────────────

def freq_to_band(freq_hz):
    """Convert frequency in Hz to WSPR-compatible band integer."""
    if freq_hz is None:
        return None
    mhz = freq_hz / 1e6
    if mhz < 0.5:   return -1
    if mhz < 2.0:   return 0
    if mhz < 2.5:   return 1
    if mhz < 4.0:   return 3
    if mhz < 6.0:   return 5
    if mhz < 8.0:   return 7
    if mhz < 12.0:  return 10
    if mhz < 16.0:  return 14
    if mhz < 20.0:  return 18
    if mhz < 22.0:  return 21
    if mhz < 26.0:  return 24
    if mhz < 40.0:  return 28
    if mhz < 60.0:  return 50
    if mhz < 100.0: return 70
    if mhz < 200.0: return 144
    if mhz < 500.0: return 432
    return 1296


def upsert_psk_spot(s):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO psk_spots
                (spot_time, rx_sign, rx_loc, rx_lat, rx_lon,
                 tx_sign, tx_loc, tx_lat, tx_lon,
                 frequency, band, mode, snr, dxcc, region, fetched_at)
            VALUES
                (:spot_time, :rx_sign, :rx_loc, :rx_lat, :rx_lon,
                 :tx_sign, :tx_loc, :tx_lat, :tx_lon,
                 :frequency, :band, :mode, :snr, :dxcc, :region, :fetched_at)
        """, {**s, 'fetched_at': now})
        conn.commit()
    finally:
        conn.close()


def log_psk_fetch(rx_sign, count, status, message=''):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    conn.execute(
        "INSERT INTO psk_fetch_log (fetched_at, rx_sign, record_count, status, message) VALUES (?,?,?,?,?)",
        (now, rx_sign, count, status, message)
    )
    conn.commit()
    conn.close()


def get_last_psk_fetch(rx_sign=None):
    conn = get_conn()
    if rx_sign:
        row = conn.execute(
            "SELECT * FROM psk_fetch_log WHERE rx_sign=? ORDER BY id DESC LIMIT 1", (rx_sign,)
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM psk_fetch_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_psk_spots(rx_sign, minutes=10, limit=300):
    conn = get_conn()
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    rows = conn.execute(
        """SELECT * FROM psk_spots
           WHERE rx_sign=? AND spot_time >= ?
           ORDER BY spot_time DESC LIMIT ?""",
        (rx_sign, cutoff, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_psk_map_data(rx_signs, start_minutes=60, end_minutes=0):
    """Return PSK spots heard by one or more rx_signs with valid tx lat/lon.
    start_minutes: how far back the window begins (older boundary).
    end_minutes:   how far back the window ends (0 = now)."""
    conn = get_conn()
    from datetime import timedelta
    now = datetime.utcnow()
    cutoff_from = (now - timedelta(minutes=start_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    cutoff_to   = (now - timedelta(minutes=end_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(rx_signs, str):
        rx_signs = [rx_signs]
    placeholders = ','.join('?' * len(rx_signs))
    rows = conn.execute(
        f"""SELECT * FROM psk_spots
           WHERE rx_sign IN ({placeholders})
             AND spot_time >= ? AND spot_time <= ?
             AND tx_lat IS NOT NULL AND tx_lon IS NOT NULL
           ORDER BY spot_time DESC""",
        rx_signs + [cutoff_from, cutoff_to]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_psk_stats(rx_sign):
    conn = get_conn()
    total  = conn.execute("SELECT COUNT(*) FROM psk_spots WHERE rx_sign=?", (rx_sign,)).fetchone()[0]
    recent = conn.execute(
        "SELECT COUNT(*) FROM psk_spots WHERE rx_sign=? AND spot_time >= datetime('now','-10 minutes')",
        (rx_sign,)
    ).fetchone()[0]
    max_dist = conn.execute(
        """SELECT MAX(
             ROUND(6371 * ACOS(
               SIN(RADIANS(rx_lat)) * SIN(RADIANS(tx_lat)) +
               COS(RADIANS(rx_lat)) * COS(RADIANS(tx_lat)) *
               COS(RADIANS(tx_lon - rx_lon))
             ))
           ) FROM psk_spots
           WHERE rx_sign=? AND spot_time >= datetime('now','-10 minutes')
             AND rx_lat IS NOT NULL AND tx_lat IS NOT NULL""",
        (rx_sign,)
    ).fetchone()[0]
    modes = [dict(r) for r in conn.execute(
        """SELECT mode, COUNT(*) as cnt FROM psk_spots WHERE rx_sign=?
           AND spot_time >= datetime('now','-10 minutes')
           GROUP BY mode ORDER BY cnt DESC LIMIT 8""",
        (rx_sign,)
    ).fetchall()]
    conn.close()
    return {'total': total, 'recent_10min': recent,
            'max_distance_km': int(max_dist) if max_dist else None, 'modes': modes}
