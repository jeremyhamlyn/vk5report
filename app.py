#!/usr/bin/env python3
"""VK5 Report — PSKReporter + WSPR dashboard for multiple VK5 receivers."""

import threading
from flask import Flask, render_template, jsonify, request

import database
import fetcher        # PSKReporter all-VK5 background fetcher
import wspr_fetcher   # WSPR RX fetcher (multi-station)
import psk_fetcher    # PSKReporter RX fetcher (multi-station)

app = Flask(__name__)

STATIONS      = ['VK5ARG', 'VK5HW']
WSPR_STATIONS = ['VK5ARG', 'VK5HW']   # up to 12 WSPR receiver callsigns

# Init DB and start background fetchers
database.init_db()
fetcher.start()
wspr_fetcher.CALLSIGNS = WSPR_STATIONS  # keep fetcher in sync with station list
wspr_fetcher.start()
psk_fetcher.start()

# Immediate first fetches for all stations
for _cs in STATIONS:
    threading.Thread(target=psk_fetcher.fetch_psk, args=(_cs,), daemon=True).start()
for _cs in WSPR_STATIONS:
    threading.Thread(target=wspr_fetcher.fetch_wspr, args=(_cs,), daemon=True).start()
threading.Thread(target=fetcher.fetch_once, daemon=True).start()


# ── Pages ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return data_page()


@app.route('/data')
def data_page():
    stations_data = {}
    # PSK stations
    for cs in STATIONS:
        stations_data[cs] = {
            'psk_spots': database.get_psk_spots(cs, minutes=10),
            'psk_stats': database.get_psk_stats(cs),
            'psk_last':  database.get_last_psk_fetch(cs),
        }
    # WSPR stations (may overlap with or differ from STATIONS)
    for cs in WSPR_STATIONS:
        entry = stations_data.setdefault(cs, {})
        entry['wspr_spots'] = database.get_wspr_spots(cs, minutes=10)
        entry['wspr_stats'] = database.get_wspr_stats(cs)
        entry['wspr_last']  = database.get_last_wspr_fetch(cs)

    return render_template('data.html',
        stations=STATIONS,
        wspr_stations=WSPR_STATIONS,
        stations_data=stations_data,
        psk_fetcher_status=psk_fetcher.status(),
        wspr_fetcher_status=wspr_fetcher.status(),
        fetcher_status=psk_fetcher.status(),
    )


@app.route('/repeaters')
def repeaters_page():
    return render_template('repeaters.html',
        fetcher_status=psk_fetcher.status(),
    )


@app.route('/api/repeaters')
def api_repeaters():
    mode = request.args.get('mode', '')
    rows = database.get_repeaters(mode_group=mode if mode else None)
    return jsonify(rows)


@app.route('/map')
def map_page():
    return render_template('map.html',
        stations=STATIONS,
        wspr_stations=WSPR_STATIONS,
        fetcher_status=psk_fetcher.status(),
    )


# ── APIs ─────────────────────────────────────────────────────────────────

@app.route('/api/wspr-snr-chart')
def api_wspr_snr_chart():
    rx      = request.args.get('rx', '')
    minutes = min(int(request.args.get('minutes', 180)), 10080)
    if not rx:
        return jsonify([])
    return jsonify(database.get_wspr_snr_history(rx, minutes))


@app.route('/api/wspr-rx-stations')
def api_wspr_rx_stations():
    return jsonify(database.get_wspr_rx_stations())


@app.route('/api/wspr-spots')
def api_wspr_spots():
    start = min(int(request.args.get('start', 60)), 1440)
    end   = max(min(int(request.args.get('end',   0)), 1440), 0)
    if end >= start:
        end = 0
    return jsonify(database.get_wspr_map_data(WSPR_STATIONS, start_minutes=start, end_minutes=end))


@app.route('/api/psk-spots')
def api_psk_spots():
    start = min(int(request.args.get('start', 60)), 1440)
    end   = max(min(int(request.args.get('end',   0)), 1440), 0)
    if end >= start:
        end = 0
    return jsonify(database.get_psk_map_data(STATIONS, start_minutes=start, end_minutes=end))


@app.route('/api/fetch-now', methods=['POST'])
def api_fetch_now():
    for cs in STATIONS:
        threading.Thread(target=psk_fetcher.fetch_psk, args=(cs,), daemon=True).start()
    for cs in WSPR_STATIONS:
        threading.Thread(target=wspr_fetcher.fetch_wspr, args=(cs,), daemon=True).start()
    threading.Thread(target=fetcher.fetch_once, daemon=True).start()
    return jsonify({'ok': True})


@app.route('/api/stats')
def api_stats():
    return jsonify({
        'stations': {cs: {
            'psk':  database.get_psk_stats(cs),
            'wspr': database.get_wspr_stats(cs),
        } for cs in STATIONS},
        'psk_fetcher':  psk_fetcher.status(),
        'wspr_fetcher': wspr_fetcher.status(),
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8079, debug=False)
