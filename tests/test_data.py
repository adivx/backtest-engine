import csv
import tempfile
import unittest

from backtest.data import Bar, DataError, generate_synthetic, load_csv


class TestSynthetic(unittest.TestCase):
    def test_bar_count(self):
        self.assertEqual(len(generate_synthetic(years=5)), 5 * 252)
        self.assertEqual(len(generate_synthetic(years=0.5)), 126)

    def test_seeded_reproducibility(self):
        a = generate_synthetic(seed=42)
        b = generate_synthetic(seed=42)
        self.assertEqual([x.close for x in a], [x.close for x in b])

    def test_ohlc_invariants(self):
        for bar in generate_synthetic(seed=7):
            self.assertGreaterEqual(bar.high, max(bar.open, bar.close))
            self.assertLessEqual(bar.low, min(bar.open, bar.close))
            self.assertGreater(bar.close, 0)

    def test_invalid_inputs(self):
        with self.assertRaises(DataError):
            generate_synthetic(start_price=0)
        with self.assertRaises(DataError):
            generate_synthetic(years=-1)
        with self.assertRaises(DataError):
            generate_synthetic(volatility=-0.1)


class TestCSV(unittest.TestCase):
    def _write(self, rows, header=("date", "open", "high", "low", "close", "volume")):
        path = tempfile.mktemp(suffix=".csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        return path

    def test_roundtrip(self):
        bars = generate_synthetic(seed=1, years=1)[:20]
        path = self._write(
            [(b.date, b.open, b.high, b.low, b.close, b.volume) for b in bars]
        )
        self.assertEqual(load_csv(path), bars)

    def test_column_order_independent(self):
        path = self._write(
            [(b.close, b.date, b.volume, b.low, b.open, b.high) for b in [Bar("2026-01-05", 1, 3, 0.5, 2, 100)]],
            header=("close", "date", "volume", "low", "open", "high"),
        )
        self.assertEqual(load_csv(path), [Bar("2026-01-05", 1, 3, 0.5, 2, 100)])

    def test_missing_column_raises(self):
        path = self._write([("2026-01-05", 1, 3, 2, 100)], header=("date", "open", "high", "close", "volume"))
        with self.assertRaises(DataError):
            load_csv(path)

    def test_bad_number_raises(self):
        path = self._write([("2026-01-05", "x", 3, 2, 1, 100)])
        with self.assertRaises(DataError):
            load_csv(path)

    def test_missing_file_raises(self):
        with self.assertRaises(DataError):
            load_csv("/nonexistent/definitely-not-here.csv")


if __name__ == "__main__":
    unittest.main()
