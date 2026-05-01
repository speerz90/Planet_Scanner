from flask import Flask, render_template, request, jsonify
import swisseph as swe
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

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
    "sun":      "authority / career",
    "moon":     "emotions / movement",
    "mercury":  "communication",
    "venus":    "relationships",
    "mars":     "action / conflict",
    "jupiter":  "growth / expansion",
    "saturn":   "career / job",
    "truenode": "sudden / unconventional",
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
    "sun":      "authority / career",
    "moon":     "emotions / movement",
    "mercury":  "communication",
    "venus":    "relationships",
    "mars":     "action / conflict",
    "jupiter":  "growth / expansion",
    "saturn":   "career / job",
    "truenode": "sudden / unconventional",
}

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

    # Build axis for every natal planet
    all_axes = {}
    for planet_key, lon in pos.items():
        all_axes[planet_key] = {
            "Conjunction": round(lon % 360, 4),
            "Trine 120":   round((lon + 120) % 360, 4),
            "Trine 240":   round((lon + 240) % 360, 4),
            "Opposition":  round((lon + 180) % 360, 4),
        }

    return jsonify({"natal": natal_out, "all_axes": all_axes})

@app.route('/scan', methods=['POST'])
def scan():
    data = request.get_json()

    all_axes         = data.get('allAxes', {})
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

        # Only emit if at least one natal planet has ALL THREE groups activated
        activated_natal = {
            np: buckets
            for np, buckets in natal_buckets.items()
            if buckets["trigger"] and buckets["moon"] and buckets["background"]
        }

        if activated_natal:
            results.append({
                "datetime": dt.strftime("%Y-%m-%d %H:%M"),
                "activated_natal_planets": [
                    {
                        "natal_planet": PLANET_DISPLAY.get(np, np),
                        "trigger":    buckets["trigger"],
                        "moon":       buckets["moon"],
                        "background": buckets["background"],
                    }
                    for np, buckets in activated_natal.items()
                ]
            })

        dt += step

    return jsonify({"events": results, "count": len(results)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)