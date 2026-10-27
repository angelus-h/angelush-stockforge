import os
import csv
import unittest
import tempfile
from pathlib import Path
from PIL import Image
from dashboard.stock_metadata import (
    parse_keywords_list,
    generate_agency_csv,
    AGENCY_CSV_FILENAMES,
    apply_stock_metadata_to_image,
    find_exiftool,
    _escape_cstr,
    SHUTTERSTOCK_CATEGORIES,
    map_to_shutterstock_categories
)
from pod_workflow.ArtHeroes.apply_art_heroes_metadata import apply_metadata_to_image
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

            # Vecteezy (strictly 4 columns, clean UTF-8 without BOM)
            p_vect = generate_agency_csv(sample_data, "Vecteezy", tmp_path)
            self.assertTrue(p_vect.exists())
            with open(p_vect, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["Filename", "Title", "Description", "Keywords"])

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

            # Shutterstock (strictly 2 categories from the official 26 category list)
            p_shutter = generate_agency_csv(sample_data, "Shutterstock", tmp_path)
            self.assertTrue(p_shutter.exists())
            with open(p_shutter, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                row = next(reader)
                self.assertEqual(header, ["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"])
                self.assertEqual(row[0], "test_img.jpg")
                cats = [c.strip() for c in row[3].split(",") if c.strip()]
                self.assertEqual(len(cats), 2, "Shutterstock must have exactly 2 categories")
                for c in cats:
                    self.assertIn(c, SHUTTERSTOCK_CATEGORIES)
                self.assertNotIn("2", cats)
                self.assertNotIn("Travel", cats)

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

            # Shutterstock export test
            csv_shutter = Path(tmp_dir) / "export_shutterstock.csv"
            saved_shutter = export_catalog_csv(csv_shutter, platform="Shutterstock", db_path=str(db_path))
            self.assertTrue(Path(saved_shutter).exists())
            with open(saved_shutter, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self.assertEqual(header, ["Filename", "Description", "Keywords", "Categories", "Editorial", "Mature content", "illustration"])
                row = next(reader)
                self.assertEqual(row[0], "sample1.jpg")
                cats = [c.strip() for c in row[3].split(",") if c.strip()]
                self.assertEqual(len(cats), 2)
                for c in cats:
                    self.assertIn(c, SHUTTERSTOCK_CATEGORIES)

    def test_map_to_shutterstock_categories(self):
        # 1. Official 26 categories list verification
        self.assertEqual(len(SHUTTERSTOCK_CATEGORIES), 26)

        # 2. Numeric Adobe ID '2' (Buildings and Architecture)
        cat_str = map_to_shutterstock_categories("2", title="Castle", description="Ancient stone fortress", keywords="castle")
        cats = [c.strip() for c in cat_str.split(",") if c.strip()]
        self.assertEqual(len(cats), 2)
        self.assertEqual(cats[0], "Buildings/Landmarks")
        for c in cats:
            self.assertIn(c, SHUTTERSTOCK_CATEGORIES)

        # 3. Old invalid default 'Buildings/Landmarks, Travel'
        cat_str = map_to_shutterstock_categories("Buildings/Landmarks, Travel")
        cats = [c.strip() for c in cat_str.split(",") if c.strip()]
        self.assertEqual(len(cats), 2)
        self.assertEqual(cats[0], "Buildings/Landmarks")
        self.assertNotIn("Travel", cats)
        for c in cats:
            self.assertIn(c, SHUTTERSTOCK_CATEGORIES)

        # 4. Contextual triggers: Church in rural landscape
        cat_str = map_to_shutterstock_categories(
            None,
            title="Baroque church tower in South Moravia Czechia",
            description="A baroque church tower peeks over a rolling agricultural field of ripening rapeseed with wild poppies under a blue summer sky with clouds in South Moravia, Czech Republic.",
            keywords="south moravia, czech republic, czechia, moravia, kyjov, church tower, spire, baroque, chapel, church"
        )
        cats = [c.strip() for c in cat_str.split(",") if c.strip()]
        self.assertEqual(len(cats), 2)
        self.assertEqual(cats[0], "Buildings/Landmarks")
        self.assertEqual(cats[1], "Religion")
        for c in cats:
            self.assertIn(c, SHUTTERSTOCK_CATEGORIES)

        # 5. Explicit 2 valid categories
        cat_str = map_to_shutterstock_categories("Food and drink, Objects")
        self.assertEqual(cat_str, "Food and drink, Objects")

        # 6. Completely empty inputs
        cat_str = map_to_shutterstock_categories(None)
        cats = [c.strip() for c in cat_str.split(",") if c.strip()]
        self.assertEqual(len(cats), 2)
        for c in cats:
            self.assertIn(c, SHUTTERSTOCK_CATEGORIES)

    def test_escape_cstr(self):
        raw = "Line 1\r\nLine 2\nLine 3\rPath\\File"
        escaped = _escape_cstr(raw)
        self.assertEqual(escaped, "Line 1\\nLine 2\\nLine 3\\nPath\\\\File")

    def test_multiline_art_heroes_metadata_embed(self):
        try:
            exe = find_exiftool()
        except FileNotFoundError:
            self.skipTest("ExifTool not installed")

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_img = Path(tmp_dir) / "IMGP5288.jpg"
            Image.new("RGB", (100, 100), color="green").save(test_img)

            meta = {
                "title": "Majestic Lednice Castle - Elegant Hall Wall Art",
                "description": (
                    "This scenic architectural landscape serves as a captivating focal point in contemporary living rooms.\n\n"
                    "Its lush emerald tones complement Scandinavian and European interior styles.\n\n"
                    "Crafted with meticulous attention to detail. Original fine art photography by Angelus H."
                ),
                "keywords": ["castle", "architecture", "czech republic", "green", "fine art"]
            }

            # Should complete without throwing "Error: File not found - This scenic..."
            apply_metadata_to_image(exe, test_img, meta)
            self.assertTrue(test_img.exists())

    def test_multiline_stock_metadata_embed(self):
        try:
            exe = find_exiftool()
        except FileNotFoundError:
            self.skipTest("ExifTool not installed")

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_img = Path(tmp_dir) / "stock_test.jpg"
            Image.new("RGB", (100, 100), color="blue").save(test_img)

            desc = "Paragraph 1 of description.\n\nParagraph 2 of description.\n\nParagraph 3 of description."
            apply_stock_metadata_to_image(
                image_path=test_img,
                title="Scenic Alpine Lake",
                description=desc,
                keywords=["lake", "mountain", "nature"],
                exiftool_path=exe
            )
            self.assertTrue(test_img.exists())


if __name__ == "__main__":
    unittest.main()
