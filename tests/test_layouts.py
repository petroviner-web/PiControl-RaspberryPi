"""Lightweight consistency checks without a Qt graphical environment."""
from pathlib import Path
import unittest
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


class LayoutTests(unittest.TestCase):
    def test_qt_designer_forms_are_valid_xml(self):
        forms = sorted((ROOT / "ui").glob("*.ui"))
        self.assertGreaterEqual(len(forms), 6)
        for form in forms:
            with self.subTest(form=form.name):
                self.assertEqual(ElementTree.parse(form).getroot().tag, "ui")

    def test_app_and_gui_files_are_present(self):
        for name in ("main.py", "pi_server.py", "remote_backend.py", "protocol_controls.py", "styles.qss"):
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file())


if __name__ == "__main__":
    unittest.main()
