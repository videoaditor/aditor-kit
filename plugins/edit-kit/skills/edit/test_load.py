"""python3 test_load.py  (stdlib unittest)"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import load

B1 = {"version": "aaaaaaaaaaaa", "files": {"RULES.md": "rules", "skills/rough-cut/SKILL.md": "cut", "skills/rough-cut/rc.py": "print(1)"}}

class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
    def tearDown(self):
        self.tmp.cleanup()
    def test_writes_a_fake_bundle(self):
        self.assertEqual(load.write_bundle(B1, self.cache), "written")
        self.assertEqual((self.cache / "skills/rough-cut/SKILL.md").read_text(), "cut")
        self.assertEqual(load.cached_version(self.cache), "aaaaaaaaaaaa")
        self.assertTrue(os.access(self.cache / "skills/rough-cut/rc.py", os.X_OK))
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["cache"], "no temp folder left behind")
    def test_current_leaves_the_cache_alone(self):
        load.write_bundle(B1, self.cache)
        (self.cache / "marker").write_text("x")
        self.assertEqual(load.write_bundle({"version": "aaaaaaaaaaaa", "current": True}, self.cache), "current")
        self.assertTrue((self.cache / "marker").exists())
        self.assertEqual(load.cached_version(self.cache), "aaaaaaaaaaaa")
    def test_a_new_version_replaces_the_cache(self):
        load.write_bundle(B1, self.cache)
        load.write_bundle({"version": "bbbbbbbbbbbb", "files": {"RULES.md": "new"}}, self.cache)
        self.assertEqual(sorted(p.name for p in self.cache.rglob("*") if p.is_file()), ["RULES.md", "VERSION"])
        self.assertEqual(load.cached_version(self.cache), "bbbbbbbbbbbb")
    def test_bad_paths_are_refused_and_nothing_is_written(self):
        load.write_bundle(B1, self.cache)
        for bad in ["../evil", "a/../../evil", "/etc/evil", "C:/evil", "a\\b", "", "skills/../../x", ".", "a/", "VERSION", "./x", "a//b"]:
            with self.assertRaises(ValueError, msg=bad):
                load.write_bundle({"version": "cccccccccccc", "files": {"ok.md": "x", bad: "y"}}, self.cache)
        self.assertEqual(load.cached_version(self.cache), "aaaaaaaaaaaa", "the old cache is untouched")
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).iterdir()), ["cache"])
        self.assertFalse((Path(self.tmp.name) / "evil").exists())
    def test_current_needs_a_matching_cache(self):
        with self.assertRaises(ValueError):
            load.write_bundle({"version": "aaaaaaaaaaaa", "current": True}, self.cache)
        load.write_bundle(B1, self.cache)
        with self.assertRaises(ValueError):
            load.write_bundle({"version": "zzzzzzzzzzzz", "current": True}, self.cache)
    def test_file_dir_conflict_keeps_the_cache(self):
        load.write_bundle(B1, self.cache)
        with self.assertRaises(OSError):
            load.write_bundle({"version": "eeeeeeeeeeee", "files": {"a": "x", "a/b": "y"}}, self.cache)
        self.assertEqual(load.cached_version(self.cache), "aaaaaaaaaaaa")
    def test_utf8_and_leftovers(self):
        (Path(self.tmp.name) / "cache.tmp-dead").mkdir()
        load.write_bundle({"version": "ffffffffffff", "files": {"RULES.md": "Grüße \U0001F44D"}}, self.cache)
        self.assertEqual((self.cache / "RULES.md").read_text(encoding="utf-8"), "Grüße \U0001F44D")
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["cache"])
    def test_stdin(self):
        env = {**os.environ, "ADITOR_EDIT_KIT_CACHE": str(self.cache)}
        r = subprocess.run([sys.executable, str(Path(load.__file__)), "write", "-"], input=json.dumps(B1).encode(), env=env, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(load.cached_version(self.cache), "aaaaaaaaaaaa")
    def test_cli(self):
        env = {**os.environ, "ADITOR_EDIT_KIT_CACHE": str(self.cache)}
        run = lambda *a: subprocess.run([sys.executable, str(Path(load.__file__)), *a], env=env, capture_output=True, text=True)
        self.assertEqual(run("version").stdout.strip(), "")
        f = Path(self.tmp.name) / "b.json"
        f.write_text(json.dumps(B1))
        self.assertEqual(run("write", str(f)).returncode, 0)
        self.assertEqual(run("version").stdout.strip(), "aaaaaaaaaaaa")
        f.write_text(json.dumps({"version": "d", "files": {"../x": "y"}}))
        r = run("write", str(f))
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL", r.stderr)

if __name__ == "__main__":
    unittest.main()
