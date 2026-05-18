"""Test the URA API response parser with a synthetic payload.

Shape modeled on the documented PMI_Resi_Transaction response: a top-level
{Status, Message, Result} envelope where Result is a list of project rows,
each carrying its own transactions[] array.
"""
import unittest

from ura_scraper.api_client import _iter_transactions
from ura_scraper.parser import filter_apartments_and_condos_resale


SAMPLE_PAYLOAD = {
    "Status": "Success",
    "Message": "success",
    "Result": [
        {
            "project": "THE SAIL @ MARINA BAY",
            "street": "MARINA BOULEVARD",
            "marketSegment": "CCR",
            "x": "30311.123",
            "y": "29110.456",
            "transaction": [
                {
                    "contractDate": "0325",
                    "price": "2450000",
                    "area": "85.01",
                    "typeOfArea": "Strata",
                    "propertyType": "Condominium",
                    "district": "01",
                    "tenure": "99 yrs lease commencing from 2002",
                    "floorRange": "26-30",
                    "typeOfSale": "3",
                    "noOfUnits": "1",
                },
                {
                    "contractDate": "0425",
                    "price": "3000000",
                    "area": "74.32",
                    "typeOfArea": "Strata",
                    "propertyType": "Condominium",
                    "district": "01",
                    "tenure": "99 yrs lease commencing from 2002",
                    "floorRange": "11-15",
                    "typeOfSale": "1",  # New Sale — should be filtered out
                    "noOfUnits": "1",
                },
            ],
        },
        {
            "project": "LANDED HOUSE",
            "street": "SOMEWHERE LANE",
            "marketSegment": "RCR",
            "transaction": [
                {
                    "contractDate": "0125",
                    "price": "4500000",
                    "area": "232.26",
                    "typeOfArea": "Land",
                    "propertyType": "Terrace",  # Landed — should be filtered out
                    "district": "15",
                    "tenure": "Freehold",
                    "floorRange": "-",
                    "typeOfSale": "3",
                    "noOfUnits": "1",
                }
            ],
        },
    ],
}


class APIClientTests(unittest.TestCase):
    def test_iter_transactions_decodes_codes_and_shape(self):
        rows = list(_iter_transactions(SAMPLE_PAYLOAD))
        self.assertEqual(len(rows), 3)

        sail = rows[0]
        self.assertEqual(sail.project, "THE SAIL @ MARINA BAY")
        self.assertEqual(sail.market_segment, "CCR")
        self.assertEqual(sail.type_of_sale, "Resale")
        self.assertEqual(sail.price_sgd, 2_450_000)
        self.assertAlmostEqual(sail.area_sqm, 85.01, places=2)
        self.assertAlmostEqual(sail.area_sqft, 915.0, delta=2.0)
        self.assertEqual(sail.district, "01")
        self.assertEqual(sail.property_type, "Condominium")

        self.assertEqual(rows[1].type_of_sale, "New Sale")
        self.assertEqual(rows[2].property_type, "Terrace")

    def test_filter_keeps_only_resale_apartments_and_condos(self):
        rows = list(_iter_transactions(SAMPLE_PAYLOAD))
        filtered = filter_apartments_and_condos_resale(rows)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].project, "THE SAIL @ MARINA BAY")


if __name__ == "__main__":
    unittest.main()
