"""python3 -m unittest test_edit_kit  (run inside plugins/edit-kit)"""
import sys, unittest
from pathlib import Path
sys.path[:0] = [str(Path(__file__).parent / "skills/rough-cut"), str(Path(__file__).parent / "skills/broll")]
import rc, br

W = [{"i": 0, "w": "It's", "t": 0.0, "d": 0.2}, {"i": 1, "w": "it's", "t": 0.3, "d": 0.2},
     {"i": 2, "w": "great.", "t": 0.6, "d": 0.3}, {"i": 3, "w": "Buy", "t": 1.2, "d": 0.2},
     {"i": 4, "w": "now.", "t": 1.5, "d": 0.3}]

class T(unittest.TestCase):
    def test_parse_glues_punctuation(self):
        segs = [{"text": " Hi", "offsets": {"from": 0, "to": 200}}, {"text": ".", "offsets": {"from": 200, "to": 210}},
                {"text": " ", "offsets": {"from": 210, "to": 220}}, {"text": " Yo", "offsets": {"from": 300, "to": 500}}]
        self.assertEqual([w["w"] for w in rc.parse_whisper(segs)], ["Hi.", "Yo"])
    def test_sentences(self):
        self.assertEqual([len(s) for s in rc.sentences(W)], [3, 2])
    def test_repeats(self):
        self.assertEqual(rc.repeats(W), ["[0-1] It's it's"])
    def test_drop_spans_runs_to_next_word(self):
        self.assertEqual(rc.drop_spans(W, "0, 3-4"), [(0.0, 0.3), (1.2, 1.8)])
        with self.assertRaises(SystemExit): rc.drop_spans(W, "4-9")
    def test_plan(self):
        inv = {"01": {"path": "a", "dur": 2.0}, "02": {"path": "b", "dur": 0.4}}
        p = br.plan([{"clip": "01", "from": 3, "to": 4}], W, inv, 2.0)
        self.assertAlmostEqual(p[0]["at"], 1.2); self.assertAlmostEqual(p[0]["dur"], 0.6)
        with self.assertRaises(SystemExit): br.plan([{"clip": "02", "from": 3, "to": 4}], W, inv, 2.0)  # too short
        with self.assertRaises(SystemExit):
            br.plan([{"clip": "01", "from": 0, "to": 2}, {"clip": "01", "from": 2, "to": 3}], W, inv, 2.0)  # overlap

class Keeps(unittest.TestCase):
    def test_pauses_shrink_and_drops_go(self):
        cfg = rc.PACES["ad"]
        k = rc.plan_keeps(W, [(0.9, 1.2), (0.2, 0.25)], 2.0, 30, cfg, [(0.0, 0.3)])
        self.assertAlmostEqual(k[0][0], 0.3, places=2)           # dropped take gone
        cut = sum(b - a for a, b in k)
        self.assertLess(cut, 2.0 - 0.3 - 0.1)                    # long pause shrank, short one kept

if __name__ == "__main__":
    unittest.main()
