"""Isolierte, deterministische Beispieldaten und eine rein virtuelle Wallbox."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import time
import logging
import shutil
import sqlite3
from pathlib import Path

DEMO_PERSON_ID = "demo-person"
DEMO_PERSON_NAME = "Alex Beispiel (Demo)"
DEMO_PRICE = Decimal("0.29")


def data_directory(base_dir):
    """Hält Demo-Laufzeitdaten im Demo-Ordner und übernimmt alte Daten einmalig."""
    base_dir = Path(base_dir)
    target = base_dir / "demo" / "data"
    previous = base_dir / "demo_data"
    if previous.is_dir() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        previous.rename(target)
    elif previous.is_dir() and target.exists():
        logging.warning("Altes demo_data und demo/data vorhanden; alte Daten bleiben unverändert.")
    target.mkdir(parents=True, exist_ok=True)
    return target


def seed_data(db_file, images_dir, load_persons, save_persons, car_image_name, demo_asset):
    """Initialisiert einmalig ausschließlich die isolierten Beispieldaten."""
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS demo_seed (id INTEGER PRIMARY KEY CHECK(id=1))")
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT id FROM demo_seed WHERE id=1").fetchone():
            return
        people = load_persons()
        if not any(p["id"] == DEMO_PERSON_ID for p in people):
            save_persons([*people, {"id": DEMO_PERSON_ID, "name": DEMO_PERSON_NAME}])
        images_dir.mkdir(parents=True, exist_ok=True)
        image_path = images_dir / car_image_name(DEMO_PERSON_ID)
        if not image_path.exists():
            shutil.copyfile(demo_asset, image_path)
        conn.executemany("""
            INSERT INTO sessions (person, start_time, end_time, energy_total_start,
                energy_total_end, max_power, verbrauch_total, total_costs, cost_per_kwh)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, example_sessions())
        conn.execute("UPDATE cost_settings SET cost_per_kwh=? WHERE id=1", (float(DEMO_PRICE),))
        conn.execute("INSERT INTO demo_seed(id) VALUES (1)")


def create_wallbox(db_file, registers, control_register, offset_minus_one=False):
    with sqlite3.connect(db_file) as conn:
        meter = conn.execute("""
            SELECT MAX(COALESCE(energy_total_end, energy_total_start, 0)) FROM sessions
        """).fetchone()[0]
    return SimulatedWallbox(registers, control_register, max(1250, meter or 0), offset_minus_one)


def example_sessions(now=None):
    """Erzeugt drei Kalendermonate mit ausschließlich vergangenen Ladevorgängen."""
    now = now or datetime.now()
    current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # In den ersten Stunden eines Monats die letzten drei abgeschlossenen Monate
    # verwenden, damit keine erfundene Sitzung in der Zukunft liegt.
    latest = current_month if now >= current_month + timedelta(hours=5) else (current_month - timedelta(days=1)).replace(day=1)
    starts = [latest]
    for _ in range(2):
        starts.append((starts[-1] - timedelta(days=1)).replace(day=1))
    rows = []
    meter = Decimal("1250.000")
    consumption_values = [Decimal(x) for x in ("24.850", "18.420", "36.710", "12.360", "29.050", "41.280", "21.670", "33.190", "16.840", "27.560")]
    prices = [Decimal("0.27"), Decimal("0.28"), DEMO_PRICE]
    for month_i, month in enumerate(reversed(starts)):
        next_month = (month + timedelta(days=32)).replace(day=1)
        for i, day_offset in enumerate((0, 3, 6, 9, 12, 15, 18, 21, 24, 27)):
            start = month + timedelta(days=day_offset, hours=18 + (i % 3), minutes=(12 + 13*i) % 60)
            if start >= next_month:
                continue
            factor = (Decimal("0.91"), Decimal("1.07"), Decimal("1.00"))[month_i]
            consumption = (consumption_values[(i + month_i*3) % len(consumption_values)] * factor).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            peak = Decimal(("11.00", "8.20", "6.20", "11.00")[i % 4])
            # Durchschnittliche Leistung unterhalb des jeweiligen Spitzenwertes.
            duration = timedelta(minutes=round(float(consumption / (peak * Decimal("0.78")) * 60)))
            # Auch am ersten Tag bereits vergangene Stunden verwenden.
            if i == 0 and month == current_month and start + duration > now:
                start = month + timedelta(minutes=10)
            end = start + duration
            if end > now or end > next_month:
                continue
            price = prices[month_i]
            end_meter = meter + consumption
            cost = (consumption * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            rows.append((DEMO_PERSON_NAME, start.isoformat(), end.isoformat(),
                         float(meter), float(end_meter), float(peak), float(consumption),
                         float(cost), float(price)))
            meter = end_meter
    return rows


class SimulatedWallbox:
    """Kompatible Register-Schnittstelle, ohne irgendeine serielle Verbindung."""

    def __init__(self, registers, control_register, energy_kwh, offset_minus_one=False):
        self.client = self  # Der vorhandene Monitor ruft client.connect() auf.
        self.registers = registers
        self.control_register = control_register
        self.offset_minus_one = offset_minus_one
        self.connected = True
        self.level = 0
        self.energy_wh = float(energy_kwh) * 1000
        self.boot_wh = self.energy_wh
        self.last_sample = time.monotonic()
        self.snapshot = {}

    @property
    def power_w(self):
        # Nur ein anschaulicher virtueller Messwert, keine Hardwarevorgabe.
        return round(self.level / 10 * 230 * 3) if self.connected else 0

    def _advance(self):
        now = time.monotonic()
        self.energy_wh += self.power_w * max(0, now - self.last_sample) / 3600
        self.last_sample = now

    def connect(self):
        self._advance()
        status = (7 if self.level else 6) if self.connected else (3 if self.level else 2)
        total = int(self.energy_wh)
        poweron = int(self.energy_wh - self.boot_wh)
        current = self.level if self.connected else 0
        values = dict(status=status, current_L1=current, current_L2=current, current_L3=current,
                      pcb_temp=270, voltage_L1=230, voltage_L2=231, voltage_L3=229,
                      power=self.power_w, energy_poweron_high=(poweron >> 16) & 65535,
                      energy_poweron_low=poweron & 65535, energy_total_high=(total >> 16) & 65535,
                      energy_total_low=total & 65535)
        self.snapshot = {address - int(self.offset_minus_one): values[name] for name, address in self.registers.items()}
        return True

    def close(self):
        self._advance()

    def read_input_register(self, address, count=1):
        return [self.snapshot[address + i] for i in range(count)]

    read_holding_register = read_input_register

    def write_register(self, address, value):
        if address != self.control_register or not 0 <= value <= 160:
            raise ValueError("Ungültiger virtueller Steuerbefehl")
        self._advance()
        self.level = value

    def set_connected(self, connected):
        self._advance()
        self.connected = connected
        if not connected:
            self.level = 0
