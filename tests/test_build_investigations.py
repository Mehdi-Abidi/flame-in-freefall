import unittest

from pipeline.build_investigations import compute_ranges, platform_from_flight_platform, range_with_basis


def row(record_type="test", o2="", o2_source="", pressure="", pressure_source="", phase="gas"):
    return {"record_type": record_type, "o2_mole_fraction": o2, "o2_source": o2_source,
            "pressure_kpa": pressure, "pressure_source": pressure_source, "fuel_phase": phase}


class PlatformTests(unittest.TestCase):
    def test_space_station_long_name(self):
        self.assertEqual(platform_from_flight_platform("International Space Station (ISS)"), "ISS")

    def test_cygnus(self):
        self.assertEqual(platform_from_flight_platform("Cygnus Spacecraft"), "Cygnus")

    def test_ground_study_wins_over_blank_or_not_applicable(self):
        self.assertEqual(platform_from_flight_platform("", "Ground Investigation"), "ground")
        self.assertEqual(platform_from_flight_platform("Not Applicable", "Ground Investigation"), "ground")

    def test_unknown_flight_platform_kept_as_written(self):
        self.assertEqual(platform_from_flight_platform("Parabolic aircraft", "Reduced Gravity Investigation"), "Parabolic aircraft")

    def test_missing_platform_is_none(self):
        self.assertIsNone(platform_from_flight_platform("Not Applicable", "Microgravity Investigation"))


class RangeTests(unittest.TestCase):
    def test_measured_values_win_over_nominal(self):
        rows = [row(o2="0.21", o2_source="nominal_cabin_air"), row(o2="0.15", o2_source="measured"), row(o2="0.30", o2_source="measured")]
        self.assertEqual(range_with_basis(rows, "o2_mole_fraction", "o2_source", ("measured", "nominal_cabin_air"), 3),
                         ([0.15, 0.3], "measured"))

    def test_nominal_only_is_labelled_nominal(self):
        rows = [row(o2="0.21", o2_source="nominal_cabin_air")]
        self.assertEqual(range_with_basis(rows, "o2_mole_fraction", "o2_source", ("measured", "nominal_cabin_air"), 3),
                         ([0.21, 0.21], "nominal_cabin_air"))

    def test_no_values_gives_empty_range_and_basis(self):
        self.assertEqual(range_with_basis([row()], "o2_mole_fraction", "o2_source", ("measured",), 3), (None, None))


class ComputeRangesTests(unittest.TestCase):
    def test_planned_matrix_is_not_counted_as_tests(self):
        rows = [row("condition_matrix", "0.17", "planned", "50.7", "planned", "liquid") for _ in range(4)]
        result = compute_ranges(rows)
        self.assertEqual((result["n_tests"], result["n_records"]), (0, 4))
        self.assertEqual((result["o2_basis"], result["pressure_basis"]), ("planned", "planned"))

    def test_counts_mixed_record_types(self):
        rows = [row("test"), row("test"), row("test_day"), row("session", phase="dust")]
        result = compute_ranges(rows)
        self.assertEqual((result["n_tests"], result["n_records"]), (2, 4))
        self.assertEqual(result["fuel_phase"], ["dust", "gas"])

    def test_empty_investigation(self):
        result = compute_ranges([])
        self.assertEqual((result["n_tests"], result["n_records"], result["o2_range"], result["o2_basis"]), (0, 0, None, None))


if __name__ == "__main__":
    unittest.main()
