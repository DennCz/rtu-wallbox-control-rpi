"""Tests für isolierte Demo-Daten, Bilder und virtuelle Ladebefehle."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import importlib.util
from pathlib import Path
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo import DEMO_PERSON_NAME, SimulatedWallbox, example_sessions, data_directory


class TestDemo(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        shutil.copy(ROOT / "wallbox_monitor.py", root / "wallbox_monitor.py")
        shutil.copytree(ROOT / "demo", root / "demo", ignore=shutil.ignore_patterns("data", "__pycache__"))
        shutil.copytree(ROOT / "templates", root / "templates")
        shutil.copytree(ROOT / "static", root / "static")
        spec = importlib.util.spec_from_file_location("wallbox_demo_test", root / "wallbox_monitor.py")
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.mod
        self.addCleanup(sys.modules.pop, spec.name, None)
        # Eine Verbindung oder auch eine Konstruktion des echten Modbus-Clients
        # muss in der Demo ausgeschlossen sein.
        with patch.dict(os.environ, {"WALLBOX_DEMO": "1"}), patch(
            "pymodbus.client.ModbusSerialClient", side_effect=AssertionError("Echte Hardware angesprochen")
        ):
            spec.loader.exec_module(self.mod)
        self.client = self.mod.app.test_client()
        self.root = root

    def cycle(self):
        self.mod.monitor._stop_thread = False
        with patch.object(self.mod.time, "sleep", side_effect=lambda _: setattr(self.mod.monitor, "_stop_thread", True)):
            self.mod.monitor.read_registers()

    def test_seed_and_isolation(self):
        m = self.mod
        self.assertIsInstance(m.monitor.wallbox, SimulatedWallbox)
        self.assertEqual(m.DB_FILE.parent, self.root / "demo" / "data")
        self.assertFalse((self.root / "demo_data").exists())
        self.assertFalse((self.root / "wallbox_sessions.db").exists())
        self.assertFalse((self.root / "persons.yaml").exists())
        people = self.client.get("/persons").json
        self.assertEqual([p["name"] for p in people], [DEMO_PERSON_NAME])
        rows = self.client.get("/sessions").json
        months = {r["start_time"][:7] for r in rows}
        self.assertEqual(len(months), 3)
        self.assertEqual(len(self.client.get("/monthly_totals").json), 3)
        self.assertTrue(all(r["end_time"] and datetime.fromisoformat(r["end_time"]) <= datetime.now() for r in rows))
        self.assertTrue(all(r["person"] == DEMO_PERSON_NAME for r in rows))
        m.seed_demo_data()
        self.assertEqual(self.client.get("/sessions").json, rows)
        self.assertEqual(self.client.get("/persons").json, people)
        self.assertFalse(self.client.get("/auto-settings").json["enabled"])

    def test_images_and_demo_banner(self):
        person = self.client.get("/persons").json[0]
        with self.client.get(person["image_url"]) as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, (ROOT / "demo/demo-vehicle.webp").read_bytes())
        with self.client.get("/static/wallbox-idle.webp") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/static/demo-vehicle.webp").status_code, 404)
        self.assertIn(b"Virtuelle Wallbox", self.client.get("/").data)
        self.assertIn(b"demoVehicleBtn", self.client.get("/").data)
        self.cycle()
        self.assertTrue(self.client.get("/data").json["demo_connected"])
        self.assertEqual(self.client.post("/demo/vehicle", json={"connected": False}).status_code, 200)
        self.cycle()
        self.assertEqual(self.client.get("/data").json["raw_status"], 2)
        self.assertFalse(self.client.get("/data").json["demo_connected"])
        self.assertEqual(self.client.post("/demo/vehicle", json={"connected": True}).status_code, 200)
        self.cycle()
        self.assertEqual(self.client.get("/data").json["raw_status"], 6)
        self.assertEqual(self.client.post("/demo/vehicle", json={"connected": "yes"}).status_code, 400)

    def test_virtual_charge(self):
        self.cycle()
        person = self.client.get("/persons").json[0]
        count = len(self.client.get("/sessions").json)
        response = self.client.post("/select_person", json={"person": person["id"]})
        self.assertEqual(response.status_code, 200)
        self.cycle()
        data = self.client.get("/data").json
        self.assertEqual(data["raw_status"], 7)
        self.assertTrue(data["charging_active"])
        self.assertGreater(data["power_kw"], 0)
        self.assertEqual(len(self.client.get("/sessions").json), count + 1)
        self.assertEqual(self.client.post("/set_power", json={"level": "4"}).status_code, 200)
        self.cycle()
        self.assertAlmostEqual(self.client.get("/data").json["power_kw"], 4.14, places=2)
        self.assertEqual(self.client.post("/stop").status_code, 200)
        for _ in range(self.mod.END_DEBOUNCE_READS):
            self.cycle()
        self.assertFalse(self.client.get("/data").json["charging_active"])
        self.assertIsNotNone(self.client.get("/sessions").json[0]["end_time"])

    def configure_automatic(self):
        m = self.mod
        person = self.client.get("/persons").json[0]
        when = int(datetime(2026, 11, 27, 1, tzinfo=m.SCHEDULE_TZ).timestamp())
        before = when - 3600
        with patch.object(m.time, "time", return_value=before):
            result = self.client.post("/auto-settings", json={"enabled": True, "hour": 1, "person_id": person["id"]})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(self.client.get("/data").json["auto_pending"]["due"], when)
        return before, when, person

    def test_skip_restore_persists_and_starts_only_at_due(self):
        m = self.mod
        before, due, person = self.configure_automatic()
        with patch.object(m.time, "time", return_value=before):
            plan = self.client.get("/data").json["auto_pending"]
            self.assertFalse(plan["skipped"])
            result = self.client.post("/auto-cancel", json={"due": due})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["status"], "skipped")
            self.assertIsNone(m.read_auto()["last_check_date"])
            self.assertEqual(m.read_auto()["skipped_date"], "2026-11-27")
            # Der Termin bleibt derselbe; Datenbank-Neuinitialisierung verliert ihn nicht.
            m.init_db()
            self.assertEqual(self.client.get("/data").json["auto_pending"]["due"], due)
            self.assertTrue(self.client.get("/data").json["auto_pending"]["skipped"])
            self.assertTrue(self.client.get("/auto-settings").json["enabled"])
            self.cycle()
            self.assertEqual(m.monitor.wallbox.level, 0)
            result = self.client.post("/auto-resume", json={"due": due})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["status"], "restored")
            self.assertEqual(self.client.get("/data").json["auto_pending"]["due"], due)
            self.assertFalse(self.client.get("/data").json["auto_pending"]["skipped"])
            self.assertIsNone(m.read_auto()["skipped_date"])
            self.cycle()
            self.assertEqual(m.monitor.wallbox.level, 0)
        with patch.object(m.time, "time", return_value=due+5):
            self.cycle()
            self.cycle()
            self.assertTrue(self.client.get("/data").json["charging_active"])
            self.assertEqual(m.current_person["id"], person["id"])
            self.assertEqual(m.read_auto()["last_check_date"], "2026-11-27")
            self.assertEqual(self.client.get("/data").json["auto_pending"]["due"], due+86400)

    def test_skip_consumed_and_next_day_automatic_still_enabled(self):
        m = self.mod
        before, due, _ = self.configure_automatic()
        with patch.object(m.time, "time", return_value=before):
            self.assertEqual(self.client.post("/auto-cancel", json={"due": due}).status_code, 200)
        with patch.object(m.time, "time", return_value=due+5):
            # Keine kurzfristige Rücknahme nach Erreichen der Startzeit.
            self.assertEqual(self.client.post("/auto-resume", json={"due": due}).status_code, 409)
            self.cycle()
            self.assertEqual(m.monitor.wallbox.level, 0)
            self.assertIsNone(m.read_schedule())
            self.assertEqual(m.read_auto()["last_check_date"], "2026-11-27")
            self.assertIsNone(m.read_auto()["skipped_date"])
            plan = self.client.get("/data").json["auto_pending"]
            self.assertEqual(plan["due"], due+86400)
            self.assertFalse(plan["skipped"])
            # Eine alte Browseransicht darf nicht den neuen Termin ändern.
            self.assertEqual(self.client.post("/auto-cancel", json={"due": due}).status_code, 409)
            self.assertFalse(self.client.get("/data").json["auto_pending"]["skipped"])
        with patch.object(m.time, "time", return_value=due+86405):
            self.cycle()
            self.cycle()
            self.assertTrue(self.client.get("/data").json["charging_active"])

    def test_no_vehicle_no_delayed_start_and_skip_undo_accessible(self):
        m = self.mod
        before, due, _ = self.configure_automatic()
        with patch.object(m.time, "time", return_value=before):
            self.client.post("/demo/vehicle", json={"connected": False})
            self.cycle()
            data = self.client.get("/data").json
            self.assertEqual(data["raw_status"], 2)
            self.assertEqual(data["auto_pending"]["due"], due)
            self.assertEqual(self.client.post("/auto-cancel", json={"due": due}).status_code, 200)
            self.assertTrue(self.client.get("/data").json["auto_pending"]["skipped"])
            self.assertEqual(self.client.post("/auto-resume", json={"due": due}).status_code, 200)
        with patch.object(m.time, "time", return_value=due+5):
            self.cycle()
            self.assertEqual(m.monitor.wallbox.level, 0)
            self.assertEqual(m.read_auto()["last_check_date"], "2026-11-27")
            self.client.post("/demo/vehicle", json={"connected": True})
            self.cycle()
            self.assertEqual(m.monitor.wallbox.level, 0)
            self.assertIsNone(m.read_schedule())
        with patch.object(m.time, "time", return_value=due+61):
            self.cycle()
            self.assertEqual(m.monitor.wallbox.level, 0)

    def test_manual_schedule_has_priority_over_auto(self):
        m = self.mod
        before, due, person = self.configure_automatic()
        with patch.object(m.time, "time", return_value=before):
            self.cycle()
            manual_due = due+3600
            response = self.client.post("/select_person", json={
                "person": person["id"], "mode": "scheduled", "due": manual_due})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.get("/data").json["auto_pending"]["due"], due)
            self.assertEqual(self.client.post("/auto-cancel", json={"due": due}).status_code, 200)
            self.assertEqual(self.client.post("/auto-resume", json={"due": due}).status_code, 200)
            self.assertEqual(m.read_schedule()["due"], manual_due)
        with patch.object(m.time, "time", return_value=due+5):
            self.cycle()
            self.assertEqual(m.monitor.wallbox.level, 0)
            self.assertEqual(m.read_schedule()["due"], manual_due)
        with patch.object(m.time, "time", return_value=manual_due+5):
            self.cycle()
            self.cycle()
            self.assertTrue(self.client.get("/data").json["charging_active"])

    def test_skip_reset_on_changed_settings_and_legacy_history_preserved(self):
        m = self.mod
        before, due, person = self.configure_automatic()
        with patch.object(m.time, "time", return_value=before):
            self.assertEqual(self.client.post("/auto-cancel", json={"due": due}).status_code, 200)
            # Identische Einstellungen behalten die Ausnahme.
            self.client.post("/auto-settings", json={"enabled": True, "hour": 1, "person_id": person["id"]})
            self.assertTrue(self.client.get("/data").json["auto_pending"]["skipped"])
            self.client.post("/auto-settings", json={"enabled": True, "hour": 2, "person_id": person["id"]})
            self.assertIsNone(m.read_auto()["skipped_date"])
            self.assertFalse(self.client.get("/data").json["auto_pending"]["skipped"])
            # Migration: alte erledigte (oder übersprungene) Tage niemals reaktivieren.
            with sqlite3.connect(m.DB_FILE) as db:
                db.execute("ALTER TABLE auto_charge DROP COLUMN skipped_date")
                db.execute("UPDATE auto_charge SET last_check_date='2026-11-27'")
            m.init_db()
            self.assertEqual(m.read_auto()["last_check_date"], "2026-11-27")
            self.assertIsNone(m.read_auto()["skipped_date"])
            self.assertEqual(self.client.get("/data").json["auto_pending"]["due"], due+3600+86400)
            self.assertEqual(self.client.post("/auto-resume", json={"due": due}).status_code, 409)

    def test_deleted_demo_person_stays_deleted(self):
        person = self.client.get("/persons").json[0]
        image_path = self.mod.CAR_IMAGES / self.mod.car_image_name(person["id"])
        self.assertTrue(image_path.exists())
        history = self.client.get("/sessions").json
        self.assertEqual(self.client.delete("/persons/" + person["id"]).status_code, 200)
        self.assertFalse(image_path.exists())
        self.assertEqual(self.client.get("/persons").json, [])
        self.mod.seed_demo_data()
        self.assertEqual(self.client.get("/persons").json, [])
        self.assertEqual(self.client.get("/sessions").json, history)
        self.assertFalse(image_path.exists())

    def test_legacy_demo_data_migration_preserves_existing_state(self):
        person = self.client.get("/persons").json[0]
        history = self.client.get("/sessions").json
        # Die gelöschte Demo-Person soll auch nach einer Migration nicht
        # wieder angelegt werden.
        self.assertEqual(self.client.delete("/persons/" + person["id"]).status_code, 200)
        legacy = self.root / "demo_data"
        old_location = self.root / "demo" / "data"
        old_location.rename(legacy)
        self.assertFalse(old_location.exists())
        self.assertEqual(data_directory(self.root), old_location)
        self.assertFalse(legacy.exists())
        self.mod.seed_demo_data()
        self.assertEqual(self.client.get("/persons").json, [])
        self.assertEqual(self.client.get("/sessions").json, history)

    def test_separate_old_demo_directory_is_not_overwritten(self):
        legacy = self.root / "demo_data"
        legacy.mkdir()
        (legacy / "sentinel.txt").write_text("alte Daten", encoding="utf-8")
        with self.assertLogs(level="WARNING"):
            self.assertEqual(data_directory(self.root), self.root / "demo" / "data")
        self.assertEqual((legacy / "sentinel.txt").read_text(encoding="utf-8"), "alte Daten")
        self.assertTrue(self.client.get("/sessions").json)

    def test_example_month_boundaries_and_costs(self):
        for now in (datetime(2026, 11, 27), datetime(2027, 1, 1), datetime(2027, 1, 1, 12), datetime(2027, 1, 1, 19)):
            with self.subTest(now=now):
                rows = example_sessions(now)
                self.assertEqual(len({row[1][:7] for row in rows}), 3)
                for name, start, end, start_kwh, end_kwh, peak, kwh, cost, price in rows:
                    self.assertLess(datetime.fromisoformat(start), datetime.fromisoformat(end))
                    self.assertLessEqual(datetime.fromisoformat(end), now)
                    self.assertAlmostEqual(end_kwh-start_kwh, kwh, places=3)
                    self.assertEqual(Decimal(str(cost)), (Decimal(str(kwh))*Decimal(str(price))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


if __name__ == "__main__":
    unittest.main()
