"""Smoke test for the parser using a synthetic HTML fixture.

Run with: python -m unittest tests.test_parser
"""
import unittest

from ura_scraper.parser import (
    filter_apartments_and_condos_resale,
    parse_results_table,
)


SAMPLE_HTML = """
<html><body>
<table class="tbl">
  <tr>
    <th>S/N</th><th>Project Name</th><th>Street Name</th>
    <th>Type</th><th>Postal District</th><th>Market Segment</th>
    <th>Tenure</th><th>Type of Sale</th><th>No. of Units</th>
    <th>Price ($)</th><th>Area (Sqft)</th><th>Type of Area</th>
    <th>Floor Level</th><th>Unit Price ($psf)</th><th>Date of Sale</th>
  </tr>
  <tr>
    <td>1</td><td>THE SAIL @ MARINA BAY</td><td>MARINA BOULEVARD</td>
    <td>Condominium</td><td>01</td><td>CCR</td>
    <td>99 yrs lease commencing from 2002</td><td>Resale</td><td>1</td>
    <td>2,450,000</td><td>915</td><td>Strata</td>
    <td>26-30</td><td>2,678</td><td>Mar-25</td>
  </tr>
  <tr>
    <td>2</td><td>SOME NEW LAUNCH</td><td>FAKE ROAD</td>
    <td>Condominium</td><td>09</td><td>CCR</td>
    <td>Freehold</td><td>New Sale</td><td>1</td>
    <td>3,000,000</td><td>800</td><td>Strata</td>
    <td>11-15</td><td>3,750</td><td>Apr-25</td>
  </tr>
  <tr>
    <td>3</td><td>SUBURBAN APT</td><td>TAMPINES STREET 12</td>
    <td>Apartment</td><td>18</td><td>OCR</td>
    <td>99 yrs lease commencing from 2015</td><td>Resale</td><td>1</td>
    <td>1,200,000</td><td>700</td><td>Strata</td>
    <td>06-10</td><td>1,714</td><td>Feb-25</td>
  </tr>
  <tr>
    <td>4</td><td>LANDED HOUSE</td><td>SOMEWHERE LANE</td>
    <td>Terrace</td><td>15</td><td>RCR</td>
    <td>Freehold</td><td>Resale</td><td>1</td>
    <td>4,500,000</td><td>2,500</td><td>Land</td>
    <td>-</td><td>1,800</td><td>Jan-25</td>
  </tr>
</table>
</body></html>
"""


class ParserTests(unittest.TestCase):
    def test_parse_all_rows(self):
        rows = parse_results_table(SAMPLE_HTML)
        self.assertEqual(len(rows), 4)
        sail = rows[0]
        self.assertEqual(sail.project, "THE SAIL @ MARINA BAY")
        self.assertEqual(sail.property_type, "Condominium")
        self.assertEqual(sail.type_of_sale, "Resale")
        self.assertEqual(sail.price_sgd, 2_450_000)
        self.assertEqual(sail.area_sqft, 915.0)
        self.assertAlmostEqual(sail.area_sqm, 85.01, places=1)
        self.assertEqual(sail.unit_price_psf, 2678)
        self.assertEqual(sail.district, "01")
        self.assertEqual(sail.market_segment, "CCR")

    def test_filter_drops_new_sale_and_landed(self):
        rows = parse_results_table(SAMPLE_HTML)
        filtered = filter_apartments_and_condos_resale(rows)
        projects = sorted(t.project for t in filtered)
        self.assertEqual(projects, ["SUBURBAN APT", "THE SAIL @ MARINA BAY"])
        for t in filtered:
            self.assertEqual(t.type_of_sale, "Resale")
            self.assertIn(t.property_type, ("Apartment", "Condominium"))


if __name__ == "__main__":
    unittest.main()
