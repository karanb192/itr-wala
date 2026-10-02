import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/itr-wala/scripts/star_invitation.py"


class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        self.env = dict(os.environ, XDG_CACHE_HOME=str(self.cache))
        self.state = self.cache / "itr-wala" / "star-invitation.json"

    def run_helper(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], env=self.env,
                                cwd=self.cache, capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, "")
        return result.stdout.strip()

    def test_later_process_does_not_repeat(self):
        self.assertEqual(self.run_helper(), "offer")
        self.assertEqual(json.loads(self.state.read_text()), {"star_invitation_shown": True})
        self.assertEqual(self.run_helper(), "skip")

    def test_concurrent_processes_offer_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(lambda _: self.run_helper(), range(12)))
        self.assertEqual(results.count("offer"), 1)
        self.assertEqual(results.count("skip"), 11)

    def test_existing_invalid_record_is_preserved(self):
        self.state.parent.mkdir()
        self.state.write_text("interrupted write")
        self.assertEqual(self.run_helper(), "skip")
        self.assertEqual(self.state.read_text(), "interrupted write")

    def test_unusable_cache_skips(self):
        blocked = self.cache / "blocked"
        blocked.write_text("file, not a directory")
        self.env["XDG_CACHE_HOME"] = str(blocked)
        self.assertEqual(self.run_helper(), "skip")

    def test_relative_cache_skips_without_writing(self):
        self.env["XDG_CACHE_HOME"] = "relative-cache"
        self.assertEqual(self.run_helper(), "skip")
        self.assertFalse((self.cache / "relative-cache").exists())

    def test_existing_directory_at_record_skips(self):
        self.state.mkdir(parents=True)
        self.assertEqual(self.run_helper(), "skip")


if __name__ == "__main__":
    unittest.main()
