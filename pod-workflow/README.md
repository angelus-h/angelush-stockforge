# Fine Art America (FAA) & POD Metaadat Munkafolyamat (Print-on-Demand Workflow)

Ez a munkafolyamat kifejezetten a **Fine Art America (FAA)** és **Pixels.com** Print-on-Demand (POD) művészeti piacterekre optimalizált SEO címek, 3-bekezdéses érzelmi értékesítési leírások (sales letters) és kulcsszavak generálására készült.

---

## 🎯 A Munkafolyamat Célja és Szabályai (`FAA-prompt.txt` alapján)

### 1. Előnézetek létrehozása (Token- és adatforgalom-takarékosság)
A nagyméretű (24-36+ Megapixeles) RAW és finális fotók közvetlen beolvasása helyett a rendszer a célkönyvtárban létrehoz egy `_temp/` almappát, és max. 1024px méretű web-optimalizált másolatokat készít.

### 2. GPS és Helyszín Kontextus
A fotók beágyazott GPS koordinátáit és EXIF/XMP adatait felhasználva automatikusan azonosítja a pontos földrajzi helyszínt és a történelmi környezetet (pl. **Hardegg Castle / Burg Hardegg, Thayatal Nemzeti Park, Alsó-Ausztria / Čížov Vasfüggöny Emlékhely**).

### 3. SEO Címképzés (`optimized_title`)
- **Tilos:** Nyers fájlnevek, számok (`#1`, `v2`), technikai kameranevek vagy túl absztrakt megnevezések.
- **Kötelező:** Keresőoptimalizált, lakberendező-barát és hangulatos cím, amely pontosan tartalmazza a témát és a stílust.  
  *Példa:* `Medieval Hardegg Castle Rising Above Green Forest - Austrian Fortress Wall Art` vagy `Infrared Fairytale Hardegg Town and Castle - Dreamy Austrian Landscape Fine Art Print`.

### 4. 3-Bekezdéses Értékesítési Leírás (`sales_description`)
- **1. Bekezdés (Hangulat & Művészi Kifejezés):** Megfesti a képi látványt, a fényeket (infravörös ragyogás, nyári napsütés), és a kép érzelmi hatását (nyugtató, természetközeli, harmonikus).
- **2. Bekezdés (Belsőépítészet & Elhelyezés):** Konkrét szobák és belső terek megnevezése (Living Room, Master Bedroom, Cozy Study, Calming Office, Hotel Lobby, Healthcare/Medical Waiting Room - healing art), kiemelve a domináns színeket.
- **3. Bekezdés (Minőség & Garancia):** Múzeumi minőségű nyomatok (vászonkép, keretezett galérianyomat, akril, fémnyomat), 30 napos pénzvisszafizetési garancia, Angelus H tájfotós aláírással.

### 5. Kulcsszavak (`comma_separated_tags`)
- **SZIGORÚ LIMIT:** A teljes kulcsszó-karakterlánc hossza **500 karakter alatt** kell maradjon (vesszőkkel együtt).
- Stratégiai összetétel: Tág témák (`wall art`, `landscape print`), stílus (`infrared photography`, `fine art print`), konkrét elemek (`castle`, `forest`, `river`), színek (`emerald green`, `silver white`), hangulat (`calming art`, `healing art`, `serene`), szobák (`living room decor`, `office wall art`) és földrajz (`hardegg`, `austria`, `thayatal`).

---

## 📂 Fájlstruktúra

```text
pod-workflow/
├── README.md                     # Ez a dokumentáció
├── FAA-prompt.txt                # Az eredeti FAA AI prompt
├── pod_metadata_generator.py     # Automatizált FAA JSON és CSV generáló szkript
├── hardegg_dataset.json          # A 46 Hardegg művészeti alkotás strukturált adatai
├── faa_metadata_results.json     # A generált végleges FAA JSON adatbázis
└── faa_metadata_results.csv      # A feltöltésre kész FAA CSV fájl
```

---

## 🛠️ Használati Útmutató Új Fotósorozathoz

### 1. Előnézetek generálása és metaadatok kinyerése
```powershell
python "F:\AI-WORK\ai-workflows\stock-workflow\create_thumbnails.py" --input "F:\Kepek\Uj_Mappa" --max-size 1024
```

### 2. FAA Metaadatok előállítása és exportálása
```powershell
python "F:\AI-WORK\ai-workflows\pod-workflow\pod_metadata_generator.py" --json "F:\AI-WORK\ai-workflows\pod-workflow\hardegg_dataset.json" --output "F:\Kepek\Uj_Mappa"
```

---

## 🏰 Hardegg Fotósorozat Összefoglalása (46 Alkotás)

| Csoport / Képtartomány | Darabszám | Stílus / Technika | Fő Téma / Látvány |
| :--- | :--- | :--- | :--- |
| **`IMGP1340 - IMGP1351`** | 12 db | Színes képzőművészeti fotó | Burg Hardegg középkori bástyái és tornyai az erdőből |
| **`IMGP1357 - IMGP1373`** | 8 db | Színes panoráma tájkép | Reginafelsen kilátó panorámája a várra és a Thayatal völgyre |
| **`IMGP1555 - IMGP1590`** | 14 db | **Infravörös (IR) Fine Art** | Tündérmese-szerű fehér lombkoronás Hardegg vár és város |
| **`IMGP2352 - IMGP2374`** | 4 db | Színes folyóparti tájkép | Osztrák-cseh határhíd a Thaya (Dyje) folyón a várral |
| **`IMGP2383 - IMGP2386`** | 2 db | Történelmi emlékhely fotó | Čížov Vasfüggöny emlékhely, tankcsapdák és őrtorony |
| **`IMGP5491 - IMGP5505`** | 3 db | Nyári tölgyerdős panoráma | Tölgyfákkal keretezett Hardegg panoráma nyári felhőkkel |
| **`IMGP6691 - IMGP6702`** | 3 db | Rusztikus vidéki tájkép | Csendes alsó-ausztriai falusi utcák és kápolnatornyok |
