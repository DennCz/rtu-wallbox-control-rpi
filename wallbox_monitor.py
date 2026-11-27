from flask import Flask, render_template, jsonify, request, url_for, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image, ImageOps, UnidentifiedImageError
import hashlib, tempfile, warnings, uuid, unicodedata
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
import threading, time, yaml, os

import sqlite3
import math, re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import signal
import logging
import sys

BASE_DIR = Path(__file__).resolve().parent
# Demo- und Echtbetrieb verwenden strikt getrennte Laufzeitdaten.
DEMO_MODE = os.environ.get("WALLBOX_DEMO") == "1" or (__name__ == "__main__" and "--demo" in sys.argv[1:])
if DEMO_MODE:
    from demo import DEMO_PERSON_ID, data_directory, seed_data, create_wallbox
    DATA_DIR = data_directory(BASE_DIR)
else:
    DATA_DIR = BASE_DIR
CAR_IMAGES = DATA_DIR / "person_images"
PERSONS_FILE = DATA_DIR / "persons.yaml"
_persons_lock = threading.RLock()
MAX_IMAGE_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 25_000_000
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ------------------------------ SQLite ------------------------------
DB_FILE = DATA_DIR / "wallbox_sessions.db"
LEGACY_COST_PER_KWH = 0.26


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            energy_total_start REAL,
            energy_total_end REAL,
            max_power REAL,
            verbrauch_total REAL,
            total_costs REAL,
            cost_per_kwh REAL
        )
    ''')
    # V12: additive Migration; historische Preise nicht rückwirkend erraten.
    columns = {row[1] for row in c.execute("PRAGMA table_info(sessions)")}
    for column in ("energy_total_start", "energy_total_end", "cost_per_kwh"):
        if column not in columns:
            c.execute(f"ALTER TABLE sessions ADD COLUMN {column} REAL")
    c.execute("""CREATE TABLE IF NOT EXISTS cost_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), cost_per_kwh REAL NOT NULL
        CHECK(cost_per_kwh >= 0 AND cost_per_kwh <= 10)
    )""")
    c.execute("INSERT OR IGNORE INTO cost_settings(id,cost_per_kwh) VALUES(1,?)", (LEGACY_COST_PER_KWH,))
    # Offene V11-Sessions wurden bisher zum fest codierten Preis abgerechnet.
    c.execute("UPDATE sessions SET cost_per_kwh=? WHERE end_time IS NULL AND cost_per_kwh IS NULL", (LEGACY_COST_PER_KWH,))
    c.execute("""CREATE TABLE IF NOT EXISTS scheduled_charge (
        id INTEGER PRIMARY KEY CHECK(id=1), person_id TEXT NOT NULL,
        due INTEGER NOT NULL, phase TEXT NOT NULL DEFAULT 'pending'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS auto_charge (
        id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
        hour INTEGER NOT NULL DEFAULT 1, person_id TEXT, due INTEGER,
        blocked INTEGER NOT NULL DEFAULT 0
    )""")
    # V9: Tagesprüfung dauerhaft merken, unabhängig vom Anschlusszeitpunkt.
    if "last_check_date" not in {row[1] for row in c.execute("PRAGMA table_info(auto_charge)")}:
        c.execute("ALTER TABLE auto_charge ADD COLUMN last_check_date TEXT")
        c.execute("UPDATE auto_charge SET due=NULL, blocked=0")
    # Überspringen ist eine widerrufbare Ausnahme, kein bereits ausgeführter Startversuch.
    if "skipped_date" not in {row[1] for row in c.execute("PRAGMA table_info(auto_charge)")}:
        c.execute("ALTER TABLE auto_charge ADD COLUMN skipped_date TEXT")
    c.execute("INSERT OR IGNORE INTO auto_charge(id) VALUES(1)")
    conn.commit()
    conn.close()


def read_cost_settings():
    with sqlite3.connect(DB_FILE) as conn:
        price = conn.execute("SELECT cost_per_kwh FROM cost_settings WHERE id=1").fetchone()[0]
    return {"cost_per_kwh": price, "price_ct": float(Decimal(str(price)) * 100)}


def parse_price_ct(value):
    # Eingabe in Cent/kWh, maximal zwei Nachkommastellen.
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Strompreis eingeben.")
    text = str(value).strip().replace(",", ".")
    if not re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,2})?", text):
        raise ValueError("Preis in ct/kWh mit maximal zwei Nachkommastellen eingeben.")
    cents = Decimal(text)
    if not 0 <= cents <= 1000:
        raise ValueError("Preis zwischen 0 und 1000 ct/kWh eingeben.")
    return float(cents / 100)


def start_session(person, energy_total_start):
    if energy_total_start is None or not math.isfinite(energy_total_start) or energy_total_start < 0:
        raise ValueError("Kein gültiger Start-Zählerstand")
    with sqlite3.connect(DB_FILE) as conn:
        # Tarif und Zählerstand werden beim tatsächlichen Ladestart fixiert.
        c = conn.execute("""
            INSERT INTO sessions (person, start_time, energy_total_start, cost_per_kwh)
            SELECT ?, ?, ?, cost_per_kwh FROM cost_settings WHERE id=1
        """, (person, datetime.now().isoformat(), float(energy_total_start)))
        if c.rowcount != 1:
            raise RuntimeError("Strompreis fehlt")
        return c.lastrowid


def end_session(session_id, energy_total_end, max_power):
    if energy_total_end is None or not math.isfinite(energy_total_end) or energy_total_end < 0:
        raise ValueError("Kein gültiger End-Zählerstand")
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT energy_total_start,cost_per_kwh FROM sessions WHERE id=? AND end_time IS NULL", (session_id,)).fetchone()
        if row is None:
            return  # bereits abgeschlossen
        energy_total_start, price = row
        # Zählerstände immer unverändert speichern. Bei Rücksprung ist der Verbrauch unbekannt.
        consumption = costs = None
        if energy_total_start is not None and energy_total_end >= energy_total_start:
            delta = Decimal(str(energy_total_end)) - Decimal(str(energy_total_start))
            consumption = float(delta)
            if price is not None:
                costs = float((delta * Decimal(str(price))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:
            logging.warning("Session %s: ungültige Zählerdifferenz; Verbrauch/Kosten unbekannt", session_id)
        conn.execute("""
            UPDATE sessions SET end_time=?, energy_total_end=?, max_power=?,
                verbrauch_total=?, total_costs=? WHERE id=? AND end_time IS NULL
        """, (datetime.now().isoformat(), float(energy_total_end), float(max_power or 0), consumption, costs, session_id))


def get_all_sessions():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, person, start_time, end_time,
               energy_total_start, energy_total_end,
               max_power, verbrauch_total, total_costs
        FROM sessions
        ORDER BY start_time DESC, id DESC
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_current_month_summary():
    """
    Summiert das AKTUELLE Monat.
    Wichtig: Zuordnung erfolgt über start_time (nicht end_time).
    Damit zählt ein Ladevorgang komplett zu dem Monat, in dem er gestartet wurde.
    """
    month_key = datetime.now().strftime("%Y-%m")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT
            COUNT(*) AS sessions_count,
            COALESCE(SUM(verbrauch_total), 0) AS total_kwh,
            COALESCE(SUM(total_costs), 0) AS total_costs
        FROM sessions
        WHERE end_time IS NOT NULL
          AND substr(start_time, 1, 7) = ?
    """, (month_key,))

    row = c.fetchone()
    conn.close()

    return {
        "month_key": month_key,
        "sessions_count": int(row["sessions_count"] or 0),
        "total_kwh": round(float(row["total_kwh"] or 0), 3),
        "total_costs": round(float(row["total_costs"] or 0), 2),
    }


def get_monthly_totals():
    """
    Monatswerte aller gespeicherten Monate.
    Ebenfalls über start_time gruppiert.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT
            substr(start_time, 1, 7) AS month_key,
            COUNT(*) AS sessions_count,
            COALESCE(SUM(verbrauch_total), 0) AS total_kwh,
            COALESCE(SUM(total_costs), 0) AS total_costs
        FROM sessions
        WHERE end_time IS NOT NULL
        GROUP BY substr(start_time, 1, 7)
        ORDER BY month_key DESC
    """)

    rows = c.fetchall()
    conn.close()

    return [
        {
            "month_key": r["month_key"],
            "sessions_count": int(r["sessions_count"] or 0),
            "total_kwh": round(float(r["total_kwh"] or 0), 3),
            "total_costs": round(float(r["total_costs"] or 0), 2),
        }
        for r in rows
    ]

# ------------------------------ Config ------------------------------
PORT = "/dev/ttyUSB0"
BAUDRATE = 19200
UNIT_ID = 1
READ_INTERVAL = 2

# Heidelberg Energy Control: Stromvorgabe zum Freigeben/Sperren
CONTROL_REGISTER = 261
CONTROL_ALLOW_VALUE = 160   # Freigabe: 16 A (0,1 A pro Registereinheit)
CONTROL_STOP_VALUE = 0     # Sperren

# Lesen: Input-Register, serielle Konfiguration 8E1
USE_HOLDING_REGISTERS = False
REGISTER_OFFSET_MINUS_ONE = False

# Ende-Absicherung
END_DEBOUNCE_READS = 3        # wie viele aufeinanderfolgende !=7 Messungen nötig
ZERO_POWER_SECONDS = 20       # wenn Leistung ~0 so lange, dann Ende (Fallback)
ZERO_POWER_KW = 0.05          # Schwelle für "0 kW"

# status==7 bedeutet Laden 
CHARGING_STATUS_CODE = 7

STATE_MAP = {
    2:  "Kein Fahrzeug angeschlossen\nLadevorgang gesperrt.",
    3:  "Kein Fahrzeug angeschlossen\nLadevorgang freigegeben.",
    4:  "Fahrzeug angeschlossen\nkeine Ladeanforderung\n Ladevorgang gesperrt.",
    5:  "Fahrzeug angeschlossen\nkeine Ladeanforderung\n Ladevorgang freigegeben.",
    6:  "Fahrzeug angeschlossen\nLadeanforderung erkannt\nLadevorgang gesperrt.",
    7:  "Ladevorgang aktiv",
    8:  "Leistungsbegrenzung aktiv (Derating).",
    9:  "Fehlerzustand (E).",
    10: "Fehlerzustand (F).",
    11: "Allgemeiner Fehler (ERR).",
}

REGISTERS = {
    "status": 5,
    "current_L1": 6,
    "current_L2": 7,
    "current_L3": 8,
    "pcb_temp": 9,
    "voltage_L1": 10,
    "voltage_L2": 11,
    "voltage_L3": 12,
    "power": 14,
    "energy_poweron_high": 15,
    "energy_poweron_low": 16,
    "energy_total_high": 17,
    "energy_total_low": 18
}


# ------------------------------ Globals (Session State) ------------------------------
current_person = None              # dict aus persons.yaml
current_session_id = None
charging_active = False
max_power_seen = 0.0
waiting_for_person = False

_thread_started = False
schedule_notice = None
SCHEDULE_TZ = ZoneInfo("Europe/Berlin")
SCHEDULE_GRACE = 900  # maximal 15 Minuten auf sichere Freigabe warten
RELEASE_GRACE = 300   # unveränderte Prüfung nach erteilter Freigabe
DISCONNECT_READS = 3
_disconnect_streak = 0


def observe_connection(status):
    """Nur aufeinanderfolgende gültige Abgezogen-Messungen zählen."""
    global _disconnect_streak
    _disconnect_streak = min(DISCONNECT_READS, _disconnect_streak + 1) if status in (2, 3) else 0


def disconnected_confirmed(status):
    return status in (2, 3) and _disconnect_streak >= DISCONNECT_READS


def next_hour(hour, now=None):
    """Nächste tatsächlich existierende lokale volle Stunde (inkl. Zeitumstellung)."""
    now = time.time() if now is None else now
    day = datetime.fromtimestamp(now, SCHEDULE_TZ).date()
    for offset in range(3):
        date = day + timedelta(days=offset)
        naive = datetime(date.year, date.month, date.day, hour)
        candidates = set()
        for fold in (0, 1):
            local = naive.replace(tzinfo=SCHEDULE_TZ, fold=fold)
            stamp = int(local.timestamp())
            if datetime.fromtimestamp(stamp, SCHEDULE_TZ).replace(tzinfo=None) == naive and stamp > now:
                candidates.add(stamp)
        if candidates:
            return min(candidates)
    raise ValueError("Keine gültige Startzeit")


def schedule_options(now=None):
    now = time.time() if now is None else now
    today = datetime.fromtimestamp(now, SCHEDULE_TZ).date()
    options = []
    for hour in range(24):
        due = next_hour(hour, now)
        local = datetime.fromtimestamp(due, SCHEDULE_TZ)
        days = (local.date() - today).days
        options.append(dict(hour=hour, due=due, day="Heute" if days == 0 else "Morgen" if days == 1 else local.strftime("%d.%m."), label=local.strftime("%d.%m.%Y · %H:%M Uhr %Z")))
    return options


def read_schedule():
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT person_id, due, phase FROM scheduled_charge WHERE id=1").fetchone()
    return dict(person_id=row[0], due=row[1], phase=row[2]) if row else None


def save_schedule(person_id, due, phase="pending"):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO scheduled_charge(id,person_id,due,phase) VALUES(1,?,?,?)", (person_id,due,phase))


def clear_schedule():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM scheduled_charge WHERE id=1")


def read_auto():
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT enabled,hour,person_id,last_check_date,skipped_date FROM auto_charge WHERE id=1").fetchone()
    return dict(enabled=bool(row[0]), hour=row[1], person_id=row[2], last_check_date=row[3], skipped_date=row[4])


def auto_slot(cfg, now):
    """Eine Prüfung je lokalem Kalendertag, nur in der ersten Minute der Stunde."""
    local = datetime.fromtimestamp(now, SCHEDULE_TZ)
    day = local.date().isoformat()
    if not cfg["enabled"] or local.hour != cfg["hour"] or local.minute != 0:
        return None
    if cfg["last_check_date"] and day <= cfg["last_check_date"]:
        return None
    return day


def next_auto_check(cfg, now):
    """Nächster täglicher Starttermin, einschließlich widerrufbar übersprungener Termine."""
    if not cfg["enabled"] or not valid_person(cfg["person_id"]):
        return None
    if auto_slot(cfg, now):
        return int(now // 60 * 60)
    due = next_hour(cfg["hour"], now)
    # Doppelte Stunde bei Winterzeit nicht zweimal ausführen.
    while cfg["last_check_date"] and datetime.fromtimestamp(due, SCHEDULE_TZ).date().isoformat() <= cfg["last_check_date"]:
        due = next_hour(cfg["hour"], due)
    return due


def mark_auto_checked(day):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE auto_charge SET last_check_date=?, skipped_date=CASE WHEN skipped_date<=? THEN NULL ELSE skipped_date END WHERE id=1", (day, day))


def block_auto():
    """Manuelle Aktion im Prüfzeitfenster hat Vorrang; kein Dauerblock."""
    day = auto_slot(read_auto(), time.time())
    if day:
        mark_auto_checked(day)


def process_auto(status, now):
    """Täglich einmal den aktuellen Status prüfen. Keine Vorabplanung, kein Nachholen.
    Nur nach gültiger Modbus-Messung und unter dem Monitor-Lock aufrufen.
    """
    global schedule_notice
    cfg = read_auto()
    day = auto_slot(cfg, now)
    if not day:
        return
    if cfg["skipped_date"] == day:
        mark_auto_checked(day)
        logging.info("Automatischer Ladestart %s wurde übersprungen.", day)
        return
    person = valid_person(cfg["person_id"])
    # Auch bei fehlendem Fahrzeug oder manueller Ladung gilt die Prüfung als erledigt.
    # Freigabe nur im bekannten, gesperrten Anschlusszustand (4/6).
    eligible = bool(person and not current_person and not charging_active
                    and not read_schedule() and status in (4, 6))
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE auto_charge SET last_check_date=?, skipped_date=CASE WHEN skipped_date<=? THEN NULL ELSE skipped_date END WHERE id=1", (day, day))
        if eligible:
            # Nur zum Zeitpunkt der Prüfung; process_schedule gibt im selben Zyklus frei.
            conn.execute("INSERT INTO scheduled_charge(id,person_id,due,phase) VALUES(1,?,?, 'auto_pending')", (person["id"], int(now)))
    logging.info("Automatikprüfung %s: Status %s, %s", day, status, "Start" if eligible else "kein Start")
    if eligible:
        schedule_notice = "Automatik startet."


def process_schedule(controller, status, now):
    """Nur im Modbus-Monitor unter dessen Lock und nach gültiger Messung ausführen."""
    global current_person, waiting_for_person, schedule_notice
    plan = read_schedule()
    if not plan:
        return
    person = next((p for p in load_persons() if p.get("id") == plan["person_id"]), None)
    phase = plan["phase"]
    if phase == "auto_pending":
        # Kein verspäteter Automatikstart nach Neustart oder Statuswechsel.
        cfg = read_auto()
        if (not cfg["enabled"] or cfg["person_id"] != plan["person_id"]
                or int(now // 60) != int(plan["due"] // 60) or status not in (4, 6)):
            clear_schedule()
            schedule_notice = "Automatik übersprungen."
            return
        phase = "pending"
    if phase == "released" and charging_active:
        clear_schedule()
        return
    if phase == "released" and person and status in (5, 7, 8):
        current_person = person  # Wiederanlauf vor Beginn der aufgezeichneten Session
        return
    if phase == "released" and person and current_person and status in (4,6) and now < plan["due"] + RELEASE_GRACE:
        return  # Freigabe kann erst im nächsten Messzyklus sichtbar werden
    reason = None
    if phase != "pending":
        reason = "Freigabe unklar – Start abgebrochen."
    elif not person or charging_active or current_person:
        reason = "Planung ungültig."
    elif disconnected_confirmed(status):
        reason = "Planung abgebrochen: Fahrzeug getrennt."
    elif status in (7, 8):
        reason = "Planung abgebrochen: unerwartete Ladung."
    elif now >= plan["due"] + SCHEDULE_GRACE:
        reason = "Startzeit verpasst."
    if reason:
        # Bei widersprüchlichem Freigabezustand sperren. Keine erneute Freigabe.
        if status not in (2, 4, 6) or phase != "pending":
            controller.write_register(CONTROL_REGISTER, CONTROL_STOP_VALUE)
        clear_schedule()
        if not charging_active:
            current_person = None
        schedule_notice = reason
        return
    # Eine unerwartete Freigabe ohne Ladung zurücknehmen, Termin behalten.
    if status in (3, 5):
        controller.write_register(CONTROL_REGISTER, CONTROL_STOP_VALUE)
        return
    # Kurzzeitige Fehler, unbekannte Zustände und einzelne Abgezogen-Messungen
    # behalten den Termin. Freigabe nur nach gültiger Messung in Status 4/6.
    if now < plan["due"] or status not in (4, 6):
        return
    # Vor dem Hardwarebefehl dauerhaft markieren. Nach Absturz niemals blind wiederholen.
    save_schedule(plan["person_id"], plan["due"], "releasing")
    try:
        controller.write_register(CONTROL_REGISTER, CONTROL_ALLOW_VALUE)
        save_schedule(plan["person_id"], plan["due"], "released")
    except Exception:
        schedule_notice = "Ladestart fehlgeschlagen."
        logging.exception("Geplante Ladefreigabe fehlgeschlagen")
        controller.write_register(CONTROL_REGISTER, CONTROL_STOP_VALUE)
        clear_schedule()
        return
    current_person = person
    waiting_for_person = False
    schedule_notice = "Ladung freigegeben."



# ------------------------------ Helpers ------------------------------
def load_persons():
    """Eine frische Installation startet ohne Personen."""
    with _persons_lock:
        try:
            with PERSONS_FILE.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            return []
        if data is None:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("persons"), list):
            raise ValueError("Ungültige Personenkonfiguration.")
        return data["persons"]


def save_persons(persons):
    """Die Datei atomar austauschen; auch parallele Leser sehen gültiges YAML."""
    with _persons_lock:
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=PERSONS_FILE.parent, mode="w", encoding="utf-8",
                prefix=".persons-", suffix=".tmp", delete=False
            ) as f:
                temp_path = Path(f.name)
                yaml.safe_dump({"persons": persons}, f, allow_unicode=True, sort_keys=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, PERSONS_FILE)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def parse_person_name(value):
    if not isinstance(value, str) or any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("Bitte einen gültigen Namen eingeben.")
    name = " ".join(value.split())
    if not 1 <= len(name) <= 80:
        raise ValueError("Der Name muss 1 bis 80 Zeichen enthalten.")
    return name


def car_image_name(person_id):
    return hashlib.sha256(str(person_id).encode("utf-8")).hexdigest() + ".webp"


def seed_demo_data():
    """Initialisiert die optionalen, strikt getrennten Beispieldaten."""
    if not DEMO_MODE:
        raise RuntimeError("Demo-Daten sind im Echtbetrieb nicht erlaubt.")
    seed_data(DB_FILE, CAR_IMAGES, load_persons, save_persons, car_image_name,
              BASE_DIR / "demo" / "demo-vehicle.webp")


# ------------------------------ Modbus Wallbox ------------------------------
class Wallbox:
    def __init__(self, port, baudrate=19200, slave_id=1):
        self.client = ModbusSerialClient(
            method="rtu",
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity="E",   # gerade Parität (Modbus RTU 8E1)
            stopbits=1,
            timeout=1
        )
        self.slave_id = slave_id

    def connect(self):
        if not self.client.connect():
            raise ConnectionError("❌ Verbindung zur Wallbox fehlgeschlagen")
        print("✅ Modbus RTU verbunden")

    def close(self):
        self.client.close()

    def _call_read(self, fn_name: str, address: int, count: int):
        fn = getattr(self.client, fn_name)
        try:
            return fn(address=address, count=count, slave=self.slave_id)
        except TypeError:
            return fn(address=address, count=count, unit=self.slave_id)

    def _call_write_register(self, address: int, value: int):
        fn = getattr(self.client, "write_register")
        try:
            return fn(address=address, value=value, slave=self.slave_id)
        except TypeError:
            return fn(address=address, value=value, unit=self.slave_id)

    def read_input_register(self, address, count=1):
        try:
            result = self._call_read("read_input_registers", address, count)
            if result is None or result.isError():
                raise ModbusException(result)
            return result.registers
        except Exception:
            return None

    def read_holding_register(self, address, count=1):
        try:
            result = self._call_read("read_holding_registers", address, count)
            if result is None or result.isError():
                raise ModbusException(result)
            return result.registers
        except Exception:
            return None

    def write_register(self, address, value):
        r = self._call_write_register(address, value)
        if r is None or r.isError():
            raise ConnectionError(f"Schreiben Register {address} fehlgeschlagen")


# ------------------------------ Monitor + robuste Session Logik ------------------------------
def finalize_session(reason: str, energy_total_end: float | None = None):
    """
    Beendet die aktive Session genau einmal (DB write + State reset).
    """
    global charging_active, current_session_id, max_power_seen
    global current_person, waiting_for_person

    if not charging_active or current_session_id is None:
        return

    if energy_total_end is None:
        values = monitor.get_values()
        energy_total_end = values.get("energy_total_kwh")
    if energy_total_end is None:
        raise RuntimeError("Kein gültiger Energiezählerstand")

    try:
        end_session(current_session_id, float(energy_total_end), float(max_power_seen or 0.0))
    except Exception as e:
        logging.exception("Session ENDE Fehler (%s)", reason)
        raise

    charging_active = False
    current_session_id = None
    max_power_seen = 0.0
    current_person = None
    waiting_for_person = False


class WallboxMonitor:
    def __init__(self, port, baudrate, unit_id, wallbox=None):
        self.wallbox = wallbox if wallbox is not None else Wallbox(port=port, baudrate=baudrate, slave_id=unit_id)
        self.values = {k: None for k in REGISTERS.keys()}
        self._lock = threading.RLock()
        self._stop_thread = False

        self._not7_streak = 0
        self._zero_power_since = None

    def connect(self):
        while True:
            try:
                self.wallbox.connect()
                return
            except Exception as e:
                print(f"✖ Verbindung zu {PORT} fehlgeschlagen ({e}), retry in 5s ...")
                time.sleep(5)

    def _read_one(self, reg_addr: int):
        if REGISTER_OFFSET_MINUS_ONE:
            reg_addr = reg_addr - 1

        if USE_HOLDING_REGISTERS:
            regs = self.wallbox.read_holding_register(reg_addr, 1)
        else:
            regs = self.wallbox.read_input_register(reg_addr, 1)

        if regs and len(regs) > 0:
            return regs[0]
        return None

    def read_registers(self):
        global charging_active, current_person, current_session_id, max_power_seen

        while not self._stop_thread:
            try:
                with self._lock:
                    if not self.wallbox.client.connect():
                        raise ConnectionError("Modbus nicht erreichbar")
                    # --- Register lesen ---
                    for key, reg in REGISTERS.items():
                        self.values[key] = self._read_one(reg)

                    # Keine Session aus unvollständigen Messungen ableiten.
                    if any(self.values[k] is None for k in ("status", "power", "energy_total_high", "energy_total_low")):
                        self.values = {k: None for k in REGISTERS}
                        self._not7_streak = 0
                        self.wallbox.close()
                        raise ConnectionError("Ungültige Modbus-Messung; erneuter Verbindungsversuch")

                    # --- Umrechnungen ---
                    for phase in ["current_L1", "current_L2", "current_L3"]:
                        if self.values.get(phase) is not None:
                            self.values[phase] = self.values[phase] / 10.0

                    if self.values.get("pcb_temp") is not None:
                        self.values["pcb_temp"] = self.values["pcb_temp"] / 10.0

                    # Energie PowerOn kWh
                    if self.values.get("energy_poweron_high") is not None and self.values.get("energy_poweron_low") is not None:
                        ep = (self.values["energy_poweron_high"] << 16) + self.values["energy_poweron_low"]
                        self.values["energy_poweron_kwh"] = round(ep / 1000.0, 3)
                    else:
                        self.values["energy_poweron_kwh"] = 0.0

                    # Gesamtenergie kWh
                    if self.values.get("energy_total_high") is not None and self.values.get("energy_total_low") is not None:
                        et = (self.values["energy_total_high"] << 16) + self.values["energy_total_low"]
                        self.values["energy_total_kwh"] = round(et / 1000.0, 3)
                    else:
                        self.values["energy_total_kwh"] = 0.0

                    # Leistung kW
                    self.values["power_kw"] = round((self.values.get("power") or 0) / 1000.0, 2)

                    status = self.values.get("status")
                    p_kw = self.values.get("power_kw", 0) or 0.0

                    now = time.time()
                    observe_connection(status)
                    process_auto(status, now)
                    process_schedule(self, status, now)

                    # -------- Start Session --------
                    if current_person and (not charging_active) and status == CHARGING_STATUS_CODE:
                        values = self.get_values()
                        energy_total_start = values.get("energy_total_kwh")
                        current_session_id = start_session(current_person["name"], energy_total_start)
                        charging_active = True
                        if read_schedule():
                            clear_schedule()
                        max_power_seen = 0.0
                        self._not7_streak = 0
                        self._zero_power_since = None

                    # -------- Während Session --------
                    if charging_active:
                        max_power_seen = max(max_power_seen, p_kw)

                        # 1) Primär: Status != 7, aber erst nach Debounce
                        if status != CHARGING_STATUS_CODE:
                            self._not7_streak += 1
                        else:
                            self._not7_streak = 0

                        if self._not7_streak >= END_DEBOUNCE_READS:
                            values = self.get_values()
                            monitor.write_register(CONTROL_REGISTER, CONTROL_STOP_VALUE)
                            finalize_session(f"status_not_7_x{END_DEBOUNCE_READS}", values["energy_total_kwh"])
                            self._not7_streak = 0
                            self._zero_power_since = None
                            # Nächster Messzyklus

            except Exception as e:
                observe_connection(None)
                logging.warning("Fehler beim Lesen: %s", e)
                with self._lock:
                    self.values = {k: None for k in REGISTERS}
                    self._not7_streak = 0
                    self.wallbox.close()

            time.sleep(READ_INTERVAL)

    def get_values(self):
        with self._lock:
            status_raw = self.values.get("status")
            status_de = STATE_MAP.get(status_raw, f"Unbekannter Status ({status_raw})") if status_raw is not None else "Keine Verbindung"

            plan = read_schedule()
            scheduled = None
            if plan and plan["phase"] != "released":
                person = next((p for p in load_persons() if p.get("id") == plan["person_id"]), None)
                scheduled = {**plan, "person": person["name"] if person else plan["person_id"],
                             "label": datetime.fromtimestamp(plan["due"], SCHEDULE_TZ).strftime("%d.%m.%Y · %H:%M Uhr %Z")}
            auto = read_auto()
            auto_pending = None
            now = time.time()
            due = next_auto_check(auto, now)
            if due is not None:
                person = valid_person(auto["person_id"])
                if person:
                    auto_pending = {"due": due, "person": person["name"],
                                    "skipped": auto["skipped_date"] == datetime.fromtimestamp(due, SCHEDULE_TZ).date().isoformat(),
                                    "label": datetime.fromtimestamp(due, SCHEDULE_TZ).strftime("%d.%m.%Y · %H:%M Uhr %Z")}
            return {
                "demo_mode": DEMO_MODE,
                "demo_connected": self.wallbox.connected if DEMO_MODE else None,
                "demo_person_id": DEMO_PERSON_ID if DEMO_MODE else None,
                "auto_pending": auto_pending,
                "auto_enabled": auto["enabled"],
                "auto_blocked": False,
                "scheduled_charge": scheduled,
                "schedule_notice": schedule_notice,
                "server_now": now,
                "raw_status": status_raw,
                "status": status_de,
                "status_text": status_de,

                "current_L1": self.values.get("current_L1"),
                "current_L2": self.values.get("current_L2"),
                "current_L3": self.values.get("current_L3"),
                "voltage_L1": self.values.get("voltage_L1"),
                "voltage_L2": self.values.get("voltage_L2"),
                "voltage_L3": self.values.get("voltage_L3"),
                "pcb_temp": self.values.get("pcb_temp"),
                "power_kw": self.values.get("power_kw"),
                "energy_poweron_kwh": self.values.get("energy_poweron_kwh"),
                "energy_total_kwh": self.values.get("energy_total_kwh"),

                "current_person": current_person["name"] if current_person else None,
                "current_person_id": current_person.get("id") if current_person else None,
                "waiting_for_person": waiting_for_person,
                "charging_active": charging_active,
            }

    def stop(self):
        self._stop_thread = True
        with self._lock:
            self.wallbox.close()

    def write_register(self, register, value):
        with self._lock:
            self.wallbox.write_register(register, value)


# ------------------------------ Flask App ------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 128 * 1024
init_db()
if DEMO_MODE:
    seed_demo_data()
monitor = WallboxMonitor(PORT, BAUDRATE, UNIT_ID, wallbox=create_wallbox(DB_FILE, REGISTERS, CONTROL_REGISTER, REGISTER_OFFSET_MINUS_ONE) if DEMO_MODE else None)


def restore_open_session():
    global current_person, current_session_id, charging_active
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute("SELECT id, person FROM sessions WHERE end_time IS NULL ORDER BY id DESC").fetchall()
    if len(rows) == 1:
        current_session_id, name = rows[0]
        current_person = next((p for p in load_persons() if p.get("name") == name), {"name": name})
        charging_active = True
        logging.warning("Offene Session %s wieder aufgenommen; Maximalleistung seit Neustart", current_session_id)
    elif rows:
        logging.warning("Mehrere offene Sessions vorhanden; bitte manuell prüfen: %s", [r[0] for r in rows])


def start_modbus_thread():
    global _thread_started
    if _thread_started:
        return
    _thread_started = True

    t = threading.Thread(target=monitor.read_registers, daemon=True)
    t.start()
    print("✔ Virtuelle Wallbox gestartet (nur Demo)" if DEMO_MODE else "✔ Modbus Thread gestartet")


@app.route("/")
def index():
    return render_template("dashboard.html", demo_mode=DEMO_MODE)


@app.route("/data")
def data():
    return jsonify(monitor.get_values())


@app.post("/demo/vehicle")
def demo_vehicle():
    # Der Endpunkt darf niemals an einer echten Wallbox funktionieren.
    if not DEMO_MODE:
        return jsonify(error="Nur im Demo-Modus verfügbar."), 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or type(payload.get("connected")) is not bool:
        return jsonify(error="Ungültiger Verbindungsstatus."), 400
    with monitor._lock:
        monitor.wallbox.set_connected(payload["connected"])
        return jsonify(connected=monitor.wallbox.connected)


def person_payload(person):
    path = CAR_IMAGES / car_image_name(person["id"])
    try:
        version = path.stat().st_mtime_ns
    except FileNotFoundError:
        version = None
    image_url = url_for("person_image", person_id=person["id"], v=version) if version is not None else None
    return {**person, "image_url": image_url}


@app.route("/persons", methods=["GET", "POST"])
def persons_endpoint():
    if request.method == "GET":
        with _persons_lock:
            return jsonify([person_payload(person) for person in load_persons()])
    data = request.get_json(silent=True)
    try:
        if not isinstance(data, dict):
            raise ValueError("Ungültige Anfrage.")
        name = parse_person_name(data.get("name"))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    try:
        with _persons_lock:
            persons = load_persons()
            # Namen bleiben eindeutig, weil die Ladehistorie Namen speichert.
            key = unicodedata.normalize("NFKC", name).casefold()
            if any(unicodedata.normalize("NFKC", " ".join(p["name"].split())).casefold() == key for p in persons):
                return jsonify(error="Eine Person mit diesem Namen existiert bereits."), 409
            person = {"id": uuid.uuid4().hex, "name": name}
            save_persons([*persons, person])
    except (OSError, ValueError, yaml.YAMLError):
        logging.exception("Person konnte nicht gespeichert werden")
        return jsonify(error="Person konnte nicht gespeichert werden."), 500
    return jsonify(person_payload(person)), 201


@app.delete("/persons/<person_id>")
def delete_person(person_id):
    """Entfernt ein Profil und sein Bild, ohne abgeschlossene Historie zu löschen."""
    # Gleiche Lock-Reihenfolge wie im Monitor; kein Start oder Bild-Upload
    # kann zwischen der Prüfung und dem Entfernen erfolgen.
    with monitor._lock, _persons_lock:
        persons = load_persons()
        person = next((p for p in persons if p.get("id") == person_id), None)
        if person is None:
            return jsonify(error="Person nicht gefunden."), 404
        if current_person and (
            current_person.get("id") == person_id or current_person.get("name") == person["name"]
        ):
            return jsonify(error="Die Person ist einer aktiven Ladung oder Freigabe zugeordnet. Bitte zuerst stoppen."), 409
        plan = read_schedule()
        if plan and plan["person_id"] == person_id:
            return jsonify(error="Für die Person ist eine Ladung geplant. Bitte zuerst die Planung abbrechen."), 409

        image_path = CAR_IMAGES / car_image_name(person_id)
        image_backup = None
        image_removed = False
        profile_removed = False
        try:
            with sqlite3.connect(DB_FILE) as conn:
                # Auch nach einem Neustart oder bei nicht wiederhergestellten
                # Sitzungen darf eine noch offene Ladung nicht verwaisen.
                if conn.execute("SELECT 1 FROM sessions WHERE end_time IS NULL AND person=? LIMIT 1",
                                (person["name"],)).fetchone():
                    return jsonify(error="Es gibt eine offene Ladung für diese Person. Bitte zuerst abschließen."), 409
                try:
                    image_backup = image_path.read_bytes()
                except FileNotFoundError:
                    pass
                # Eine gelöschte Standardperson darf keine Automatik auslösen.
                auto_reset = conn.execute("""
                    UPDATE auto_charge SET enabled=0, person_id=NULL, due=NULL, blocked=0, skipped_date=NULL
                    WHERE id=1 AND person_id=?
                """, (person_id,)).rowcount > 0
                save_persons([p for p in persons if p["id"] != person_id])
                profile_removed = True
                if image_backup is not None:
                    image_path.unlink()
                    image_removed = True
            # Datenbanktransaktion ist abgeschlossen. Historische Sitzungen
            # einschließlich des damaligen Namens bleiben unverändert.
        except (OSError, ValueError, yaml.YAMLError, sqlite3.Error):
            logging.exception("Person konnte nicht gelöscht werden")
            # Bei einem Fehler nach einem Teilschritt nach Möglichkeit den
            # ursprünglichen Zustand wiederherstellen.
            try:
                if image_removed:
                    image_path.write_bytes(image_backup)
                if profile_removed:
                    save_persons(persons)
            except (OSError, ValueError, yaml.YAMLError):
                logging.exception("Wiederherstellung nach Löschfehler fehlgeschlagen")
            return jsonify(error="Person konnte nicht gelöscht werden. Bitte erneut prüfen."), 500
        return jsonify(status="ok", auto_reset=auto_reset)


def valid_person(person_id):
    return next((p for p in load_persons() if p.get("id") == person_id), None)


@app.errorhandler(RequestEntityTooLarge)
def upload_too_large(error):
    return jsonify(error="Datei zu groß (maximal 8 MB)."), 413


@app.route("/person-image/<person_id>", methods=["GET", "POST", "DELETE"])
def person_image(person_id):
    with _persons_lock:
        return _person_image(person_id)


def _person_image(person_id):
    person = valid_person(person_id)
    if person is None:
        return jsonify(error="Person nicht gefunden."), 404
    filename = car_image_name(person_id)
    path = CAR_IMAGES / filename
    if request.method == "GET":
        return send_from_directory(CAR_IMAGES, filename, mimetype="image/webp", max_age=0)
    if request.method == "DELETE":
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logging.exception("Fahrzeugbild konnte nicht entfernt werden")
            return jsonify(error="Bild konnte nicht entfernt werden."), 500
        return jsonify(status="ok", image_url=None)
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return jsonify(error="Bitte eine Bilddatei auswählen."), 400
    if len(upload.stream.read(MAX_IMAGE_BYTES + 1)) > MAX_IMAGE_BYTES:
        return jsonify(error="Datei zu groß (maximal 8 MB)."), 413
    upload.stream.seek(0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload.stream) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    return jsonify(error="Nur JPG, PNG und WebP werden unterstützt."), 400
                if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                    return jsonify(error="Bildauflösung zu groß (maximal 25 Megapixel)."), 400
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return jsonify(error="Ungültiges oder zu großes Bild."), 400
    temp_path = None
    try:
        CAR_IMAGES.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=CAR_IMAGES, suffix=".tmp", delete=False) as tmp:
            temp_path = Path(tmp.name)
            image.save(tmp, format="WEBP", quality=88)
        os.replace(temp_path, path)
    except OSError:
        logging.exception("Fahrzeugbild konnte nicht gespeichert werden")
        return jsonify(error="Bild konnte nicht gespeichert werden."), 500
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return jsonify(status="ok", image_url=url_for("person_image", person_id=person_id, v=path.stat().st_mtime_ns))


@app.route("/sessions")
def sessions():
    # liefert dicts aus db.py
    return jsonify(get_all_sessions())


@app.route("/start", methods=["POST"])
def start_charging():
    with monitor._lock:
        global waiting_for_person, current_person
        if charging_active or current_person or read_schedule():
            return jsonify({"error": "Ladung aktiv oder geplant."}), 409
        waiting_for_person = True
        current_person = None
        return jsonify({"status": "select_person"})


@app.route("/cost-settings", methods=["GET", "POST"])
def cost_settings():
    with monitor._lock:
        if request.method == "GET":
            return jsonify(read_cost_settings())
        data = request.get_json(silent=True)
        try:
            if not isinstance(data, dict):
                raise ValueError("Ungültige Anfrage.")
            price = parse_price_ct(data.get("price_ct"))
        except ValueError as e:
            return jsonify(error=str(e)), 400
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE cost_settings SET cost_per_kwh=? WHERE id=1", (price,))
        return jsonify(read_cost_settings())


@app.route("/auto-settings", methods=["GET", "POST"])
def auto_settings():
    with monitor._lock:
        if request.method == "GET":
            return jsonify(read_auto())
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Ungültige Anfrage."), 400
        enabled, hour, person_id = data.get("enabled"), data.get("hour"), data.get("person_id")
        if type(enabled) is not bool or type(hour) is not int or not 0 <= hour <= 23:
            return jsonify(error="Uhrzeit oder Modus ungültig."), 400
        if person_id is not None and (not isinstance(person_id, str) or not valid_person(person_id)):
            return jsonify(error="Person nicht gefunden."), 400
        if enabled and not person_id:
            return jsonify(error="Standardperson wählen."), 400
        old = read_auto()
        if (enabled, hour, person_id) != (old["enabled"], old["hour"], old["person_id"]):
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("UPDATE auto_charge SET enabled=?,hour=?,person_id=?,due=NULL,blocked=0,skipped_date=NULL WHERE id=1", (int(enabled),hour,person_id))
        return jsonify(read_auto())


def set_auto_skipped(skipped):
    """Nur den angezeigten, noch zukünftigen Starttermin ändern (kein Ladebefehl)."""
    with monitor._lock:
        data = request.get_json(silent=True)
        cfg = read_auto()
        now = time.time()
        due = next_auto_check(cfg, now)
        if (not isinstance(data, dict) or type(data.get("due")) is not int
                or due is None or due <= now or data["due"] != due):
            return jsonify(error="Ladestart nicht mehr verfügbar. Bitte Ansicht aktualisieren."), 409
        day = datetime.fromtimestamp(due, SCHEDULE_TZ).date().isoformat()
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE auto_charge SET skipped_date=? WHERE id=1",
                         (day if skipped else None,))
        return jsonify(status="skipped" if skipped else "restored", due=due)


@app.route("/auto-cancel", methods=["POST"])
def auto_cancel():
    return set_auto_skipped(True)


@app.route("/auto-resume", methods=["POST"])
def auto_resume():
    return set_auto_skipped(False)


@app.route("/charge-times")
def charge_times():
    return jsonify(options=schedule_options(), timezone="Europe/Berlin")


@app.route("/select_person", methods=["POST"])
def select_person():
    with monitor._lock:
        global current_person, waiting_for_person, schedule_notice

        if charging_active or current_person or read_schedule():
            return jsonify({"error": "Ladung aktiv oder geplant."}), 409
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(error="Ungültige Anfrage."), 400
        person_id = data.get("person")
        person = next((p for p in load_persons() if p.get("id") == person_id), None)

        if not person:
            return jsonify({"error": "Person nicht gefunden"}), 400

        mode = data.get("mode", "now")
        status = monitor.values.get("status")
        if mode == "scheduled":
            due = data.get("due")
            if type(due) is not int:
                return jsonify(error="Ungültige Startzeit."), 400
            if due not in {o["due"] for o in schedule_options()}:
                return jsonify(error="Startzeit erneut wählen."), 400
            if status not in (4,6):
                return jsonify(error="Fahrzeug anschließen und Wallbox sperren."), 409
            try:
                block_auto()
                monitor.write_register(CONTROL_REGISTER, CONTROL_STOP_VALUE)
                save_schedule(person_id, due)
            except Exception:
                logging.exception("Ladeplanung fehlgeschlagen")
                return jsonify(error="Planung fehlgeschlagen."), 503
            schedule_notice = None
            waiting_for_person = False
            return jsonify(status="scheduled", due=due, person=person["name"])
        if mode != "now":
            return jsonify(error="Ungültiger Startmodus."), 400
        if status not in (2,4,6):
            return jsonify(error="Wallbox nicht gesperrt."), 409
        try:
            block_auto()
            monitor.write_register(CONTROL_REGISTER, CONTROL_ALLOW_VALUE)
        except Exception as e:
            return jsonify({"error": str(e)}), 503
        current_person = person
        waiting_for_person = False
        schedule_notice = None

        return jsonify({"status": "started", "person": current_person.get("name")})


@app.route("/stop", methods=["POST"])
def stop_charging():
    global current_person, waiting_for_person, schedule_notice
    with monitor._lock:
        block_auto()
        plan = read_schedule()
        if plan and plan["phase"] in ("pending", "auto_pending"):
            clear_schedule()  # keine künftige Freigabe, auch wenn Modbus offline ist
            schedule_notice = "Planung abgebrochen."
            waiting_for_person = False
            return jsonify(status="cancelled")
        # Wallbox sperren
        try:
            monitor.write_register(CONTROL_REGISTER, CONTROL_STOP_VALUE)
            if plan:
                clear_schedule()
                schedule_notice = "Planung abgebrochen."
            # Ende erst mit gültiger Messung und bestätigtem Statuswechsel.
            if not charging_active:
                current_person = None
                waiting_for_person = False
        except Exception as e:
            return jsonify({"error": str(e)}), 503
        return jsonify({"status": "stopped"})

@app.route("/monthly_summary")
def monthly_summary():
    return jsonify(get_current_month_summary())


@app.route("/monthly_totals")
def monthly_totals():
    return jsonify(get_monthly_totals())

@app.route("/set_power", methods=["POST"])
def set_power():
    with monitor._lock:
        data = request.get_json(silent=True) or {}
        level = str(data.get("level", "")).upper().strip()

        # kW-Stufen -> Ampere
        power_step_map = {
            "2": 30,     # ca. 2.1 kW
            "4": 60,     # ca. 4.1 kW
            "6": 90,     # ca. 6.2 kW
            "8": 120,    # ca. 8.3 kW
            "MAX": 160   # ca. 11 kW
        }

        # Nur während aktivem Laden erlauben
        values = monitor.get_values()
        status = values.get("raw_status")

        if status != CHARGING_STATUS_CODE:
            return jsonify({
                "error": "Leistung kann nur während aktivem Laden geändert werden"
            }), 400

        if level not in power_step_map:
            return jsonify({
                "error": "Ungültige Leistungsstufe"
            }), 400

        ampere = power_step_map[level]

        try:
            monitor.write_register(CONTROL_REGISTER, ampere)

            return jsonify({
                "status": "ok",
                "selected_level": level,
                "ampere": ampere
            })
        except Exception as e:
            return jsonify({
                "error": f"Fehler beim Setzen der Ladeleistung: {str(e)}"
            }), 500

if __name__ == "__main__":
    def shutdown(signum, frame):
        monitor._stop_thread = True
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        restore_open_session()
        if DEMO_MODE:
            logging.info("DEMO: keine serielle Verbindung; alle Daten sind fiktiv.")
        start_modbus_thread()
        app.run(host=os.environ.get("WALLBOX_HOST", "127.0.0.1"), port=int(os.environ.get("WALLBOX_PORT", "5000")), debug=False, use_reloader=False)
    finally:
        monitor.stop()
