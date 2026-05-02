from flask import Flask, render_template, request, jsonify
import swisseph as swe
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__, template_folder="templates")

# ====================== SWISS EPHEMERIS ======================
# EPHE_DIR = os.path.join(os.getcwd(), "ephe")
# os.makedirs(EPHE_DIR, exist_ok=True)

# BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"
# 

EPHE_DIR = os.path.join(os.path.dirname(__file__), "ephe")
#swe.set_ephe_path(EPHE_DIR)
swe.set_ephe_path(os.path.abspath("ephe"))
swe.set_sid_mode(swe.SIDM_LAHIRI)
files = ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]

for fname in files:
    target = os.path.join(EPHE_DIR, fname)
    if not os.path.exists(target):
        r = requests.get(BASE_URL + fname)
        if r.status_code == 200:
            with open(target, "wb") as f:
                f.write(r.content)

swe.set_ephe_path(EPHE_DIR)
swe.set_sid_mode(swe.SIDM_LAHIRI)

# from flask import Flask, render_template, request, jsonify
# import swisseph as swe
# import os
# import requests
# from datetime import datetime, timedelta

# app = Flask(__name__)

# # ====================== SWISS EPHEMERIS ======================
# EPHE_DIR = os.path.join(os.getcwd(), "ephe")
# os.makedirs(EPHE_DIR, exist_ok=True)

# BASE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/"
# files = ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]

# for fname in files:
#     target = os.path.join(EPHE_DIR, fname)
#     if not os.path.exists(target):
#         r = requests.get(BASE_URL + fname)
#         if r.status_code == 200:
#             with open(target, "wb") as f:
#                 f.write(r.content)

# swe.set_ephe_path(EPHE_DIR)
# swe.set_sid_mode(swe.SIDM_LAHIRI)

SIGNS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]

def lon_to_str(lon):
    deg = lon % 30
    sign = SIGNS[int(lon // 30) % 12]
    return f"{deg:.2f}° {sign}"

PLANETS = {
    "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY,
    "venus": swe.VENUS, "mars": swe.MARS, "jupiter": swe.JUPITER,
    "saturn": swe.SATURN, "truenode": swe.TRUE_NODE
}

PLANET_MEANINGS = {
    "sun":       "authority / career",
    "moon":      "emotions",
    "mercury":   "communication",
    "venus":     "relationships",
    "mars":      "action",
    "jupiter":   "growth",
    "saturn":    "career / karma",
    "truenode":  "sudden events",
    "southnode": "past karma",
}

def get_positions(dt):
    jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
    pos = {}
    for name, pid in PLANETS.items():
        pos[name] = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL)[0][0]
    north = swe.calc_ut(jd, swe.MEAN_NODE, swe.FLG_SIDEREAL)[0][0]
    pos["southnode"] = (north + 180) % 360
    return pos

def get_closest_hit(planet_lon, axis_points, orb):
    min_orb = float('inf')
    for p in axis_points:
        diff = abs((planet_lon - p) % 360)
        distance = min(diff, 360 - diff)
        if distance < min_orb:
            min_orb = distance
    return min_orb <= orb, round(min_orb, 2)

def classify_event(pos, axis_points, config):
    trigger_list = []
    moon_list = []
    bg_list = []

    # Trigger Planets
    for p in ['sun', 'venus', 'mercury', 'mars']:
        if config.get(f'include_{p}', True):
            hit, orb_dist = get_closest_hit(pos[p], axis_points, config.get('orb_trigger', 8))
            if hit:
                trigger_list.append(f"{p.capitalize()} {lon_to_str(pos[p])} ({orb_dist}°)")

    # Moon
    if config.get('include_moon', True):
        m_hit, m_orb = get_closest_hit(pos['moon'], axis_points, config.get('orb_moon', 4))
        if m_hit:
            moon_list.append(f"Moon {lon_to_str(pos['moon'])} ({m_orb}°)")

    # Background
    for p in ['jupiter', 'saturn', 'truenode', 'southnode']:
        if config.get(f'include_{p}', True):
            hit, orb_dist = get_closest_hit(pos[p], axis_points, config.get('orb_bg', 12))
            if hit:
                name = "Rahu" if p == "truenode" else "Ketu" if p == "southnode" else p.capitalize()
                bg_list.append(f"{name} {lon_to_str(pos[p])} ({orb_dist}°)")

    trigger_str = " | ".join(trigger_list) if trigger_list else "—"
    moon_str = " | ".join(moon_list) if moon_list else "—"
    bg_str = " | ".join(bg_list) if bg_list else "—"

    trigger_ok = bool(trigger_list)
    moon_ok = bool(moon_list)
    bg_ok = bool(bg_list)

    if trigger_ok and moon_ok and bg_ok:
        strength = "FINAL_EVENT"
    elif trigger_ok and bg_ok:
        strength = "EVENT_WINDOW"
    elif moon_ok and bg_ok:
        strength = "MOVEMENT"
    else:
        strength = "NO_EVENT"

    # Return separate fields for trigger, moon, background
    return strength, trigger_str, moon_str, bg_str

PLANET_DISPLAY = {
    "sun": "Sun", "moon": "Moon", "mercury": "Mercury",
    "venus": "Venus", "mars": "Mars", "jupiter": "Jupiter",
    "saturn": "Saturn", "truenode": "Rahu"
}

PLANET_MEANINGS = {
    "sun":       "authority / career",
    "moon":      "emotions",
    "mercury":   "communication",
    "venus":     "relationships",
    "mars":      "action",
    "jupiter":   "growth",
    "saturn":    "career / karma",
    "truenode":  "sudden events",
    "southnode": "past karma",
}

# ====================== SCORING & CLASSIFICATION ======================

PLANET_WEIGHTS = {
    'venus':     30,
    'moon':      25,
    'mercury':   20,
    'mars':      20,
    'sun':       20,
    'jupiter':   15,
    'saturn':    15,
    'truenode':  10,
    'southnode': 10,
}

EVENT_TYPE_MAP = {
    'venus':   'Agreement / Offer',
    'mercury': 'Communication',
    'mars':    'Action / Conflict',
    'sun':     'Decision / Authority',
}

def compute_score_and_classification(trigger_hits, moon_hits, bg_hits):
    """
    Given lists of hit dicts (each has 'planet' key as display name or raw key),
    compute total score and return (score, classification, event_type).
    """
    # Build a reverse map from display name to planet key
    DISPLAY_TO_KEY = {v: k for k, v in PLANET_DISPLAY.items()}
    DISPLAY_TO_KEY['Rahu'] = 'truenode'
    DISPLAY_TO_KEY['Ketu'] = 'southnode'

    score = 0
    trigger_planet_keys = []

    all_hits = trigger_hits + moon_hits + bg_hits
    for hit in all_hits:
        pname = hit.get('planet', '')
        pkey = DISPLAY_TO_KEY.get(pname, pname.lower())
        score += PLANET_WEIGHTS.get(pkey, 0)
        if pkey in EVENT_TYPE_MAP:
            trigger_planet_keys.append(pkey)

    trigger_ok = bool(trigger_hits)
    moon_ok    = bool(moon_hits)
    bg_ok      = bool(bg_hits)

    # Classification — bucket presence takes priority over score
    if trigger_ok and moon_ok and bg_ok:
        classification = 'FINAL_EVENT'
    elif trigger_ok and bg_ok:
        classification = 'STRONG_EVENT'
    elif moon_ok and bg_ok:
        classification = 'MOVEMENT'
    else:
        classification = 'NO_EVENT'

    # Event type — use the first matched trigger planet
    event_type = ''
    for pk in trigger_planet_keys:
        if pk in EVENT_TYPE_MAP:
            event_type = EVENT_TYPE_MAP[pk]
            break

    return score, classification, event_type


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/natal', methods=['POST'])
def natal():
    data = request.get_json()
    dob = data.get('dob', '1990-01-22')
    tob = data.get('tob', '17:35')
    utc_offset = float(data.get('utcOffset', 5.5))   # hours, e.g. 5.5 for IST
    place      = data.get('place', '')

    try:
        dt_local = datetime.fromisoformat(f"{dob}T{tob}:00")
        # Convert local birth time to UTC for ephemeris calculation
        dt = dt_local - timedelta(hours=utc_offset)
    except Exception:
        return jsonify({"error": "Invalid date/time"}), 400

    pos = get_positions(dt)
    natal_out = {k: {"longitude": round(v, 4), "display": lon_to_str(v)}
                 for k, v in pos.items()}

    # Build axis for every natal planet — all 12 aspects (0-330 in 30° steps)
    ALL_ASPECTS = {
        "0° ": 0,
        "30° ": 30,
        "60° ": 60,
        "90° ": 90,
        "120° ": 120,
        "150° ": 150,
        "180° ": 180,
        "210° ": 210,
        "240° ": 240,
        "270° ": 270,
        "300° ": 300,
        "330° ": 330,
    }
    all_axes = {}
    for planet_key, lon in pos.items():
        all_axes[planet_key] = {
            label: round((lon + offset) % 360, 4)
            for label, offset in ALL_ASPECTS.items()
        }

    return jsonify({"natal": natal_out, "all_axes": all_axes})

@app.route('/scan', methods=['POST'])
def scan():
    data = request.get_json()

    all_axes_full    = data.get('allAxes', {})
    selected_aspects = set(data.get('selectedAspects', []))  # e.g. {"0","120","180"}
    # Filter each natal planet's axis to only selected aspect offsets
    all_axes = {}
    for natal_p, aspect_map in all_axes_full.items():
        filtered = {label: lon for label, lon in aspect_map.items()
                    if not selected_aspects or any(label.startswith(f"{a}°") or label.startswith(f"{a} ") for a in selected_aspects)}
        if filtered:
            all_axes[natal_p] = filtered

    selected_planets = data.get('selectedPlanets', list(PLANET_DISPLAY.keys()))
    orb_trigger = float(data.get('orbTrigger', 1.0))
    orb_moon    = float(data.get('orbMoon', 1.0))
    orb_bg      = float(data.get('orbBg', 1.0))
    PLANET_ORB = {
        'sun': orb_trigger, 'mercury': orb_trigger, 'venus': orb_trigger, 'mars': orb_trigger,
        'moon': orb_moon,
        'jupiter': orb_bg, 'saturn': orb_bg, 'truenode': orb_bg, 'southnode': orb_bg,
    }

    start = datetime.fromisoformat(data.get('startDate'))
    end = datetime.fromisoformat(data.get('endDate'))
    step_hours = int(data.get('stepHours', 4))

    results = []
    dt = start
    step = timedelta(hours=step_hours)

    TRIGGER_PLANETS = {'sun', 'mercury', 'venus', 'mars'}
    MOON_PLANETS    = {'moon'}
    BG_PLANETS      = {'jupiter', 'saturn', 'truenode', 'southnode'}

    def check_planet(planet_key, p_lon, planet_orb):
        """
        Returns a dict keyed by natal_planet name for every natal planet
        whose axis this transiting planet activates within orb.
        """
        hits = {}
        for natal_planet, axis_points in all_axes.items():
            best_relation = None
            best_dist = float('inf')
            for relation, axis_lon in axis_points.items():
                diff = abs(p_lon - float(axis_lon)) % 360
                dist = min(diff, 360 - diff)
                if dist <= planet_orb and dist < best_dist:
                    best_dist = dist
                    best_relation = relation
            if best_relation:
                hits[natal_planet] = {
                    "planet": PLANET_DISPLAY.get(planet_key, planet_key),
                    "natal_planet": PLANET_DISPLAY.get(natal_planet, natal_planet),
                    "relation": best_relation,
                    "orb": round(best_dist, 3),
                    "meaning": PLANET_MEANINGS.get(planet_key, "")
                }
        return hits

    while dt <= end:
        pos = get_positions(dt)

        # Build per-natal-planet buckets: {natal_planet: {trigger:[], moon:[], bg:[]}}
        natal_buckets = {}
        for natal_planet in all_axes:
            natal_buckets[natal_planet] = {"trigger": [], "moon": [], "background": []}

        for planet_key in selected_planets:
            if planet_key not in pos:
                continue
            p_lon = pos[planet_key]
            planet_orb = PLANET_ORB.get(planet_key, orb_trigger)
            hits_by_natal = check_planet(planet_key, p_lon, planet_orb)

            for natal_planet, hit_info in hits_by_natal.items():
                if planet_key in TRIGGER_PLANETS:
                    natal_buckets[natal_planet]["trigger"].append(hit_info)
                elif planet_key in MOON_PLANETS:
                    natal_buckets[natal_planet]["moon"].append(hit_info)
                elif planet_key in BG_PLANETS:
                    natal_buckets[natal_planet]["background"].append(hit_info)

        # Emit if a natal planet has trigger+moon+bg (FINAL_EVENT),
        # trigger+bg (STRONG_EVENT), or moon+bg (MOVEMENT).
        # Require at least 2 of the 3 groups to avoid pure NO_EVENT noise.
        activated_natal = {
            np: buckets
            for np, buckets in natal_buckets.items()
            if (buckets["trigger"] and buckets["background"]) or
               (buckets["moon"] and buckets["background"]) or
               (buckets["trigger"] and buckets["moon"] and buckets["background"])
        }

        if activated_natal:
            natal_entries = []
            for np, buckets in activated_natal.items():
                score, classification, event_type = compute_score_and_classification(
                    buckets["trigger"], buckets["moon"], buckets["background"]
                )
                natal_entries.append({
                    "natal_planet":    PLANET_DISPLAY.get(np, np),
                    "trigger":         buckets["trigger"],
                    "moon":            buckets["moon"],
                    "background":      buckets["background"],
                    "score":           score,
                    "classification":  classification,
                    "event_type":      event_type,
                })
            results.append({
                "datetime": dt.strftime("%Y-%m-%d %H:%M"),
                "activated_natal_planets": natal_entries
            })

        dt += step

    return jsonify({"events": results, "count": len(results)})


@app.route('/export_excel', methods=['POST'])
def export_excel():
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    data = request.get_json()
    events = data.get('events', [])
    birth_info = data.get('birthInfo', {})

    wb = Workbook()
    ws = wb.active
    ws.title = "Planetary Transits"

    # Colors
    hdr_fill   = PatternFill("solid", fgColor="2C1F0E")
    gold_fill  = PatternFill("solid", fgColor="9A6F1E")
    sub_fill   = PatternFill("solid", fgColor="F2EDE6")
    nat_fill   = PatternFill("solid", fgColor="FDF0D0")
    white_font = Font(color="FFFFFF", bold=True, name="Calibri", size=12)
    gold_font  = Font(color="9A6F1E", bold=True, name="Calibri", size=12)
    body_font  = Font(name="Calibri", size=11)
    bold_font  = Font(name="Calibri", size=11, bold=True)
    thin = Side(style='thin', color="DDD5C8")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Row 1: Title header — set value/style BEFORE merging
    c1 = ws.cell(row=1, column=1, value="Planetary Scanner — Transit Report")
    c1.font = Font(color="FFFFFF", bold=True, name="Calibri", size=13)
    c1.fill = hdr_fill
    c1.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("A1:G1")
    ws.row_dimensions[1].height = 28

    # Row 2: Birth info — set value/style BEFORE merging
    info_str = (f"DOB: {birth_info.get('dob','')}  TOB: {birth_info.get('tob','')}  "
                f"Place: {birth_info.get('place','')}  UTC: {birth_info.get('utcOffset','')}  "
                f"Scan: {birth_info.get('startDate','')} → {birth_info.get('endDate','')}")
    c2 = ws.cell(row=2, column=1, value=info_str)
    c2.font = Font(color="C8A96A", name="Calibri", size=9, italic=True)
    c2.fill = hdr_fill
    c2.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("A2:G2")
    ws.row_dimensions[2].height = 18

    # Row 3: Column headers — use explicit row=3, never ws.append near merged cells
    headers = ["Date", "Time", "Natal Planet", "Trigger Planets", "Moon", "Background Planets", "Analysis"]
    HDR_ROW = 3
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=HDR_ROW, column=col, value=h)
        c.font = white_font
        c.fill = gold_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border
    ws.row_dimensions[HDR_ROW].height = 22

    def fmt_hits(hits):
        if not hits: return "—"
        return " | ".join(f"{h['planet']} → {h['relation']} ±{h['orb']}°" for h in hits)

    # Classification fill colors
    CLASS_FILLS = {
        'FINAL_EVENT':  PatternFill("solid", fgColor="D6F0DF"),
        'STRONG_EVENT': PatternFill("solid", fgColor="D6E8F5"),
        'MOVEMENT':     PatternFill("solid", fgColor="FDF0D0"),
        'NO_EVENT':     PatternFill("solid", fgColor="F2EDE6"),
    }
    CLASS_FONTS = {
        'FINAL_EVENT':  Font(name="Calibri", size=11, bold=True, color="1A5C30"),
        'STRONG_EVENT': Font(name="Calibri", size=11, bold=True, color="1A3F5C"),
        'MOVEMENT':     Font(name="Calibri", size=11, bold=True, color="6B4E10"),
        'NO_EVENT':     Font(name="Calibri", size=11, color="4A3F30"),
    }

    # Data rows — explicit row counter avoids ws.max_row unreliability near merged cells
    current_row = HDR_ROW + 1
    for event in events:
        dt_parts = event['datetime'].split(' ')
        date_str = dt_parts[0]
        time_str = dt_parts[1] if len(dt_parts) > 1 else ''
        for np in event.get('activated_natal_planets', []):
            natal_name = np['natal_planet']
            score = np.get('score', 0)
            classification = np.get('classification', '')
            event_type = np.get('event_type', '')
            analysis_str = f"{classification}\n{event_type}\nScore: {score}" if event_type else f"{classification}\nScore: {score}"
            row_data = [
                date_str, time_str, natal_name,
                fmt_hits(np.get('trigger', [])),
                fmt_hits(np.get('moon', [])),
                fmt_hits(np.get('background', [])),
                analysis_str,
            ]
            ws.row_dimensions[current_row].height = 48
            cls_fill = CLASS_FILLS.get(classification, sub_fill)
            cls_font = CLASS_FONTS.get(classification, body_font)
            for col, val in enumerate(row_data, 1):
                c = ws.cell(row=current_row, column=col, value=val)
                if col == 7:
                    c.font = cls_font
                    c.fill = cls_fill
                    c.alignment = Alignment(vertical="center", wrap_text=True, horizontal="center")
                else:
                    c.font = bold_font if col == 3 else body_font
                    c.fill = nat_fill if col == 3 else sub_fill
                    c.alignment = Alignment(vertical="center", wrap_text=(col >= 4))
                c.border = border
            current_row += 1

    # Column widths
    widths = [12, 8, 16, 50, 32, 50, 28]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Freeze top 3 rows + header
    ws.freeze_panes = "A4"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    from flask import send_file
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='planetary_transits.xlsx')

if __name__ == '__main__':
    app.run(debug=True)