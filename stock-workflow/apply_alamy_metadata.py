#!/usr/bin/env python3
"""
apply_alamy_metadata.py
Embeds IPTC (IIM) and EXIF metadata into the contributor images for Alamy.
Updates both the working upload batch in G:\\upload_temp and the source archive in F:\\Képek.
Also outputs an alamy_metadata.csv for contributor batch management.
"""

import os
import sys
import csv
import json
import logging
import piexif
import iptcinfo3
from PIL import Image, IptcImagePlugin

logging.getLogger("iptcinfo").setLevel(logging.ERROR)

# Source folder mapping for original archival images
SOURCE_DIRS = {
    "IMGP0358.jpg": r"F:\Képek\Hrad Veveri\final",
    "IMGP1291.jpg": r"F:\Képek\Hrad Veveri\final",
    "IMGP5248.jpg": r"F:\Képek\Lednice\final",
    "IMGP5226.jpg": r"F:\Képek\Lednice\final",
    "IMGP4151.jpg": r"F:\Képek\Lednice\final",
    "IMGP4231.jpg": r"F:\Képek\Lednice\final",
    "IMGP2401.jpg": r"F:\Képek\Lednice\final",
    "_IMG7819.jpg": r"F:\Képek\Dolni Kounice\final",
    "IMGP0619.jpg": r"F:\Képek\Vitochov\final",
    "IMGP5505.jpg": r"F:\Képek\Hardegg\final",
    "IMGP8300.jpg": r"F:\Képek\Kozenek\final",
    "IMGP1533.jpg": r"F:\Képek\Vranov\final",
    "IMGP6182.jpg": r"F:\Képek\Brno Ossuary\final",
    "IMGP3734.JPG": r"F:\Képek\Brno Ossuary\final",
    "IMGP6173.jpg": r"F:\Képek\Brno Ossuary\final",
    "IMGP9529.jpg": r"F:\Képek\Plant disease\final",
    "IMGP9520.jpg": r"F:\Képek\Plant disease\final",
    "IMGP9848.jpg": r"F:\Képek\Plant disease\final",
    "IMGP9165.jpg": r"F:\Képek\Oburky-Trestenec\final",
    "IMGP5421.jpg": r"F:\Képek\Kistarcsa\final",
    "IMGP2050.jpg": r"F:\Képek\Budapest\final",
    "IMGP1669.jpg": r"F:\Képek\Budapest\final",
    "IMGP2417.jpg": r"F:\Képek\Olomouc\final",
    "IMGP0183.jpg": r"F:\Képek\Pozsony\final",
    "IMGP9742.jpg": r"F:\Képek\Balatonudvari\final",
    "IMGP9386.jpg": r"F:\Képek\Tihany\final",
    "IMGP9381.jpg": r"F:\Képek\Tihany\final",
    "IMGP0073.jpg": r"F:\Képek\Wind mill\final",
    "IMGP9984.jpg": r"F:\Képek\Wind mill\final",
}

# Complete metadata catalog for all 29 Alamy upload images
ALAMY_IMAGES = [
    {
        "filename": "IMGP0358.jpg",
        "title": "Veveri Castle View Surrounded by Forest and Rocky Terrain",
        "caption": "Distant view of medieval Veveri Castle nestled among dense forest and rugged rocks under a dramatic cloudy sky in the Czech Republic.",
        "keywords": [
            "veveri castle", "hrad veveri", "czech republic", "moravia", "brno",
            "medieval castle", "fortress", "forest", "rock", "rocky hill", "woods",
            "landscape", "cloudy sky", "landmark", "architecture", "travel destination",
            "nature", "outdoor", "historic site", "rocky terrain"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Brno"
    },
    {
        "filename": "IMGP1291.jpg",
        "title": "Historic Veveri Castle Complex Surrounded by Forest in Czech Republic",
        "caption": "Panoramic view of medieval Veveri Castle featuring stone walls and orange tiled roofs, surrounded by green forest under dramatic cloudy skies in Moravia.",
        "keywords": [
            "veveri castle", "czech republic", "castle", "fortress", "medieval architecture",
            "brno", "moravia", "historic building", "stone walls", "red tile roof",
            "defensive tower", "forest", "cloudy sky", "landmark", "travel destination",
            "heritage", "european history", "landscape", "tourism", "outdoor"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Brno"
    },
    {
        "filename": "IMGP5248.jpg",
        "title": "Minaret Tower View Across Green Meadow in Lednice Chateau Park Czech Republic",
        "caption": "Distant view of the historic Minaret tower framed by lush green trees and a wide grassy meadow under a cloudy blue sky in the Lednice-Valtice Cultural Landscape, Czech Republic.",
        "keywords": [
            "minaret", "lednice", "czech republic", "south moravia", "lednice park",
            "chateau garden", "meadow", "grass", "trees", "landmark", "unesco",
            "architecture", "historic tower", "landscape", "nature", "europe", "summer",
            "foliage", "greenery", "scenic", "outdoor", "travel destination"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Lednice"
    },
    {
        "filename": "IMGP5226.jpg",
        "title": "Janohrad Castle Ruin with Excursion Boat in Lednice Czech Republic",
        "caption": "Scenic view of Janohrad castle ruin and a tourist excursion boat on the river within the Lednice-Valtice park landscape in South Moravia, Czech Republic.",
        "keywords": [
            "janohrad", "lednice", "czech republic", "castle", "ruins", "excursion boat",
            "river", "south moravia", "lednice valtice", "unesco", "park", "landscape",
            "water reflection", "architecture", "tourism", "landmark", "historic",
            "nature", "summer", "travel destination", "boat tour"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Lednice"
    },
    {
        "filename": "IMGP4151.jpg",
        "title": "Winter Stream Flowing Through Snow Covered Park in Lednice Czech Republic",
        "caption": "Snow-covered riverbank and bare trees reflecting in calm water at Lednice park during winter in South Moravia, Czech Republic.",
        "keywords": [
            "lednice", "czech republic", "south moravia", "winter", "snow", "river",
            "stream", "park", "garden", "unesco", "trees", "reflection", "water",
            "cold", "frost", "landscape", "nature", "outdoors", "bare trees",
            "riverbank", "seasonal"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Lednice"
    },
    {
        "filename": "IMGP4231.jpg",
        "title": "Winter Landscape of Lednice Chateau Park with River and Snow",
        "caption": "Winter view of a calm river surrounded by snow-covered trees and a glimpse of Lednice Castle in South Moravia, Czech Republic.",
        "keywords": [
            "lednice", "chateau", "castle", "south moravia", "czech republic", "winter",
            "snow", "river", "park", "unesco", "trees", "frozen", "water", "landscape",
            "cold", "travel", "nature", "heritage", "europe"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Lednice"
    },
    {
        "filename": "IMGP2401.jpg",
        "title": "Minaret Tower Reflection in Lake at Lednice Castle Park Czech Republic",
        "caption": "Landscape view of the historic Minaret tower reflected in the pond at Lednice Castle gardens, a UNESCO World Heritage site in South Moravia, Czech Republic.",
        "keywords": [
            "minaret", "lednice", "lednice castle", "czech republic", "south moravia",
            "lednice-valtice", "reflection", "lake", "pond", "park", "tower",
            "unesco world heritage site", "architecture", "historic", "landmark",
            "trees", "water", "europe", "landscape", "travel destination"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Lednice"
    },
    {
        "filename": "_IMG7819.jpg",
        "title": "Chapel of St Anthony on Hill in Dolni Kounice Czech Republic",
        "caption": "White historic chapel with a red tiled roof situated on a green hill under a partly cloudy blue sky in Dolni Kounice, Czech Republic.",
        "keywords": [
            "chapel", "church", "dolni kounice", "czech republic", "moravia",
            "st anthony", "architecture", "hill", "pilgrimage", "christian",
            "landmark", "religion", "exterior", "red roof", "green hill",
            "cloudy sky", "europe", "historic building", "travel destination", "summer"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Dolni Kounice"
    },
    {
        "filename": "IMGP0619.jpg",
        "title": "Historic Stone Church of St Michael in Green Field Vitochov Czech Republic",
        "caption": "Historic stone church of St. Michael standing on a green grassy hill under a blue sky in Vitochov, Czech Republic.",
        "keywords": [
            "church", "vitochov", "czech republic", "stone church", "st michael",
            "chapel", "architecture", "medieval", "historic", "landscape", "green field",
            "rural", "countryside", "hill", "christian", "religion", "heritage",
            "landmark", "summer", "blue sky"
        ],
        "country": "Czech Republic",
        "province": "Vysocina",
        "city": "Vitochov"
    },
    {
        "filename": "IMGP5505.jpg",
        "title": "Medieval Hardegg Castle on Forested Cliff in Lower Austria",
        "caption": "Landscape view of the historic medieval fortress Burg Hardegg situated on a rocky ridge surrounded by forested hills in Lower Austria near the Czech border under a partly cloudy summer sky. Suitable for European travel, tourism, and historical architectural projects.",
        "keywords": [
            "hardegg castle", "burg hardegg", "austria", "medieval castle", "fortress",
            "thayatal", "lower austria", "stone castle", "watchtower",
            "medieval architecture", "historic landmark", "ancient fortress", "cliff",
            "forest", "valley", "landscape", "european history", "fortification",
            "stone wall", "tourism", "travel destination", "middle ages", "nature",
            "exterior", "sunny day"
        ],
        "country": "Austria",
        "province": "Lower Austria",
        "city": "Hardegg"
    },
    {
        "filename": "IMGP8300.jpg",
        "title": "Blooming Pink Cherry Blossom Tree in Spring",
        "caption": "Close-up of pink cherry blossoms in full bloom on tree branches in daylight. Suitable for spring and nature backgrounds.",
        "keywords": [
            "cherry blossom", "sakura", "pink flowers", "blooming", "spring",
            "tree branches", "floral", "prunus", "blossom", "nature", "botany",
            "petals", "seasonal", "flora", "springtime", "daylight", "close up",
            "moravia", "czech republic"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Kozenek"
    },
    {
        "filename": "IMGP1533.jpg",
        "title": "Vranov nad Dyji Chateau on Rocky Cliff in South Moravia Czech Republic",
        "caption": "Baroque chateau of Vranov nad Dyji situated atop a rocky cliff surrounded by green forest under a partly cloudy sky.",
        "keywords": [
            "vranov nad dyji", "chateau", "castle", "south moravia", "czech republic",
            "cliff", "rock", "baroque architecture", "architecture", "landmark",
            "fortress", "palace", "historical building", "europe", "travel destination",
            "tourism", "heritage", "monument", "stone wall", "forested hill"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Vranov nad Dyji"
    },
    {
        "filename": "IMGP6182.jpg",
        "title": "Brno Ossuary with Pillar of Human Bones in Czech Republic",
        "caption": "Historical underground ossuary beneath the Church of St. James in Brno, Czech Republic, featuring arched brick vaults and a central pillar constructed from human skulls and bones.",
        "keywords": [
            "brno ossuary", "ossuary", "human bones", "skulls", "catacombs",
            "crypt", "brno", "czech republic", "st james church", "bone church",
            "underground", "brick arch", "burial vault", "historical", "skeleton",
            "memento mori", "tomb", "grave", "historic site", "interior architecture"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Brno"
    },
    {
        "filename": "IMGP3734.JPG",
        "title": "Underground Vault at Brno Ossuary with Human Bones and Skulls in Czech Republic",
        "caption": "Interior view of the Brno Ossuary located beneath the Church of St. James in Brno, Czech Republic. The subterranean brick vault displays walls and a central pillar constructed from stacked human skulls and skeletal remains, accompanied by historic gravestones and exhibition lighting. Suitable for historical, archaeological, educational, and travel documentary projects.",
        "keywords": [
            "brno ossuary", "ossuary", "catacomb", "human bones", "skulls",
            "skeleton", "crypt", "church of st james", "brno", "czech republic",
            "underground", "vault", "brick arch", "historic", "archaeology",
            "tomb", "burial site", "cemetery", "death", "memento mori",
            "moravia", "tourist attraction", "monument", "medieval", "history"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Brno"
    },
    {
        "filename": "IMGP6173.jpg",
        "title": "Human Skulls and Bones in the Brno Ossuary",
        "caption": "Wall of stacked human skulls and skeletal remains inside the historic ossuary at the Church of St. James in Brno, Czech Republic.",
        "keywords": [
            "skull", "bones", "ossuary", "human bones", "skeleton", "brno",
            "czech republic", "catacomb", "cemetery", "death", "mortality",
            "crypt", "archaeology", "historical", "church of st james",
            "memento mori", "burial", "charnel house", "anatomy", "remains",
            "underground"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Brno"
    },
    {
        "filename": "IMGP9529.jpg",
        "title": "Peach Leaf Curl Disease on Fruit Tree Foliage",
        "caption": "Close-up of a fruit tree leaf showing distortion and blistering caused by peach leaf curl fungal infection in an orchard.",
        "keywords": [
            "peach leaf curl", "leaf curl", "taphrina deformans", "plant disease",
            "fungal infection", "infected leaf", "plant pathology", "fruit tree",
            "foliage", "agriculture", "horticulture", "leaf blister", "botany",
            "crop damage", "garden pest", "orchard", "damaged leaf", "plant health"
        ],
        "country": "Hungary",
        "province": "Pest County",
        "city": "Kistarcsa"
    },
    {
        "filename": "IMGP9520.jpg",
        "title": "Mummified Plum Infected with Brown Rot Fungus on Tree Branch",
        "caption": "Close-up of a shriveled, mummified plum infected with fungal brown rot on a tree trunk, displaying spore pustules in an orchard.",
        "keywords": [
            "brown rot", "monilinia", "plant disease", "fungal infection",
            "mummified fruit", "plum rot", "tree trunk", "horticulture",
            "agriculture", "plant pathology", "crop damage", "rotten fruit",
            "fungus", "spores", "botany", "orchard disease", "fruit decay",
            "garden pest"
        ],
        "country": "Hungary",
        "province": "Pest County",
        "city": "Kistarcsa"
    },
    {
        "filename": "IMGP9848.jpg",
        "title": "Pear Rust Fungal Infection with Orange Spots on Green Leaves",
        "caption": "Close-up photograph of pear tree leaves infected with pear rust fungus, displaying characteristic bright orange and yellow necrotic spots. Useful for agricultural, botanical, gardening, and plant pathology contexts.",
        "keywords": [
            "pear rust", "gymnosporangium sabinae", "plant disease", "fungal infection",
            "leaf spot", "pear leaf", "horticulture", "plant pathology", "fungus",
            "agriculture", "infected leaves", "botany", "orchard", "orange spots",
            "tree disease", "crop protection", "sick plant", "foliage",
            "garden problem", "blight"
        ],
        "country": "Hungary",
        "province": "Pest County",
        "city": "Kistarcsa"
    },
    {
        "filename": "IMGP9165.jpg",
        "title": "White Crab Spider on Purple Wild Orchid Flowers",
        "caption": "Macro shot of a white crab spider camouflaged among blooming purple wild orchid petals, photographed in Oburky-Trestenec, Czech Republic.",
        "keywords": [
            "crab spider", "spider", "orchid", "purple flower", "misumena vatia",
            "arachnid", "macro photography", "ambush predator", "wild orchid",
            "blossoms", "insect", "prey", "czech republic", "nature", "wildlife",
            "flora", "fauna", "entomology", "botany", "predator"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Blansko"
    },
    {
        "filename": "IMGP5421.jpg",
        "title": "Ripe Peach Fruit Hanging on Tree Branch",
        "caption": "Close-up of ripe peaches hanging on a tree branch surrounded by green leaves in an orchard.",
        "keywords": [
            "peach", "fruit", "tree", "branch", "leaves", "orchard", "ripe",
            "agriculture", "harvest", "foliage", "food", "organic", "gardening",
            "nature", "prunus persica", "raw", "close up", "hungary"
        ],
        "country": "Hungary",
        "province": "Pest County",
        "city": "Kistarcsa"
    },
    {
        "filename": "IMGP2050.jpg",
        "title": "Baross Gabor Statue in Front of Keleti Railway Station in Budapest",
        "caption": "Exterior view of the historic Keleti Railway Station and the Baross Gabor monument under a clear blue sky in Budapest, Hungary.",
        "keywords": [
            "budapest", "hungary", "keleti railway station", "keleti palyaudvar",
            "baross gabor", "statue", "monument", "train station", "railway terminal",
            "architecture", "historic building", "facade", "european landmark",
            "transportation hub", "travel destination", "exterior", "daytime",
            "hungarian architecture"
        ],
        "country": "Hungary",
        "province": "Budapest",
        "city": "Budapest"
    },
    {
        "filename": "IMGP1669.jpg",
        "title": "Suburban Railway Station and Tracks in Cinkota Budapest Hungary",
        "caption": "Rail tracks, overhead electrical wires, and platform facilities at the Cinkota suburban train station in Budapest, Hungary under an overcast sky.",
        "keywords": [
            "railway", "train tracks", "cinkota", "budapest", "hungary",
            "train station", "suburban train", "overhead lines", "railroad",
            "transportation", "public transit", "railway tracks", "electric railway",
            "platform", "track switch", "rails", "urban transit", "travel",
            "commute", "junction"
        ],
        "country": "Hungary",
        "province": "Budapest",
        "city": "Budapest"
    },
    {
        "filename": "IMGP2417.jpg",
        "title": "Elevated View of Olomouc City Center and Historic Church Spires Czech Republic",
        "caption": "Panoramic elevated view over the historic city of Olomouc in Moravia, Czech Republic. The composition features a traditional copper church spire with a golden cross in the foreground, terracotta tiled rooftops, and distant cathedral towers beneath an overcast sky. Suitable for European travel, historical heritage, and urban architecture projects.",
        "keywords": [
            "olomouc", "czech republic", "moravia", "church spire", "cityscape",
            "aerial view", "historic center", "rooftop", "cathedral", "cross",
            "architecture", "old town", "central europe", "cloudy sky",
            "skyline", "european travel", "urban landscape", "heritage", "town",
            "roof", "overcast", "steeple", "tourism"
        ],
        "country": "Czech Republic",
        "province": "Olomouc Region",
        "city": "Olomouc"
    },
    {
        "filename": "IMGP0183.jpg",
        "title": "Bratislava Castle Overlooking City on Hill in Slovakia",
        "caption": "Panoramic view of Bratislava Castle situated on a rocky hill overlooking the capital city of Slovakia. The historic fortress features white facade walls and red roofs under a dramatic sky with soft sunlight, suitable for European travel, tourism, and historical architectural themes.",
        "keywords": [
            "bratislava castle", "bratislava", "slovakia", "bratislavsky hrad",
            "fortress", "castle", "landmark", "architecture", "historic building",
            "cityscape", "european landmark", "central europe", "capital city",
            "hill", "travel destination", "tourism", "danube riverbank",
            "exterior view", "old town", "cloudy sky", "heritage", "monument"
        ],
        "country": "Slovakia",
        "province": "Bratislava Region",
        "city": "Bratislava"
    },
    {
        "filename": "IMGP9742.jpg",
        "title": "Historic Heart Shaped Gravestones in Balatonudvari Cemetery Hungary",
        "caption": "Historic heart-shaped limestone gravestones in an old cemetery at Balatonudvari, Hungary, under a blue summer sky with green trees.",
        "keywords": [
            "balatonudvari", "heart shaped gravestone", "gravestones", "hungary",
            "lake balaton", "cemetery", "tombstone", "historic cemetery",
            "graveyard", "headstone", "limestone", "heritage", "memorial",
            "old cemetery", "hungarian culture", "traditional", "burial ground",
            "monument", "landmark", "history", "outdoor", "daytime", "sunny",
            "green trees", "grass", "sky", "cloud", "travel destination"
        ],
        "country": "Hungary",
        "province": "Veszprem County",
        "city": "Balatonudvari"
    },
    {
        "filename": "IMGP9386.jpg",
        "title": "Tihany Benedictine Abbey and Hillside Village Skyline Overlooking Lake Balaton",
        "caption": "Panoramic view across the calm waters of Lake Balaton towards the historic Benedictine Abbey and hillside village of Tihany under a sunny summer sky with cumulus clouds in Hungary.",
        "keywords": [
            "tihany", "lake balaton", "tihany abbey", "benedictine abbey", "hungary",
            "village", "church", "lake", "waterfront", "shoreline", "hillside",
            "landscape", "historic landmark", "architecture", "travel destination",
            "hungarian", "eastern europe", "balaton felvidek", "summer", "sunny day",
            "cumulus clouds", "blue sky", "water reflection", "scenic", "tourism",
            "heritage", "holiday", "destination", "town", "central europe",
            "panoramic view", "outdoor", "vacation", "reed"
        ],
        "country": "Hungary",
        "province": "Veszprem County",
        "city": "Tihany"
    },
    {
        "filename": "IMGP9381.jpg",
        "title": "Landscape View of Tihany Village and Benedictine Abbey in Hungary",
        "caption": "Landscape view of the historic Tihany Abbey and hillside village across a green field under a summer sky at Lake Balaton, Hungary.",
        "keywords": [
            "tihany", "hungary", "lake balaton", "tihany abbey", "benedictine abbey",
            "village", "hillside", "landscape", "church", "europe", "european",
            "countryside", "rural", "field", "meadow", "reeds", "architecture",
            "historic", "travel", "tourism", "summer", "blue sky", "clouds"
        ],
        "country": "Hungary",
        "province": "Veszprem County",
        "city": "Tihany"
    },
    {
        "filename": "IMGP0073.jpg",
        "title": "Historic Kunkovice Windmill Surrounded by Crimson Clover Fields in South Moravia",
        "caption": "Historic Dutch style stone windmill standing in rolling agricultural landscape among dark red crimson clover and green fields under a dramatic sky in Kunkovice, South Moravia, Czech Republic.",
        "keywords": [
            "kunkovice windmill", "south moravia", "czech republic", "moravian tuscany",
            "windmill", "historic windmill", "dutch windmill", "crimson clover",
            "red clover field", "rolling hills", "rural landscape", "agriculture",
            "farmland", "stone mill", "countryside", "field", "heritage", "landmark",
            "travel destination", "central europe", "scenic", "traditional architecture",
            "moravia", "agricultural landscape", "contrast", "dramatic sky", "tourism",
            "destination", "crop", "summer", "outdoors", "nature", "culture"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Kunkovice"
    },
    {
        "filename": "IMGP9984.jpg",
        "title": "Rapeseed Field in Bloom with Rural Village and Church in Moravia",
        "caption": "Vibrant yellow flowering rapeseed field in spring with a distant traditional village and church tower nestled among rolling green hills in Moravia, Czech Republic.",
        "keywords": [
            "rapeseed", "canola field", "yellow flowers", "moravia", "czech republic",
            "rural landscape", "countryside", "village", "church tower", "agriculture",
            "rolling hills", "farmland", "brassica napus", "spring", "farming", "crop",
            "aerial perspective", "green hills", "central europe", "idyllic", "scenery",
            "travel destination", "pastoral", "european landscape", "field",
            "cultivation", "nature", "clouds", "overcast sky", "rustic",
            "moravian countryside", "outdoor"
        ],
        "country": "Czech Republic",
        "province": "South Moravia",
        "city": "Brankovice"
    }
]

def update_metadata(file_path, item):
    """
    Writes EXIF and IPTC metadata to the given image file.
    """
    if not os.path.exists(file_path):
        return False, "File does not exist"
        
    title = item["title"]
    caption = item["caption"]
    keywords = item["keywords"]
    kw_semicolon = ";".join(keywords)
    
    # 1. Update EXIF with piexif
    try:
        exif_dict = piexif.load(file_path)
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
        
    if "0th" not in exif_dict:
        exif_dict["0th"] = {}
        
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = caption.encode("utf-8")
    exif_dict["0th"][piexif.ImageIFD.XPTitle] = title.encode("utf-16le")
    exif_dict["0th"][piexif.ImageIFD.XPComment] = caption.encode("utf-16le")
    exif_dict["0th"][piexif.ImageIFD.XPKeywords] = kw_semicolon.encode("utf-16le")
    
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, file_path)
    
    # 2. Update IPTC with iptcinfo3
    info = iptcinfo3.IPTCInfo(file_path, force=True)
    info['object name'] = title.encode("utf-8")
    info['caption/abstract'] = caption.encode("utf-8")
    info['keywords'] = [k.encode("utf-8") for k in keywords]
    if item.get("country"):
        info['country/primary location name'] = item["country"].encode("utf-8")
    if item.get("province"):
        info['province/state'] = item["province"].encode("utf-8")
    if item.get("city"):
        info['city'] = item["city"].encode("utf-8")
    info.save()
    
    # Cleanup backup file if generated
    backup_file = file_path + "~"
    if os.path.exists(backup_file):
        try:
            os.remove(backup_file)
        except OSError:
            pass
            
    return True, "OK"

def verify_image(file_path):
    """
    Verifies that EXIF and IPTC fields were correctly stored.
    """
    exif = piexif.load(file_path)
    xp_title_raw = exif['0th'].get(piexif.ImageIFD.XPTitle, b'')
    if isinstance(xp_title_raw, tuple):
        exif_title = bytes(xp_title_raw).decode("utf-16le", errors="ignore")
    elif isinstance(xp_title_raw, bytes):
        exif_title = xp_title_raw.decode("utf-16le", errors="ignore")
    else:
        exif_title = ""
        
    exif_desc_raw = exif['0th'].get(piexif.ImageIFD.ImageDescription, b'')
    exif_desc = exif_desc_raw.decode("utf-8", errors="ignore") if isinstance(exif_desc_raw, bytes) else ""
    
    with Image.open(file_path) as im:
        iptc = IptcImagePlugin.getiptcinfo(im)
        iptc_title = iptc.get((2, 5), b"").decode("utf-8", errors="ignore") if iptc else ""
        iptc_caption = iptc.get((2, 120), b"").decode("utf-8", errors="ignore") if iptc else ""
        iptc_kws = [k.decode("utf-8", errors="ignore") for k in iptc.get((2, 25), [])] if iptc else []
        iptc_country = iptc.get((2, 101), b"").decode("utf-8", errors="ignore") if iptc else ""
        iptc_city = iptc.get((2, 90), b"").decode("utf-8", errors="ignore") if iptc else ""
        
    return {
        "exif_title": exif_title,
        "exif_desc": exif_desc,
        "iptc_title": iptc_title,
        "iptc_caption": iptc_caption,
        "keyword_count": len(iptc_kws),
        "location": f"{iptc_city}, {iptc_country}" if iptc_city else iptc_country
    }

def export_alamy_csv(output_csv_path, images):
    """
    Exports Alamy metadata into CSV format.
    """
    headers = ["Filename", "Title", "Caption", "Keywords", "Country", "Province", "City"]
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for item in images:
            writer.writerow([
                item["filename"],
                item["title"],
                item["caption"],
                ", ".join(item["keywords"]),
                item.get("country", ""),
                item.get("province", ""),
                item.get("city", "")
            ])

def main():
    target_dir = r"G:\upload_temp"
    print("=== Writing Alamy EXIF & IPTC Metadata ===")
    print(f"Target directory: {target_dir}")
    print(f"Total images: {len(ALAMY_IMAGES)}\n")
    
    success_count = 0
    for idx, item in enumerate(ALAMY_IMAGES, 1):
        fn = item["filename"]
        target_path = os.path.join(target_dir, fn)
        
        ok, msg = update_metadata(target_path, item)
        if ok:
            veri = verify_image(target_path)
            print(f"[{idx:02d}/{len(ALAMY_IMAGES)}] {fn}:")
            print(f"     Title   : {veri['iptc_title']}")
            print(f"     Caption : {veri['iptc_caption'][:70]}...")
            print(f"     Keywords: {veri['keyword_count']} tags | Location: {veri['location']}")
            success_count += 1
        else:
            print(f"[{idx:02d}/{len(ALAMY_IMAGES)}] {fn}: FAILED - {msg}")
            
        # Also update source archive if present
        if fn in SOURCE_DIRS:
            source_path = os.path.join(SOURCE_DIRS[fn], fn)
            if os.path.exists(source_path):
                update_metadata(source_path, item)

    # Export CSV
    csv_path = os.path.join(target_dir, "alamy_metadata.csv")
    export_alamy_csv(csv_path, ALAMY_IMAGES)
    print(f"\nAlamy CSV exported to: {csv_path}")
    print(f"\n[COMPLETE] Successfully embedded metadata into {success_count}/{len(ALAMY_IMAGES)} images!")

if __name__ == "__main__":
    main()
