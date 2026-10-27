import unittest
import tempfile
import csv
from pathlib import Path
from dashboard import db
from dashboard import llm_client


class TestRedbubbleWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_stockforge.db"
        db.init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_redbubble_title(self):
        raw_title = "Majestic Alpine Lake Reflection - Living Room Wall Art"
        cleaned = llm_client.clean_redbubble_title(raw_title)
        self.assertEqual(cleaned, "Majestic Alpine Lake Reflection")

        raw_title2 = "Luminous Forest in Autumn for Modern Bedroom Decor"
        cleaned2 = llm_client.clean_redbubble_title(raw_title2)
        self.assertEqual(cleaned2, "Luminous Forest in Autumn")

        # Pure title untouched
        pure_title = "Golden Hour Over High Tatras"
        self.assertEqual(llm_client.clean_redbubble_title(pure_title), pure_title)

    def test_clean_redbubble_description(self):
        ah_desc = (
            "A serene early morning view over the misty pine forest with golden sunlight filtering through the trees.\n\n"
            "Ideal for modern Scandinavian living rooms, bedrooms, or office spaces looking for natural calmness.\n\n"
            "Available in acrylic, canvas, or fine art framed prints. Original fine art photography by Angelus H."
        )
        rb_desc = llm_client.clean_redbubble_description(ah_desc, max_chars=245)
        self.assertTrue(len(rb_desc) <= 245)
        self.assertTrue("serene early morning view" in rb_desc)
        self.assertNotIn("Original fine art photography by Angelus H.", rb_desc)
        self.assertNotIn("Scandinavian living rooms", rb_desc)

    def test_filter_redbubble_tags(self):
        raw_tags = [
            "alpine lake", "forest", "nature", "t-shirt", "best selling", "art", "sticker",
            "sunrise", "morning mist", "scenic", "wilderness", "serene", "tranquil", "landscape", "mountains", "outdoors"
        ]
        filtered = llm_client.filter_redbubble_tags(raw_tags)
        self.assertTrue(10 <= len(filtered) <= 15)
        # Forbidden spam words must be removed
        for forbidden in ["t-shirt", "best selling", "art", "sticker"]:
            self.assertNotIn(forbidden, filtered)
        # Valid tags preserved
        self.assertIn("alpine lake", filtered)
        self.assertIn("morning mist", filtered)

    def test_adapt_art_heroes_to_redbubble(self):
        title = "Retz Calvary Statues in Sunset - Rustic Living Room Decor"
        desc = (
            "Golden sunlight illuminates historic stone statues of Calvary hill against an ominous evening storm sky.\n\n"
            "Perfect for contemporary and rustic spaces looking for architectural elegance.\n\n"
            "Museum quality finishes. Original fine art photography by Angelus H."
        )
        kws = ["retz", "calvary", "austria", "statues", "sunset", "storm sky", "clouds", "heritage", "monument", "historic", "stone", "architecture"]

        adapted = llm_client.adapt_art_heroes_to_redbubble(title, desc, kws, profile="wall_art")
        # Location stripped from title to maximize emotional appeal (4-8 words), preserved in tags/description
        self.assertEqual(adapted["title"], "Calvary Statues in Sunset")
        self.assertTrue(4 <= len(adapted["title"].split()) <= 8)
        self.assertTrue(len(adapted["description"]) <= 245)
        self.assertEqual(adapted["profile"], "wall_art")
        self.assertTrue(len(adapted["tags"]) >= 10)
        self.assertNotIn("t-shirt", adapted["tags"])
        self.assertIn("retz", adapted["tags"])

    def test_db_crud_and_csv_export(self):
        dummy_file = Path(self.temp_dir.name) / "test_photo.jpg"
        dummy_file.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

        img_id = db.insert_image(
            str(dummy_file),
            file_name="test_photo.jpg",
            directory=self.temp_dir.name,
            platform="ArtHeroes",
            status="NEW",
            db_path=self.db_path
        )

        db.update_image(
            img_id,
            title="Alpine Lake - Living Room Decor",
            description="Misty morning story.\n\nRoom styling.\n\nFinishes.",
            keywords="lake, alpine, morning, mist, trees, water, reflection, tranquil, sunrise, serene, nature, austria",
            redbubble_title="Serene Alpine Lake Water Reflection",
            redbubble_description="Misty morning story over tranquil waters bringing calm harmony to your home.",
            redbubble_tags="lake reflection, alpine, morning, mist, trees, water, reflection, tranquil, sunrise, serene, nature, living room decor",
            redbubble_profile="wall_art",
            status="GENERATED",
            db_path=self.db_path
        )

        # Check retrieval
        items = db.get_images(platform="Redbubble", db_path=self.db_path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["redbubble_title"], "Serene Alpine Lake Water Reflection")
        self.assertEqual(items[0]["redbubble_profile"], "wall_art")
        self.assertTrue(len(items[0]["redbubble_description"]) <= 250)

        # Test CSV export
        csv_path = Path(self.temp_dir.name) / "test_redbubble_export.csv"
        db.export_catalog_csv(csv_path, platform="Redbubble", db_path=self.db_path)
        self.assertTrue(csv_path.exists())

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = list(csv.reader(f))
            self.assertEqual(reader[0], ["Filename", "Title", "Description", "Tags", "Profile", "Grade", "Status"])
            self.assertEqual(reader[1][0], "test_photo.jpg")
            self.assertEqual(reader[1][1], "Serene Alpine Lake Water Reflection")
            self.assertEqual(reader[1][4], "wall_art")

    def test_parse_response_json_redbubble(self):
        fake_llm_json = """{
            "title": "Luminous Neon Cyberpunk Rain Alley",
            "description": "Luminous rainy cyber city street with vivid neon reflections and futuristic atmosphere.",
            "tags": ["cyberpunk", "neon", "cityscape", "night", "futuristic", "rain", "reflections", "urban", "street", "tokyo", "scifi", "glow"]
        }"""
        parsed = llm_client.parse_response_json(fake_llm_json, target="Redbubble_Merch")
        self.assertIn("redbubble", parsed)
        rb = parsed["redbubble"]
        self.assertEqual(rb["title"], "Luminous Neon Cyberpunk Rain Alley")
        self.assertEqual(rb["profile"], "merch")
        self.assertTrue(len(rb["description"]) <= 245)
        self.assertEqual(rb["description"], "Luminous rainy cyber city street with vivid neon reflections and futuristic atmosphere.")
        self.assertNotIn("living room", rb["description"].lower())
        self.assertEqual(len(rb["tags"]), 12)

    def test_parse_response_json_redbubble_main_and_supporting_tags(self):
        # Test realistic Red Hat / Linux Engineer prompt response with main_tag & supporting_tags
        # Brand safety must sanitize trademark 'Red Hat' to generic 'open source linux'
        fake_llm_json = """{
            "title": "Rebellious Red Hat Linux Engineer Skull",
            "main_tag": "linux engineer",
            "supporting_tags": ["red hat", "sysadmin", "skull art", "programmer", "devops", "open source", "crossed tools", "mechanic skull", "linux admin", "crimson fedora", "tech humor", "coder gift"],
            "description": "A gritty tribute to the relentless Linux engineer, featuring a defiant skull in a crimson fedora with crossed tools."
        }"""
        parsed = llm_client.parse_response_json(fake_llm_json, target="Redbubble (Merch)")
        self.assertIn("redbubble", parsed)
        rb = parsed["redbubble"]
        # Rule 1 Trademark & Brand Safety verification
        self.assertNotIn("red hat", rb["title"].lower())
        self.assertIn("open source linux", rb["title"].lower())
        self.assertEqual(rb["profile"], "merch")
        # Description must preserve original text without living room decorator boilerplate!
        self.assertEqual(rb["description"], "A gritty tribute to the relentless Linux engineer, featuring a defiant skull in a crimson fedora with crossed tools.")
        self.assertNotIn("living room", rb["description"].lower())
        self.assertNotIn("bedroom", rb["description"].lower())
        # First tag must be the main tag
        self.assertEqual(rb["tags"][0], "linux engineer")
        self.assertIn("linux admin", rb["tags"])
        # Single-word tags like 'sysadmin' are correctly filtered when multi-word phrases exist
        self.assertNotIn("sysadmin", rb["tags"])
        # No landscape / water reflection hallucination!
        self.assertNotIn("serene landscape", rb["tags"])
        self.assertNotIn("water reflection", rb["tags"])

        # Split test for 1-click chip boxes
        main_t, supp_t = llm_client.split_redbubble_tags(rb["tags"])
        self.assertEqual(main_t, "linux engineer,")
        self.assertTrue(supp_t.startswith("open source linux,"))
        self.assertNotIn("living room decor", supp_t)

    def test_redbubble_2026_seo_prompt_and_parsing(self):
        # 1. Verify prompt contains 2026 guidelines
        prompt = llm_client.get_prompt_for_target("Redbubble", "An artistic infrared photo of a church")
        self.assertIn("2026", prompt)
        self.assertIn("TRADEMARK & BRAND SAFETY", prompt)
        self.assertIn("TITLE (40-50 characters max)", prompt)
        self.assertIn("EXACTLY 15 MULTI-WORD PHRASES", prompt)
        self.assertIn("60/40 Split Rule", prompt)
        self.assertIn("DESCRIPTION (60-120 words)", prompt)
        self.assertIn("PRIMARY PRODUCT DETECTION", prompt)

        # 2. Test parsing valid 2026 Redbubble JSON output
        valid_2026_json = """{
            "title": "Ethereal Infrared Calvary Hill Church Fine Art Print",
            "tags": "infrared calvary landscape print, ethereal glowing foliage, surreal hill church, tranquil gothic sanctuary, high contrast monochrome, fine art landscape print, spiritual architectural pilgrimage, sacred pathway monument, surreal dreamlike nature, dramatic monochrome sanctuary, minimalist zen bedroom decor, modern living room art, atmospheric wall decor print, fine art photography collector, peaceful interior sanctuary",
            "description": "Luminous silver foliage glows against an intense dark sky in this ethereal infrared study of a historic hilltop sanctuary. The striking monochromatic contrast and surreal wood effect highlight the timeless stone architecture in breathtaking atmospheric stillness.\\n\\nThis piece brings a meditative, contemplative mood to modern minimalist living rooms, executive home offices, or tranquil master bedrooms seeking refined museum quality fine art elegance.",
            "primary_product": "Wall Art"
        }"""
        parsed = llm_client.parse_response_json(valid_2026_json, target="Redbubble")
        self.assertIn("redbubble", parsed)
        rb = parsed["redbubble"]
        
        # Title check: 40-50 chars target
        self.assertTrue(len(rb["title"]) <= 55)
        self.assertIn("Infrared Calvary", rb["title"])

        # Tags check: Exactly 15 multi-word phrases
        self.assertEqual(len(rb["tags"]), 15)
        for tag in rb["tags"]:
            words = tag.split()
            self.assertTrue(2 <= len(words) <= 5, f"Tag '{tag}' is not 2-5 words")
            self.assertNotIn(tag, ["art", "photo", "funny", "poster", "best selling", "trending"])

        # Description check: 60-120 words preserved across paragraphs
        desc_words = len(rb["description"].split())
        self.assertTrue(60 <= desc_words <= 120, f"Word count {desc_words} not in 60-120")
        self.assertIn("\n\n", rb["description"])

        # Primary product check
        self.assertEqual(rb["primary_product"], "Wall Art")
        self.assertEqual(rb["profile"], "wall_art")

    def test_trademark_brand_safety(self):
        # Trademarks like LinkedIn, Photoshop, Windows, Disney, Red Hat must be sanitized
        raw_text = "Funny LinkedIn tech humor parody of Windows and Photoshop with Disney style"
        sanitized = llm_client.sanitize_redbubble_trademarks(raw_text)
        self.assertNotIn("linkedin", sanitized.lower())
        self.assertNotIn("windows", sanitized.lower())
        self.assertNotIn("photoshop", sanitized.lower())
        self.assertNotIn("disney", sanitized.lower())
        self.assertIn("professional networking site", sanitized.lower())
        self.assertIn("operating system", sanitized.lower())


if __name__ == "__main__":
    unittest.main()
