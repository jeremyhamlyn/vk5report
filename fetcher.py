"""Background PSKReporter fetcher — polls every 5 minutes."""

import threading
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

from database import upsert_report, log_fetch
from grid import grid_to_latlon, is_valid_grid

API_URL     = "https://retrieve.pskreporter.info/query"
INTERVAL    = 300          # 5 minutes (PSKReporter recommended minimum)
LOOKBACK    = -3600        # last 1 hour of data per fetch
APPCONTACT  = "vk5report@localhost"

_last_fetch  = None
_fetch_count = 0
_running     = False
_thread      = None


def fetch_once():
    global _last_fetch, _fetch_count
    params = {
        'receiverCallsign': 'VK5',
        'rronly':           '1',
        'flowStartSeconds': str(LOOKBACK),
        'appcontact':       APPCONTACT,
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=30,
                            headers={'Accept-Encoding': 'gzip'})
        resp.raise_for_status()
        count = _parse_and_store(resp.text)
        _last_fetch  = datetime.utcnow()
        _fetch_count += count
        log_fetch(count, 'ok')
        return count, None
    except Exception as e:
        log_fetch(0, 'error', str(e))
        return 0, str(e)


def _parse_and_store(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log_fetch(0, 'parse_error', str(e))
        return 0

    count = 0
    for rr in root.iter('receptionReport'):
        a = rr.attrib
        rx_call  = a.get('receiverCallsign', '').upper().strip()
        tx_call  = a.get('senderCallsign',   '').upper().strip()
        rx_grid  = a.get('receiverLocator',  '').upper().strip()
        tx_grid  = a.get('senderLocator',    '').upper().strip()

        if not rx_call or not tx_call:
            continue
        # Extra filter: only keep VK5 prefixes
        if not rx_call.startswith('VK5'):
            continue

        rx_lat, rx_lon = grid_to_latlon(rx_grid) if is_valid_grid(rx_grid) else (None, None)
        tx_lat, tx_lon = grid_to_latlon(tx_grid) if is_valid_grid(tx_grid) else (None, None)

        try:
            freq = int(a.get('frequency', 0))
        except (ValueError, TypeError):
            freq = None

        try:
            snr = int(a.get('sNR', 0))
        except (ValueError, TypeError):
            snr = None

        try:
            flow_start = int(a.get('flowStartSeconds', 0))
        except (ValueError, TypeError):
            flow_start = None

        upsert_report({
            'receiver_callsign': rx_call,
            'receiver_locator':  rx_grid  or None,
            'receiver_lat':      rx_lat,
            'receiver_lon':      rx_lon,
            'sender_callsign':   tx_call,
            'sender_locator':    tx_grid  or None,
            'sender_lat':        tx_lat,
            'sender_lon':        tx_lon,
            'frequency':         freq,
            'mode':              a.get('mode', None),
            'snr':               snr,
            'flow_start':        flow_start,
        })
        count += 1
    return count


def _loop():
    global _running
    while _running:
        fetch_once()
        # Sleep in 10-second increments so we can stop quickly
        for _ in range(INTERVAL // 10):
            if not _running:
                break
            time.sleep(10)


def start():
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name='psk-fetcher')
    _thread.start()


def stop():
    global _running
    _running = False


def status():
    return {
        'running':     _running,
        'last_fetch':  _last_fetch.strftime('%Y-%m-%d %H:%M:%S UTC') if _last_fetch else None,
        'total_stored': _fetch_count,
        'interval_sec': INTERVAL,
    }
