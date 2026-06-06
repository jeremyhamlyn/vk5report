"""PSKReporter fetcher for a specific receiver callsign (VK5ARG)."""

import threading
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

from database import upsert_psk_spot, log_psk_fetch, freq_to_band
from grid import grid_to_latlon, is_valid_grid

API_URL    = "https://retrieve.pskreporter.info/query"
INTERVAL   = 300          # 5 minutes (PSKReporter minimum)
LOOKBACK   = -600         # last 10 minutes
CALLSIGNS  = ["VK5ARG", "VK5HW", "VK5COL"]
APPCONTACT = "vk5report@localhost"

_last_fetch = None
_running    = False
_thread     = None


def fetch_psk(rx_sign=CALLSIGNS[0], lookback=LOOKBACK):
    """Fetch PSKReporter spots for rx_sign as receiver. Returns (count, error)."""
    global _last_fetch
    params = {
        'receiverCallsign': rx_sign,
        'rronly':           '1',
        'flowStartSeconds': str(lookback),
        'appcontact':       APPCONTACT,
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=30,
                            headers={'Accept-Encoding': 'gzip'})
        resp.raise_for_status()
        count = _parse_and_store(resp.text, rx_sign)
        _last_fetch = datetime.utcnow()
        log_psk_fetch(rx_sign, count, 'ok')
        return count, None
    except Exception as e:
        log_psk_fetch(rx_sign, 0, 'error', str(e))
        return 0, str(e)


def _parse_and_store(xml_text, rx_sign):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log_psk_fetch(rx_sign, 0, 'parse_error', str(e))
        return 0

    count = 0
    for rr in root.iter('receptionReport'):
        a = rr.attrib
        rx_call = a.get('receiverCallsign', '').upper().strip()
        tx_call = a.get('senderCallsign',   '').upper().strip()
        if not rx_call or not tx_call:
            continue

        rx_loc = a.get('receiverLocator', '').upper().strip() or None
        tx_loc = a.get('senderLocator',   '').upper().strip() or None

        rx_lat, rx_lon = grid_to_latlon(rx_loc) if rx_loc and is_valid_grid(rx_loc) else (None, None)
        tx_lat, tx_lon = grid_to_latlon(tx_loc) if tx_loc and is_valid_grid(tx_loc) else (None, None)

        try:
            freq = int(a.get('frequency', 0)) or None
        except (ValueError, TypeError):
            freq = None

        try:
            snr = int(a.get('sNR', 0))
        except (ValueError, TypeError):
            snr = None

        # Convert unix timestamp to datetime string
        try:
            ts = int(a.get('flowStartSeconds', 0))
            from datetime import timezone
            spot_time = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            spot_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        band = freq_to_band(freq)

        upsert_psk_spot({
            'spot_time': spot_time,
            'rx_sign':   rx_call,
            'rx_loc':    rx_loc,
            'rx_lat':    rx_lat,
            'rx_lon':    rx_lon,
            'tx_sign':   tx_call,
            'tx_loc':    tx_loc,
            'tx_lat':    tx_lat,
            'tx_lon':    tx_lon,
            'frequency': freq,
            'band':      band,
            'mode':      a.get('mode') or None,
            'snr':       snr,
            'dxcc':      a.get('senderDXCC') or None,
            'region':    a.get('senderRegion') or None,
        })
        count += 1
    return count


def _loop():
    global _running
    while _running:
        for cs in CALLSIGNS:
            fetch_psk(cs)
        for _ in range(INTERVAL // 10):
            if not _running:
                break
            time.sleep(10)


def start():
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name='psk-arg-fetcher')
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
        'lookback_sec': LOOKBACK,
    }
