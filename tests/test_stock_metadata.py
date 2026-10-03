import os
import csv
import unittest
import tempfile
from pathlib import Path
from dashboard.stock_metadata import parse_keywords_list, generate_agency_csv, AGENCY_CSV_FILENAMES
from dashboard.db import init_db, insert_image, export_catalog_csv


class TestStockMetadata(unittest.TestCase):
    def test_parse_keywords_list(self):
        kws = "castle, Castle, fortress, medieval architecture; stone walls, CASTLE"
        parsed = parse_keywords_list(kws, max_count=10)
        self.assertEqual(parsed, ["castle", "fortress", "medieval architecture", "stone walls"])
        self.assertEqual(len(parsed), 4)

    def test_agency_csv_generation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            sample_data = [
                {
                    "file_name": "test_img.jpg",
                    "file_path": str(tmp_path / "test_img.jpg"),
                    "stock_title": "Ancient Fortress Panorama - Medieval Wall Art Decor",
                    "stock_description": "Historic European castle in spring forest.",
                    "stock_keywords": "castle, fortress, europe, wall art",
                    "stock_category": "2",
                    "is_editorial": 0
                }
            ]

            # Adobe Stock
            p_adobe = generate_agency_csv(sample_data, "Adobe Stock", tmp_path)
            self.assertTrue(p_adobe.exists())
            with open(p_adobe, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                row = next(reader)
                self.assertEqual(header, ["Filename", "Title", "Keywords", "Category", "Releases"])
                self.assertEqual(row[0], "test_img.jpg")
                self.assertEqual(row[1], "Ancient Fortress Panorama - Medieval Wall Art Decor")

            # Vecteezy
            p_vect = generate_agency_csv(sample_data, "Vecteezy", tmp_path)
            self.assertTrue(p_vect.exists())
            with open(p_vect, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["Filename", "Title", "Description", "Keywords", "License"])

            # Pond5
            p_pond = generate_agency_csv(sample_data, "Pond5", tmp_path)
            self.assertTrue(p_pond.exists())
            with open(p_pond, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["originalfilename", "title", "description", "keywords", "editorial"])

            # Dreamstime
            p_dream = generate_agency_csv(sample_data, "Dreamstime", tmp_path)
            self.assertTrue(p_dream.exists())
            with open(p_dream, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["Filename", "Image Name", "Description", "Category 1", "Category 2", "Category 3", "keywords", "Editorial"])

            # Depositphotos
            p_dep = generate_agency_csv(sample_data, "Depositphotos", tmp_path)
            self.assertTrue(p_dep.exists())
            with open(p_dep, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["Filename", "Title", "Description", "Keywords", "Categories", "Model Releases", "Property Releases", "Editorial"])

    def test_db_export_catalog_csv_agencies(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            init_db(str(db_path))
            insert_image(
                file_path=str(Path(tmp_dir) / "sample1.jpg"),
                file_name="sample1.jpg",
                directory=tmp_dir,
                stock_title="Sample Stock Title",
                stock_description="Sample Stock Desc",
                stock_keywords="kw1, kw2",
                db_path=str(db_path)
            )

            csv_out = Path(tmp_dir) / "export_depositphotos.csv"
            saved = export_catalog_csv(csv_out, platform="Depositphotos", db_path=str(db_path))
            self.assertTrue(Path(saved).exists())
            with open(saved, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["Filename", "Title", "Description", "Keywords", "Categories", "Model Releases", "Property Releases", "Editorial"])
                row = next(reader)
                self.assertEqual(row[0], "sample1.jpg")
                self.assertEqual(row[1], "Sample Stock Title")

            # Alamy export test
            csv_alamy = Path(tmp_dir) / "export_alamy.csv"
            saved_alamy = export_catalog_csv(csv_alamy, platform="Alamy", db_path=str(db_path))
            self.assertTrue(Path(saved_alamy).exists())
            with open(saved_alamy, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["Filename", "Title", "Description", "Keywords", "Editorial"])
                row = next(reader)
                self.assertEqual(row[0], "sample1.jpg")
                self.assertEqual(row[1], "Sample Stock Title")


if __name__ == "__main__":
    unittest.main()
