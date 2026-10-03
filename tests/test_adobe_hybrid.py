"""
Unit tests for Adobe Stock & Posters.cz Hybrid metadata generation and database support.
"""

import os
import unittest
import tempfile
import sqlite3
import csv
from pathlib import Path

from dashboard.llm_client import (
    is_hybrid_requested,
    get_prompt_for_target,
    parse_response_json
)
from dashboard import db


class TestAdobeHybridLLM(unittest.TestCase):
    def test_is_hybrid_requested_explicit_flag(self):
        self.assertTrue(is_hybrid_requested("", flag_value=True))
        self.assertFalse(is_hybrid_requested("", flag_value=False))

    def test_is_hybrid_requested_context_detection(self):
        # Triggers in Hungarian and English
        self.assertTrue(is_hybrid_requested("Kérem készítsünk Adobe hybrid leírást"))
        self.assertTrue(is_hybrid_requested("Ez a kép szinkronizálva lesz https://www.posters.cz/ oldalra"))
        self.assertTrue(is_hybrid_requested("Lakberendező és poszter fókuszú leírás"))
        self.assertTrue(is_hybrid_requested("Belsőépítészeti fali poszter stílus"))
        self.assertTrue(is_hybrid_requested("Interior design wall art hybrid"))
        self.assertTrue(is_hybrid_requested("Posters.cz compatible tags"))

        # Non-hybrid normal context
        self.assertFalse(is_hybrid_requested("Lednice castle in autumn with blue sky"))
        self.assertFalse(is_hybrid_requested("Retz calvary hill statues, sunny day"))

    def test_get_prompt_for_target_hybrid_stock(self):
        prompt_normal = get_prompt_for_target(
            target="Stock",
            description="Baroque statues on a hill",
            is_adobe_hybrid=False
        )
        self.assertIn("Microstock Photography metadata optimizer", prompt_normal)
        self.assertNotIn("posters.cz", prompt_normal)

        prompt_hybrid = get_prompt_for_target(
            target="Stock",
            description="Baroque statues on a hill",
            is_adobe_hybrid=True
        )
        self.assertIn("posters.cz", prompt_hybrid)
        self.assertIn("MANDATORY HYBRID FORMULA", prompt_hybrid)
        self.assertIn("MANDATORY DUAL-LAYER KEYWORDS", prompt_hybrid)
        self.assertIn("Interior Design, Wall Art & Posters.cz Search Terms", prompt_hybrid)

    def test_get_prompt_for_target_hybrid_all_platforms(self):
        prompt_all_hybrid = get_prompt_for_target(
            target="All",
            description="Vintage locomotive at terminal station",
            is_adobe_hybrid=True
        )
        self.assertIn("posters.cz", prompt_all_hybrid)
        self.assertIn("ADOBE STOCK & POSTERS.CZ HYBRID RULES", prompt_all_hybrid)
        self.assertIn("ART HEROES RULES", prompt_all_hybrid)
        self.assertIn("DISPLATE RULES", prompt_all_hybrid)

    def test_parse_response_json_stock(self):
        sample_json = '''{
            "stock": {
                "title": "Historic Retz Calvary Hill Statues in Austria - Rustic Fine Art Wall Decor",
                "description": "Evocative view of Baroque statues on Calvary hill in Retz, Lower Austria. Ideal as fine art wall decor.",
                "keywords": ["retz", "austria", "calvary hill", "wall art", "interior design", "poster"],
                "category": "Travel"
            }
        }'''
        res = parse_response_json(sample_json, target="Stock")
        self.assertIn("stock", res)
        stk = res["stock"]
        self.assertEqual(stk["title"], "Historic Retz Calvary Hill Statues in Austria - Rustic Fine Art Wall Decor")
        self.assertIn("wall art", stk["keywords"])


class TestAdobeHybridDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_stockforge.db"
        db.init_db(str(self.db_path), force=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_db_migration_and_crud(self):
        # Create a test image
        img_id = db.insert_image(
            file_path=r"C:\test\sample_hybrid.jpg",
            file_name="sample_hybrid.jpg",
            directory=r"C:\test",
            db_path=str(self.db_path)
        )
        self.assertIsNotNone(img_id)

        # Update with is_adobe_hybrid
        db.update_image(
            img_id,
            stock_title="Historic Calvary Hill - Fine Art Wall Decor",
            stock_keywords="retz, austria, wall art, interior design",
            is_adobe_hybrid=1,
            db_path=str(self.db_path)
        )

        img = db.get_image_by_id(img_id, db_path=str(self.db_path))
        self.assertEqual(img["is_adobe_hybrid"], 1)
        self.assertEqual(img["stock_title"], "Historic Calvary Hill - Fine Art Wall Decor")

    def test_export_adobe_stock_csv(self):
        img_id = db.insert_image(
            file_path=r"C:\test\adobe_sample.jpg",
            file_name="adobe_sample.jpg",
            directory=r"C:\test",
            db_path=str(self.db_path)
        )
        db.update_image(
            img_id,
            stock_title="Retz Windmill in Autumn",
            stock_description="Historic windmill on a green hill in Retz Austria",
            stock_keywords="retz, austria, windmill",
            adobe_title="Retz Windmill in Autumn - Rustic Wall Art Poster",
            adobe_description="Historic windmill in Retz Austria, ideal for modern rustic living rooms.",
            adobe_keywords="retz, windmill, wall art, posters cz",
            stock_category="Travel",
            is_adobe_hybrid=1,
            db_path=str(self.db_path)
        )

        csv_file = Path(self.temp_dir.name) / "stockforge_adobe_stock_export.csv"
        saved = db.export_catalog_csv(str(csv_file), platform="Adobe Stock", db_path=str(self.db_path))
        self.assertTrue(Path(saved).exists())

        with open(saved, mode="r", encoding="utf-8-sig") as f:
            reader = list(csv.reader(f))
            self.assertEqual(reader[0], ["Filename", "Title", "Keywords", "Category", "Releases"])
            self.assertEqual(reader[1][0], "adobe_sample.jpg")
            self.assertEqual(reader[1][1], "Retz Windmill in Autumn - Rustic Wall Art Poster")
            self.assertEqual(reader[1][3], "Travel")

    def test_agency_isolation_hybrid_vs_pure_stock(self):
        from dashboard.stock_metadata import get_image_stock_fields, generate_agency_csv

        img = {
            "id": 101,
            "file_name": "retz_mill.jpg",
            "file_path": r"C:\photos\retz_mill.jpg",
            "is_adobe_hybrid": 1,
            "stock_title": "Historic Retz windmill in Austria",
            "stock_description": "Windmill on the green hill under clear blue sky in Retz, Lower Austria.",
            "stock_keywords": "retz, austria, windmill, daylight, sunny, architecture",
            "stock_category": "Buildings and Architecture",
            "adobe_title": "Historic Retz Windmill in Austria - Rustic Fine Art Wall Decor",
            "adobe_description": "Historic windmill in Retz, ideal as wall art poster for contemporary living rooms.",
            "adobe_keywords": "retz, austria, windmill, wall art, posters cz, interior design, home decor",
            "adobe_category": "Buildings and Architecture"
        }

        # 1. Adobe Stock MUST receive the Hybrid metadata
        adobe_data = get_image_stock_fields(img, agency_name="Adobe Stock")
        self.assertEqual(adobe_data["title"], "Historic Retz Windmill in Austria - Rustic Fine Art Wall Decor")
        self.assertIn("wall art", adobe_data["keywords"])
        self.assertIn("posters cz", adobe_data["keywords"])

        # 2. Vecteezy MUST receive pure Microstock metadata
        vecteezy_data = get_image_stock_fields(img, agency_name="Vecteezy")
        self.assertEqual(vecteezy_data["title"], "Historic Retz windmill in Austria")
        self.assertEqual(vecteezy_data["description"], "Windmill on the green hill under clear blue sky in Retz, Lower Austria.")
        self.assertNotIn("wall art", vecteezy_data["keywords"])
        self.assertNotIn("posters cz", vecteezy_data["keywords"])

        # 3. Alamy MUST receive pure Microstock metadata
        alamy_data = get_image_stock_fields(img, agency_name="Alamy")
        self.assertEqual(alamy_data["title"], "Historic Retz windmill in Austria")
        self.assertEqual(alamy_data["description"], "Windmill on the green hill under clear blue sky in Retz, Lower Austria.")
        self.assertNotIn("wall art", alamy_data["keywords"])

        # 4. Shutterstock CSV generation MUST contain pure Microstock metadata
        shutter_csv = generate_agency_csv([img], agency_name="Shutterstock", output_dir=Path(self.temp_dir.name))
        with open(shutter_csv, "r", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
            # Header: Filename, Description, Keywords...
            self.assertEqual(rows[1][1], "Windmill on the green hill under clear blue sky in Retz, Lower Austria.")
            self.assertNotIn("wall art", rows[1][2])


if __name__ == "__main__":
    unittest.main()
