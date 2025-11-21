from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import swisseph as swe
import pytz
import math
import logging

# ====================== LOGGING ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

swe.set_ephe_path("/app/ephe")

class BirthInput(BaseModel):
    name: str
    dateOfBirth: str
    timeOfBirth: str
    city: str
    state: str
    country: str
    latitude: float
    longitude: float
    timezone: str

SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS = ["Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punavasu","Pushya","Ashlesha",
              "Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshta",
              "Mula","Purva Ashadha","Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadra",
              "Uttara Bhadra","Revati"]

LORDS = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
YEARS = [7,20,6,10,7,18,16,19,17]

def get_nakshatra_pada(lon: float):
    deg_per_nak = 360.0 / 27
    nak_idx = int(lon / deg_per_nak) % 27
    pada = int((lon % deg_per_nak) / (deg_per_nak / 4)) + 1
    return NAKSHATRAS[nak_idx], pada

def get_sign_degree(lon: float):
    sign_idx = int(lon // 30)
    deg_in_sign = lon % 30
    return SIGNS[sign_idx], round(deg_in_sign, 2)

def jd_to_datetime(jd: float, tz_str: str):
    y, m, d, ut = swe.jdut1_to_utc(jd, 1)
    dt = datetime(y, m, d, int(ut), int((ut - int(ut))*60))
    return pytz.timezone(tz_str).fromutc(dt)

def get_tithi(jd: float):
    moon = swe.calc_ut(jd, swe.MOON)[0][0]
    sun = swe.calc_ut(jd, swe.SUN)[0][0]
    diff = (moon - sun + 360) % 360
    tithi_idx = int(diff / 12)
    paksha = "Shukla" if tithi_idx < 15 else "Krishna"
    idx = tithi_idx % 15 if tithi_idx % 15 != 0 else 15
    names = ["Pratipada","Dwitiya","Tritiya","Chaturthi","Panchami","Shashthi","Saptami","Ashtami",
             "Navami","Dashami","Ekadashi","Dwadashi","Trayodashi","Chaturdashi","Purnima/Amavasya"]
    name = "Purnima" if idx == 15 and paksha == "Shukla" else "Amavasya" if idx == 15 else names[idx-1]
    return f"{paksha} {name}"

def get_yoga_name(jd: float):
    sun = swe.calc_ut(jd, swe.SUN)[0][0]
    moon = swe.calc_ut(jd, swe.MOON)[0][0]
    total = (sun + moon) % 360
    yoga_names = ["Vishkambha","Priti","Ayushman","Saubhagya","Shobhana","Atiganda","Sukarma","Dhriti",
                  "Shula","Ganda","Vriddhi","Dhruva","Vyaghata","Harshana","Vajra","Siddhi","Vyatipata",
                  "Variyan","Parigha","Shiva","Siddha","Sadhya","Shubha","Shukla","Brahma","Indra","Vaidhriti"]
    return yoga_names[int(total / (360.0/27)) % 27]

def get_karana_name(jd: float):
    diff = (swe.calc_ut(jd, swe.MOON)[0][0] - swe.calc_ut(jd, swe.SUN)[0][0] + 360) % 360
    k = int(diff / 6)
    if k >= 57: return "Kimstughna"
    if k <= 7: return ["Bava","Balava","Kaulava","Taitila","Gara","Vanija","Vishti"][(k-1)%7]
    return ["Shakuni","Chatushpada","Naga","Kimstughna"][(k-8)%4]

def get_sunrise_sunset(jd: float, lat: float, lon: float, tz_str: str):
    jd_day = math.floor(jd - 0.5) + 0.5
    _, rise = swe.rise_trans(jd_day-1, swe.SUN, lon, lat, swe.CALC_RISE)
    _, sett = swe.rise_trans(jd_day-1, swe.SUN, lon, lat, swe.CALC_SET)
    rise_str = jd_to_datetime(rise, tz_str).strftime("%I:%M %p") if rise > 0 else "N/A"
    set_str = jd_to_datetime(sett, tz_str).strftime("%I:%M %p") if sett > 0 else "N/A"
    return rise_str, set_str

@app.post("/full-vedic-chart")
def full_vedic_chart(data: BirthInput):
    try:
        logger.info(f"Request received for {data.name} - {data.dateOfBirth} {data.timeOfBirth}")

        local = datetime.strptime(f"{data.dateOfBirth} {data.timeOfBirth}", "%Y-%m-%d %H:%M")
        tz = pytz.timezone(data.timezone)
        utc = tz.localize(local).astimezone(pytz.UTC)
        jd_birth = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute/60.0)

        swe.set_sid_mode(swe.SIDM_LAHIRI)
        ayan = swe.get_ayanamsa_ut(jd_birth)

        pids = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}
        planets = {name: (swe.calc_ut(jd_birth, pid)[0][0] - ayan) % 360 for name, pid in pids.items()}
        planets["Ketu"] = (planets["Rahu"] + 180) % 360

        cusps, _ = swe.houses(jd_birth, data.latitude, data.longitude, b'W')
        lagna_lon = (cusps[0] - ayan) % 360

        now = datetime.utcnow()
        jd_now = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0 + now.second/3600.0)

        current = {name: (swe.calc_ut(jd_now, pid)[0][0] - swe.get_ayanamsa_ut(jd_now)) % 360 for name, pid in pids.items()}
        current["Ketu"] = (current["Rahu"] + 180) % 360

        dasha_info = get_dasha_details(planets["Moon"], jd_birth, data.timezone)

        birth_sunrise, birth_sunset = get_sunrise_sunset(jd_birth, data.latitude, data.longitude, data.timezone)
        current_sunrise, current_sunset = get_sunrise_sunset(jd_now, data.latitude, data.longitude, data.timezone)

        def fmt(name: str, lon: float):
            sign, deg = get_sign_degree(lon)
            nak, pada = get_nakshatra_pada(lon)
            retro = swe.calc_ut(jd_birth, pids.get(name, swe.MEAN_NODE))[0][3] < 0 if name not in ["Rahu","Ketu"] else False
            return {"planet": name, "sign": sign, "degree": f"{deg:.2f}", "nakshatra": nak, "pada": str(pada), "longitude": f"{lon:.2f}", "isRetro": retro}

        natal_planets = [fmt(p, l) for p, l in planets.items()]

        current_planets = []
        for p, l in current.items():
            sign, deg = get_sign_degree(l)
            nak, pada = get_nakshatra_pada(l)
            current_planets.append({
                "currentPlanetaryplanet": p,
                "currentPlanetarysign": sign,
                "currentPlanetarydegree": f"{deg:.2f}",
                "currentPlanetarynakshatra": nak,
                "currentPlanetarypada": str(pada),
                "currentPlanetarylongitude": f"{l:.2f}"
            })

        logger.info("Chart generated successfully")

        return {
            "birthDetails": {
                "name": data.name,
                "dateOfBirth": data.dateOfBirth,
                "timeOfBirth": data.timeOfBirth,
                "placeOfBirth": {
                    "city": data.city,
                    "state": data.state,
                    "country": data.country,
                    "latitude": data.latitude,
                    "longitude": data.longitude,
                    "timezone": data.timezone
                },
                "user_location": {"latitude": data.latitude, "longitude": data.longitude, "timezone": data.timezone}
            },
            "natalChart": {
                "ascendant": {**fmt("Ascendant", lagna_lon), "planet": "Ascendant"},
                "sunSign": fmt("Sun", planets["Sun"]),
                "moonSign": fmt("Moon", planets["Moon"]),
                "tithi": {"name": get_tithi(jd_birth)},
                "yoga": {"name": get_yoga_name(jd_birth)}
            },
            "houseCalculationMethod": "Whole Sign Houses based on ascendant (Lagna)",
            "natalPlanets": natal_planets,
            "currentPlanetaryPositions": current_planets,
            "currentDasha": {
                "dasha": dasha_info["mahadasha"],
                "startDate": dasha_info["mahadashaStart"],
                "endDate": dasha_info["mahadashaEnd"]
            },
            "currentAntardasha": {
                "antardasha": dasha_info["currentAntardasha"],
                "startDate": dasha_info["currentAntardashaStart"],
                "endDate": dasha_info["currentAntardashaEnd"]
            },
            "antardashaList": dasha_info["antardashaList"],
            "currentPratyantardasha": {
                "pratyantardasha": dasha_info["currentPratyantardasha"],
                "startDate": dasha_info["currentPratyantardashaStart"],
                "endDate": dasha_info["currentPratyantardashaEnd"]
            },
            "pratyantardashaList": dasha_info["pratyantardashaList"],
            "dailyDetails": {
                "sunrise": birth_sunrise,
                "sunset": birth_sunset
            },
            "currentPanchang": {
                "currentMoonSign": get_sign_degree(current["Moon"])[0],
                "currentTithi": {"currentTithiName": get_tithi(jd_now)},
                "currentKarana": {"currentKaranaName": get_karana_name(jd_now)},
                "currentYoga": {"currentYogaName": get_yoga_name(jd_now)},
                "currentNakshatra": {"currentNakshatraName": get_nakshatra_pada(current["Moon"])[0]},
                "currentSunRise": current_sunrise,
                "currentSunSet": current_sunset
            },
            "yogas": detect_yogas(planets, lagna_lon)  # 120+ yogas from previous message
        }

    except Exception as e:
        logger.error(f"ERROR: {str(e)}", exc_info=True)
        return {"error": "Something went wrong", "details": str(e)}, 500

@app.get("/")
def home():
    logger.info("Root endpoint accessed")
    return {"status": "AstroVed Ultimate Vedic API"}
