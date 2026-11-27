"""Hardwarefreie Regressionstests der Personenverwaltung."""
import io
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[1]


class TestPersons(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        shutil.copy(ROOT / "wallbox_monitor.py", root / "wallbox_monitor.py")
        sys.path.insert(0, str(root))
        self.addCleanup(sys.path.remove, str(root))
        shutil.copytree(ROOT / "templates", root / "templates")
        shutil.copytree(ROOT / "static", root / "static")
        spec = importlib.util.spec_from_file_location("wallbox_test", root / "wallbox_monitor.py")
        self.appmod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.appmod
        self.addCleanup(sys.modules.pop, spec.name, None)
        with patch.dict(os.environ, {"WALLBOX_DEMO": "0"}):
            spec.loader.exec_module(self.appmod)
        self.appmod.monitor.write_register = Mock()
        self.client = self.appmod.app.test_client()

    def add(self, name):
        return self.client.post("/persons", json={"name": name})

    def test_fresh_installation(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("Person hinzufügen".encode(), self.client.get("/").data)
        self.assertIn(b'languageSelect', self.client.get("/").data)
        with self.client.get("/static/i18n.js") as translations:
            self.assertEqual(translations.status_code, 200)
            self.assertIn(b"changeLanguage", translations.data)
        self.assertEqual(self.client.get("/?lang=fr&settings=persons").status_code, 200)
        self.assertEqual(self.client.get("/persons").json, [])
        self.assertEqual(self.client.get("/sessions").json, [])
        self.assertFalse(self.client.get("/auto-settings").json["enabled"])
        self.assertFalse(self.appmod.PERSONS_FILE.exists())
        self.assertFalse((self.appmod.BASE_DIR / "demo").exists())
        self.assertFalse(self.client.get("/data").json["demo_mode"])
        self.assertEqual(self.client.post("/demo/vehicle", json={"connected": False}).status_code, 404)

    def test_creation_and_persistence(self):
        first = self.add("  Alex  Beispiel  ")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json["name"], "Alex Beispiel")
        self.assertIsNone(first.json["image_url"])
        second = self.add("Mika")
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.json["id"], second.json["id"])
        self.assertEqual(self.client.get("/persons").json, [first.json, second.json])
        stored = yaml.safe_load(self.appmod.PERSONS_FILE.read_text(encoding="utf-8"))
        self.assertEqual(stored["persons"], [
            {k: row[k] for k in ("id", "name")} for row in (first.json, second.json)
        ])

    def test_duplicate_names(self):
        self.assertEqual(self.add("Alex Beispiel").status_code, 201)
        self.assertEqual(self.add("  ALEX   Beispiel ").status_code, 409)
        self.assertEqual(len(self.client.get("/persons").json), 1)

    def test_invalid_input(self):
        for value in ("", " ", "x" * 81, "A\nB", 123, None, ["Alex"]):
            with self.subTest(value=value):
                self.assertEqual(self.add(value).status_code, 400)
        self.assertEqual(self.client.post("/persons", json=["Alex"]).status_code, 400)
        self.assertEqual(self.client.get("/persons").json, [])

    def test_concurrent_requests(self):
        def create(name):
            with self.appmod.app.test_client() as c:
                return c.post("/persons", json={"name": name}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create, ["Alex", "Mika", "Sam", "Kim"]))
            duplicate = list(pool.map(create, ["Robin", "Robin"]))
        self.assertEqual(results, [201] * 4)
        self.assertEqual(sorted(duplicate), [201, 409])
        self.assertEqual(len(self.client.get("/persons").json), 5)

    def test_usable_for_auto_and_manual_selection(self):
        person = self.add("Alex").json
        person_id = person["id"]
        result = self.client.post("/auto-settings", json={"enabled": True, "hour": 1, "person_id": person_id})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["person_id"], person_id)
        self.appmod.monitor.values["status"] = 4
        result = self.client.post("/select_person", json={"person": person_id})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get("/data").json["current_person_id"], person_id)
        self.appmod.monitor.write_register.assert_called_once()

    def test_image_lifecycle(self):
        person = self.add("Alex").json
        path = "/person-image/" + person["id"]
        image = io.BytesIO()
        Image.new("RGB", (100, 50)).save(image, format="PNG")
        image.seek(0)
        response = self.client.post(path, data={"image": (image, "example.png")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/persons").json[0]["image_url"], response.json["image_url"])
        with self.client.get(path) as image_response:
            self.assertEqual(image_response.status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 200)
        self.assertIsNone(self.client.get("/persons").json[0]["image_url"])

    def test_delete_removes_profile_and_image_preserves_history(self):
        m = self.appmod
        person = self.add("Alex").json
        other = self.add("Mika").json
        path = "/persons/" + person["id"]
        image = io.BytesIO()
        Image.new("RGB", (100, 50)).save(image, format="PNG")
        image.seek(0)
        image_url = "/person-image/" + person["id"]
        self.assertEqual(self.client.post(image_url, data={"image": (image, "example.png")}).status_code, 200)
        image_file = m.CAR_IMAGES / m.car_image_name(person["id"])
        self.assertTrue(image_file.exists())
        session = m.start_session(person["name"], 100.0)
        m.end_session(session, 120.0, 8.0)
        history = self.client.get("/sessions").json
        self.assertEqual(self.client.post("/auto-settings", json={"enabled": True, "hour": 1, "person_id": person["id"]}).status_code, 200)
        response = self.client.delete(path)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["auto_reset"])
        self.assertEqual(self.client.get("/persons").json, [other])
        self.assertFalse(image_file.exists())
        self.assertEqual(self.client.get(image_url).status_code, 404)
        self.assertEqual(self.client.get("/sessions").json, history)
        cfg = self.client.get("/auto-settings").json
        self.assertFalse(cfg["enabled"])
        self.assertIsNone(cfg["person_id"])
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertEqual(self.client.post("/select_person", json={"person": person["id"]}).status_code, 400)
        self.assertEqual(self.client.post("/auto-settings", json={"enabled": True, "hour": 1, "person_id": person["id"]}).status_code, 400)
        self.assertIn("Person löschen".encode(), self.client.get("/").data)
        self.assertEqual(m.load_persons(), [{"id": other["id"], "name": "Mika"}])
        m.monitor.write_register.assert_not_called()

    def test_delete_blocks_current_person(self):
        person = self.add("Alex").json
        self.appmod.monitor.values["status"] = 4
        self.assertEqual(self.client.post("/select_person", json={"person": person["id"]}).status_code, 200)
        self.assertEqual(self.client.delete("/persons/" + person["id"]).status_code, 409)
        self.assertEqual(self.client.get("/persons").json, [person])

    def test_delete_blocks_scheduled_person_only(self):
        person = self.add("Alex").json
        other = self.add("Mika").json
        self.appmod.monitor.values["status"] = 4
        due = self.appmod.schedule_options()[0]["due"]
        self.assertEqual(self.client.post("/select_person", json={"person": person["id"], "mode": "scheduled", "due": due}).status_code, 200)
        self.assertEqual(self.client.delete("/persons/" + person["id"]).status_code, 409)
        self.assertEqual(self.client.delete("/persons/" + other["id"]).status_code, 200)
        self.assertEqual(self.client.get("/persons").json, [person])
        self.assertEqual(self.appmod.read_schedule()["person_id"], person["id"])

    def test_delete_blocks_unrestored_open_session(self):
        person = self.add("Alex").json
        self.appmod.start_session(person["name"], 100)
        self.assertEqual(self.client.delete("/persons/" + person["id"]).status_code, 409)
        self.assertEqual(self.client.get("/persons").json, [person])

    def test_delete_preserves_other_auto_person(self):
        person = self.add("Alex").json
        other = self.add("Mika").json
        self.assertEqual(self.client.post("/auto-settings", json={"enabled": True, "hour": 2, "person_id": other["id"]}).status_code, 200)
        cfg = self.client.get("/auto-settings").json
        response = self.client.delete("/persons/" + person["id"])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json["auto_reset"])
        self.assertEqual(self.client.get("/auto-settings").json, cfg)

    def test_delete_rolls_back_if_image_removal_fails(self):
        m = self.appmod
        person = self.add("Alex").json
        m.CAR_IMAGES.mkdir(parents=True, exist_ok=True)
        image_file = m.CAR_IMAGES / m.car_image_name(person["id"])
        Image.new("RGB", (50, 50)).save(image_file, format="WEBP")
        self.assertEqual(self.client.post("/auto-settings", json={"enabled": True, "hour": 1, "person_id": person["id"]}).status_code, 200)
        cfg = self.client.get("/auto-settings").json
        unlink = Path.unlink
        def fail_image_only(path, *args, **kwargs):
            if path == image_file:
                raise PermissionError("Simulierter Zugriffskonflikt")
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_image_only):
            with self.assertLogs(level="ERROR"):
                result = self.client.delete("/persons/" + person["id"])
        self.assertEqual(result.status_code, 500)
        self.assertTrue(image_file.exists())
        self.assertEqual(self.client.get("/persons").json[0]["id"], person["id"])
        self.assertEqual(self.client.get("/auto-settings").json, cfg)


if __name__ == "__main__":
    unittest.main()
