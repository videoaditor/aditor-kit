import json, os, tempfile, unittest
import push


class PlanParts(unittest.TestCase):
    def test_exact_and_remainder(self):
        self.assertEqual(push.plan_parts(10, 5), [(1, 0, 5), (2, 5, 5)])
        self.assertEqual(push.plan_parts(11, 5), [(1, 0, 5), (2, 5, 5), (3, 10, 1)])

    def test_small_and_empty(self):
        self.assertEqual(push.plan_parts(3, 5), [(1, 0, 3)])
        self.assertEqual(push.plan_parts(0, 5), [])

    def test_default_is_10mb(self):
        self.assertEqual(push.plan_parts(push.PART + 1)[0][2], 10 * 1024 * 1024)


class MergeState(unittest.TestCase):
    fp = {"file": "/a.mp4", "size": 5, "mtime": 1, "request": "t", "asset": None}

    def test_same_fingerprint_resumes(self):
        saved = {"fp": self.fp, "upload_id": "U", "s3_key": "k", "parts": {1: "e1"}}
        st = push.merge_state(saved, self.fp)
        self.assertEqual(st["upload_id"], "U")
        self.assertEqual(st["parts"], {"1": "e1"})

    def test_changed_file_or_asset_starts_fresh(self):
        saved = {"fp": self.fp, "upload_id": "U", "parts": {"1": "e1"}}
        for change in ({"size": 6}, {"mtime": 2}, {"asset": "A"}, {"request": "other"}):
            st = push.merge_state(saved, {**self.fp, **change})
            self.assertEqual(st, {"fp": {**self.fp, **change}, "parts": {}})

    def test_garbage_state_starts_fresh(self):
        for bad in (None, [], {"fp": self.fp}):
            self.assertEqual(push.merge_state(bad, self.fp)["parts"], {})

    def test_fingerprint_reads_the_file(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as t:
            t.write(b"abc"); t.flush()
            fp = push.fingerprint(t.name, "tok", "A")
            self.assertEqual((fp["size"], fp["request"], fp["asset"]), (3, "tok", "A"))


if __name__ == "__main__":
    unittest.main()


class StoreKey(unittest.TestCase):
    def test_key_goes_through_stdin_never_argv(self):
        import ar
        from unittest import mock
        with mock.patch.object(ar.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            ar.store_key("ara_secret")
        argv, kw = run.call_args
        self.assertEqual(argv[0], ["security", "-i"])
        self.assertIn('-w "ara_secret"', kw["input"])
        self.assertIn("-s aditor-autoreview-agent", kw["input"])
