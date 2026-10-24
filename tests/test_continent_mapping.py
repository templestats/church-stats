"""Regression tests for the static country-to-continent classification."""
import unittest

import pycountry

import temple_attendance_datawrapper3 as stats


class ContinentMappingTests(unittest.TestCase):
    def test_every_iso_country_has_a_continent(self):
        missing = [
            (country.alpha_3, country.name)
            for country in pycountry.countries
            if country.alpha_3 not in stats.CONTINENT_BY_ISO3
            and country.alpha_3 not in stats.CONTINENT_OVERRIDES_BY_ISO3
        ]
        self.assertEqual([], missing, f"Unmapped ISO-3 countries: {missing}")

    def test_known_country_classifications(self):
        expected = {
            "Argentina": "South America",
            "United States": "North America",
            "United Kingdom": "Europe",
            "South Africa": "Africa",
            "Japan": "Asia",
            "Australia": "Oceania",
            "Hong Kong": "Asia",
            "French Polynesia": "Oceania",
            "Russia": "Europe",
        }
        for country, continent in expected.items():
            with self.subTest(country=country):
                self.assertEqual(continent, stats.continent_for_country(country))

    def test_unknown_country_fails_with_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "no ISO-3 code was resolved"):
            stats.continent_for_country("Definitely Not a Country")


if __name__ == "__main__":
    unittest.main()
