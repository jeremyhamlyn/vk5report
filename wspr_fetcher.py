"""WSPR spot fetcher from wspr.live ClickHouse API."""

import threading
import time
import requests
from datetime import datetime, timezone

from database import upsert_wspr_spot, log_wspr_fetch

API_URL   = "http://db1.wspr.live/"
INTERVAL   = 120          # fetch every 2 minutes
LOOKBACK   = 10           # minutes of data to request
CALLSIGNS  = ["VK5ARG", "VK5HW"]

_last_fetch  = None
_running     = False
_thread      = None


def _build_query(rx_sign, minutes=10):
    return (
        f"SELECT id, time, band, rx_sign, rx_lat, rx_lon, rx_loc, "
        f"tx_sign, tx_lat, tx_lon, tx_loc, distance, azimuth, "
        f"frequency, power, snr, drift "
        f"FROM wspr.rx "
        f"WHERE rx_sign='{rx_sign}' "
        f"AND time >= now() - INTERVAL {minutes} MINUTE "
        f"ORDER BY time DESC "
        f"FORMAT JSON"
    )


def fetch_wspr(rx_sign=CALLSIGNS[0], minutes=LOOKBACK):
    """Fetch WSPR spots heard by a given receiver callsign. Returns (count, error)."""
    global _last_fetch
    query = _build_query(rx_sign, minutes)
    try:
        resp = requests.get(API_URL, params={'query': query}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get('data', [])
        count = 0
        for r in rows:
            upsert_wspr_spot({
                'spot_time':  r.get('time'),
                'tx_sign':    r.get('tx_sign', '').upper(),
                'tx_lat':     r.get('tx_lat'),
                'tx_lon':     r.get('tx_lon'),
                'tx_loc':     r.get('tx_loc'),
                'rx_sign':    r.get('rx_sign', '').upper(),
                'rx_lat':     r.get('rx_lat'),
                'rx_lon':     r.get('rx_lon'),
                'rx_loc':     r.get('rx_loc'),
                'frequency':  r.get('frequency'),
                'band':       r.get('band'),
                'power':      r.get('power'),
                'snr':        r.get('snr'),
                'drift':      r.get('drift'),
                'distance':   r.get('distance'),
                'azimuth':    r.get('azimuth'),
            })
            count += 1
        _last_fetch = datetime.utcnow()
        log_wspr_fetch(rx_sign, count, 'ok')
        return count, None
    except Exception as e:
        log_wspr_fetch(rx_sign, 0, 'error', str(e))
        return 0, str(e)


def _loop():
    global _running
    while _running:
        for cs in CALLSIGNS:
            fetch_wspr(cs)
        for _ in range(INTERVAL // 5):
            if not _running:
                break
            time.sleep(5)


def start():
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name='wspr-fetcher')
    _thread.start()


def stop():
    global _running
    _running = False


def status():
    return {
        'running':      _running,
        'last_fetch':   _last_fetch.strftime('%Y-%m-%d %H:%M:%S UTC') if _last_fetch else None,
        'interval_sec': INTERVAL,
        'callsigns':    CALLSIGNS,
        'lookback_min': LOOKBACK,
    }
