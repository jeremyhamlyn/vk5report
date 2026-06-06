"""
Parse the WIA Australian Repeater Directory extracted text and import to SQLite.
Run once: python3 repeater_import.py
"""

import re, os, sqlite3
from datetime import datetime

TXT = '/home/jsoh/.claude/projects/-home-jsoh/944ef925-6d1f-494f-9591-19c4ee18994e/tool-results/b2x9if9cq.txt'
DB  = os.path.join(os.path.dirname(__file__), 'data', 'vk5report.db')

STATUS = {'O', 'T', 'P', 'X', 'U', 'W'}

# ── Section detection ─────────────────────────────────────────────────────
# Match against the raw line (before stripping |) so "DMR | repeaters" works
SECTIONS = [
    (r'10.metre.*FM\s+repeater',  '10m FM'),
    (r'6.metre.*FM\s+r',          '6m FM'),
    (r'2.metre.*FM\s+repeater',   '2m FM'),
    (r'70.?cm.*FM\s+repeater',    '70cm FM'),
    (r'23.?cm.*FM\s+repeater',    '23cm FM'),
    (r'D[\s\-|]*Star\s+repeater', 'D-Star'),
    (r'APCO.*P25\s+repeater',     'P25'),
    (r'DMR\s*\|?\s*repeater',     'DMR'),
    (r'Fusion\s*\|?\s*repeater',  'Fusion'),
    (r'ATV\s*\|?\s*repeater',     'ATV'),
]

# ── Coordinate lookup ─────────────────────────────────────────────────────
# Checked against service area (lowercase substring) then location name
AREA_COORDS = [
    # Format: (substring, lat, lon)
    ('brokenhil',  -31.956,  141.454), ('mildura',   -34.209,  142.132),
    ('sydney',     -33.869,  151.209), ('melbourne', -37.814,  144.963),
    ('brisbane',   -27.470,  153.025), ('adelaide',  -34.929,  138.601),
    ('perth',      -31.951,  115.861), ('hobart',    -42.882,  147.327),
    ('darwin',     -12.463,  130.846), ('canberra',  -35.281,  149.130),
    ('goldcoast',  -28.017,  153.400), ('newcastle', -32.928,  151.782),
    ('wollongong', -34.428,  150.893), ('geelong',   -38.150,  144.362),
    ('townsville', -19.259,  146.817), ('cairns',    -16.919,  145.778),
    ('toowoomba',  -27.560,  151.951), ('ballarat',  -37.562,  143.850),
    ('bendigo',    -36.757,  144.280), ('launceston',-41.433,  147.144),
    ('albury',     -36.074,  146.914), ('wagga',     -35.108,  147.360),
    ('orange',     -33.283,  149.100), ('dubbo',     -32.257,  148.601),
    ('rockhampton',-23.379,  150.510), ('mackay',    -21.141,  149.186),
    ('bundaberg',  -24.866,  152.349), ('lismore',   -28.815,  153.279),
    ('gosford',    -33.424,  151.342), ('wyong',     -33.284,  151.430),
    ('taree',      -31.907,  152.457), ('kempsey',   -31.084,  152.836),
    ('nowra',      -34.877,  150.599), ('goulburn',  -34.755,  149.719),
    ('shepparton', -36.383,  145.398), ('warrnambool',-38.383, 142.485),
    ('traralgon',  -38.196,  146.540), ('bairnsdale',-37.844,  147.611),
    ('echuca',     -36.142,  144.760), ('hervey',    -25.299,  152.839),
    ('gladstone',  -23.843,  151.256), ('emerald',   -23.527,  148.162),
    ('roma',       -26.573,  148.787), ('mtgambier', -37.828,  140.783),
    ('naracoorte', -36.957,  140.738), ('whyalla',   -33.033,  137.567),
    ('portaug',    -32.493,  137.766), ('portpirie', -33.190,  138.017),
    ('renmark',    -34.173,  140.748), ('geraldton', -28.777,  114.615),
    ('albany',     -35.028,  117.884), ('bunbury',   -33.327,  115.641),
    ('kalgoorlie', -30.749,  121.466), ('broome',    -17.961,  122.236),
    ('esperance',  -33.861,  121.891), ('alice',     -23.698,  133.881),
    ('katherine',  -14.465,  132.267), ('mtisa',     -20.726,  139.493),
    ('longreach',  -23.443,  144.249), ('charleville',-26.403, 146.244),
    ('tamworth',   -31.090,  150.924), ('armidale',  -30.513,  151.670),
    ('inverell',   -29.770,  151.114), ('grafton',   -29.690,  152.938),
    ('coffs',      -30.296,  153.114), ('portmac',   -31.430,  152.909),
    ('taree',      -31.907,  152.457), ('bateman',   -35.709,  150.175),
    ('cooma',      -36.234,  149.131), ('devonport', -41.177,  146.357),
    ('burnie',     -41.058,  145.907), ('ipswich',   -27.617,  152.760),
    ('logan',      -27.639,  153.108), ('sunshine',  -26.650,  153.067),
    ('redcliffe',  -27.229,  153.100), ('gympie',    -26.189,  152.665),
    ('maryborough',-25.536,  152.702), ('yeppoon',   -23.130,  150.747),
    ('muswellbrook',-32.265, 150.889), ('cessnock',  -32.832,  151.355),
    ('maitland',   -32.731,  151.553), ('caloundra', -26.800,  153.133),
    ('noosa',      -26.383,  152.917), ('innisfail', -17.517,  146.033),
    ('atherton',   -17.267,  145.483), ('charters',  -20.074,  146.263),
    ('nhulunbuy',  -12.179,  136.772), ('tennant',   -19.650,  134.183),
    ('manjimup',   -34.242,  116.148), ('collie',    -33.366,  116.154),
    ('northam',    -31.649,  116.671), ('merredin',  -31.482,  118.276),
    ('bluemtn',    -33.717,  150.333), ('bluemount', -33.717,  150.333),
    ('blue mt',    -33.717,  150.333), ('wbluemtn',  -33.600,  150.200),
    ('centralcoast',-33.200, 151.400), ('centralwest',-33.000, 148.500),
    ('hunterval',  -32.800,  151.300), ('lowerhunter',-32.800, 151.300),
    ('lowerh',     -32.800,  151.300), ('upperhunter',-32.200, 150.900),
    ('illawarra',  -34.500,  150.900), ('shoalhaven', -35.000, 150.500),
    ('southernhigh',-34.500, 150.000),('riverina',   -35.500, 146.500),
    ('newengland', -30.000,  151.500), ('farwest',   -31.900,  141.400),
    ('latrobe',    -38.200,  146.500), ('gippsland', -37.800,  147.000),
    ('macedon',    -37.400,  144.570), ('mornington',-38.200,  145.100),
    ('barwon',     -38.200,  144.300), ('wimmera',   -36.500,  142.000),
    ('mallee',     -35.000,  143.000), ('goldfields',-36.800,  143.500),
    ('murray',     -36.000,  145.000), ('yarra',     -37.600,  145.300),
    ('darlingdown',-27.500,  151.900), ('seqld',     -27.500,  152.500),
    ('seqls',      -27.500,  152.500), ('nqld',      -19.300,  146.800),
    ('cqld',       -23.400,  148.500), ('sw wa',     -33.300,  115.600),
    ('midwest',    -28.000,  114.600), ('pilbara',   -22.000,  118.000),
    ('kimberley',  -17.000,  126.000), ('gascoyne',  -24.900,  113.700),
    ('wheatbelt',  -31.500,  117.000), ('hinterland',-28.300,  153.000),
    ('snowy',      -36.500,  148.500), ('actsensw',  -35.500,  149.000),
    ('sensw',      -36.500,  148.500), ('swh',       -35.100,  147.400),
    ('act',        -35.281,  149.130),
]

# Lookup keyed on location field (lowercase, stripped)
SITE_COORDS = {
    'isaacsridge': (-35.417, 149.083), 'mtginini':   (-35.529, 148.773),
    'mtsugarloaf': (-32.889, 151.516), 'olinda':     (-37.850, 145.370),
    'hillside':    (-37.680, 144.820), 'upwey':      (-37.900, 145.330),
    'berwick':     (-38.040, 145.350), 'glenwaverley':(-37.880,145.160),
    'mtdandenong': (-37.833, 145.367), 'mtmacedon':  (-37.400, 144.570),
    'mtbawbaw':    (-37.850, 146.283), 'mthotham':   (-36.990, 147.130),
    'mtbuffalo':   (-36.700, 146.800), 'mthigh':     (-37.100, 146.500),
    'mttamborine': (-27.983, 153.193), 'tamborine':  (-27.983, 153.193),
    'mtcoottha':   (-27.477, 152.968), 'mtglorious': (-27.330, 152.770),
    'mtnebo':      (-27.376, 152.800), 'oceanview':  (-27.300, 152.810),
    'greenhill':   (-27.810, 151.860), 'mtgravatt':  (-27.550, 153.070),
    'mtbindo':     (-33.500, 150.220), 'mtganghat':  (-31.770, 152.380),
    'mtcanobolas': (-33.283, 149.083), 'mtdarling':  (-31.956, 141.454),
    'mtyarrahapinni':(-30.817,152.750),'mtnardi':    (-28.730, 153.290),
    'mtwombat':    (-36.630, 145.460), 'specimenhill':(-36.760,144.290),
    'grundymtn':   (-30.870, 151.350), 'parrotsnest':(-28.810, 153.280),
    'maddensplains':(-34.500,150.800), 'highrange':  (-34.470, 150.400),
    'willanshill': (-35.110, 147.370), 'signalhill': (-34.760, 149.720),
    'nowrahill':   (-34.877, 150.599), 'terreyhill': (-33.690, 151.220),
    'terreyhills': (-33.690, 151.220), 'dural':      (-33.720, 151.000),
    'lawson':      (-33.720, 150.430), 'somersby':   (-33.380, 151.280),
    'kariong':     (-33.470, 151.270), 'baldhill':   (-27.490, 152.220),
    'mttiersmain': (-34.950, 138.720), 'mtlofty':    (-34.980, 138.710),
    'mtosmond':    (-34.920, 138.650), 'mtbarrow':   (-41.400, 147.370),
    'mtroland':    (-41.590, 146.240), 'mtarthur':   (-41.190, 146.790),
    'mtwellington':(-42.900, 147.230), 'mtnelson':   (-42.920, 147.330),
    'kunanyi':     (-42.900, 147.230), 'fern tree':  (-42.920, 147.280),
    'ridgeway':    (-42.890, 147.280), 'mtsaddleback':(-41.400,147.170),
    'kalamunda':   (-31.970, 116.050), 'bickley':    (-31.990, 116.070),
    'portable':    (None, None),
}

# Callsign prefix → state approximate centre
VK_CENTRE = {
    'VK1': (-35.281, 149.130), 'VK2': (-33.000, 147.000),
    'VK3': (-37.000, 144.500), 'VK4': (-25.000, 150.000),
    'VK5': (-33.500, 137.500), 'VK6': (-26.000, 121.000),
    'VK7': (-42.500, 147.000), 'VK8': (-20.000, 130.000),
}


def get_coords(loc, area, callsign):
    """Return (lat, lon) using best available lookup."""
    # 1. Specific site name
    key = re.sub(r'\s+', '', loc.lower())
    for k, v in SITE_COORDS.items():
        if key.startswith(k) or k in key:
            if v[0] is not None:
                return v
    # 2. Service area keyword
    sa = area.lower().replace(' ', '')
    for kw, lat, lon in AREA_COORDS:
        if kw.replace(' ', '') in sa:
            return lat, lon
    # 3. VK prefix fallback
    m = re.match(r'(VK\d)', callsign.upper())
    if m:
        return VK_CENTRE.get(m.group(1), (None, None))
    return None, None


def parse_records(txt_path):
    with open(txt_path, encoding='utf-8') as f:
        lines = f.readlines()

    cur_section = None
    records = []
    for raw in lines:
        line = raw.strip()
        # Detect section heading (check raw line)
        for pat, name in SECTIONS:
            if re.search(pat, line, re.I):
                cur_section = name
                break
        if not cur_section or '|' not in line:
            continue
        fields = [f.strip() for f in line.split('|')]
        if len(fields) < 6:
            continue
        if not re.match(r'^\d+\.', fields[0]):
            continue
        # Find status field position
        sp = None
        for i in range(3, min(9, len(fields))):
            if fields[i] in STATUS:
                sp = i
                break
        if sp is None:
            continue
        sa_parts = [f for f in fields[4:sp] if f and f != '-']
        sa = ' '.join(sa_parts)
        rem = fields[sp + 1:]

        def fval(lst, i):
            v = lst[i].strip() if i < len(lst) else ''
            return None if v in ('-', '') else v

        try:
            out_f = float(fields[0])
            inp_f = float(fields[1])
        except ValueError:
            continue

        callsign = fields[2].strip()
        lat, lon = get_coords(fields[3].strip(), sa, callsign)

        records.append({
            'mode_group':   cur_section,
            'output_freq':  out_f,
            'input_freq':   inp_f,
            'callsign':     callsign,
            'location':     fields[3].strip(),
            'service_area': sa,
            'status':       fields[sp],
            'erp':          fval(rem, 0),
            'hasl':         fval(rem, 1),
            'timeout':      fval(rem, 2),
            'sponsor':      fval(rem, 3),
            'tone':         fval(rem, 4),
            'notes':        ','.join(r for r in rem[5:] if r) or None,
            'lat':          lat,
            'lon':          lon,
        })
    return records


def import_to_db(records):
    conn = sqlite3.connect(DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS repeaters (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mode_group   TEXT NOT NULL,
            output_freq  REAL NOT NULL,
            input_freq   REAL,
            callsign     TEXT NOT NULL,
            location     TEXT,
            service_area TEXT,
            status       TEXT,
            erp          TEXT,
            hasl         TEXT,
            timeout      TEXT,
            sponsor      TEXT,
            tone         TEXT,
            notes        TEXT,
            lat          REAL,
            lon          REAL,
            imported_at  TEXT NOT NULL,
            UNIQUE(callsign, output_freq, mode_group)
        );
        CREATE INDEX IF NOT EXISTS idx_rep_mode ON repeaters(mode_group);
        CREATE INDEX IF NOT EXISTS idx_rep_call ON repeaters(callsign);
    """)
    conn.commit()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    inserted = 0
    for r in records:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO repeaters
                  (mode_group,output_freq,input_freq,callsign,location,service_area,
                   status,erp,hasl,timeout,sponsor,tone,notes,lat,lon,imported_at)
                VALUES
                  (:mode_group,:output_freq,:input_freq,:callsign,:location,:service_area,
                   :status,:erp,:hasl,:timeout,:sponsor,:tone,:notes,:lat,:lon,:now)
            """, {**r, 'now': now})
            inserted += 1
        except Exception as e:
            print(f"  skip {r['callsign']} {r['output_freq']}: {e}")
    conn.commit()
    conn.close()
    return inserted


if __name__ == '__main__':
    print('Parsing WIA repeater directory...')
    recs = parse_records(TXT)

    from collections import Counter
    modes = Counter(r['mode_group'] for r in recs)
    print(f'Parsed {len(recs)} records:')
    for m, c in sorted(modes.items()):
        print(f'  {m}: {c}')

    no_coords = sum(1 for r in recs if r['lat'] is None)
    print(f'  {no_coords} without coordinates ({len(recs)-no_coords} geocoded)')

    n = import_to_db(recs)
    print(f'Imported {n} records to database.')
