# AI Stock Fotó Metaadat & CSV Munkafolyamat (Stock Photo Workflow)

Ez a könyvtár tartalmazza az automatizált stock fotó előkészítő, méretcsökkentő és metaadat-generáló munkafolyamatot **Adobe Stock** és **Shutterstock** platformokhoz.

---

## 🚀 A Munkafolyamat Lépései (Hogyan dolgoztunk)

### 1. Lépés: Előnézetek létrehozása (Token- és sávszélesség-takarékosság)
A nagyméretű (RAW / 24-50+ Megapixeles) képek közvetlen feltöltése és elemzése LLM modellekkel rendkívül sok tokent és adatforgalmat igényelne.
- A `create_thumbnails.py` szkript a célkönyvtáron belül létrehoz egy `_temp/` almappát.
- Minden képről generál egy lecsökkentett, web-optimalizált (max. 1024px széles/magas, minőségi Lanczos resampling) másolatot.
- Ezzel párhuzamosan kinyeri az eredeti fájlok **EXIF**, **XMP** és **GPS** koordináta adatait, és elmenti a `metadata_extracted.json` fájlba.

### 2. Lépés: AI Képelemzés és Osztályozás (Commercial vs. Editorial)
A modellek (vagy felhasználó) átnézik a `_temp` előnézeti képeket és az alábbi szabályok szerint osztályoznak:
- **Commercial (Kereskedelmi célú):**
  - Nem szerepelnek a képen felismerhető személyek (vagy van róluk Model Release).
  - Nem láthatók védett márkajelzések, logók.
  - Tiszta építészeti, táj-, természet- vagy absztrakt fotók.
  - Leírás: Tárgyilagos, leíró jellegű cím angol nyelven.
- **Editorial (Szerkesztőségi / Sajtó célú):**
  - Felismerhető turisták, látogatók, védett márkanevek, rendszámok vagy nem engedélyezett modern műalkotások láthatók.
  - **Kötelező formátum:** `VÁROS, ORSZÁG - HÓNAP ÉV: Esemény / helyszín leírása angolul.`  
    *Példa:* `SZEKESFEHERVAR, HUNGARY - AUGUST 2023: Tourists visit the fairytale Bory Castle (Bory-var) surrounded by lush garden.`

### 3. Lépés: Kulcsszavak és Kategóriák meghatározása
- **Kulcsszavak száma:** Képenként 25–45 releváns, keresett angol kifejezés.
- **Fontossági sorrend:** A legfontosabb specifikus kulcsszavak elöl (pl. `bory castle`, `szekesfehervar`, `hungary`), majd a tágabb tematikus kategóriák (`architecture`, `travel`, `scenic`).
- **Kategóriák:**
  - Adobe Stock: Numerikus ID (`2`: Buildings and Architecture, `21`: Travel, stb.).
  - Shutterstock: Hivatalos kategórianevek (`Buildings/Landmarks, Travel`).

### 4. Lépés: Platform-kompatibilis CSV fájlok generálása
A `generate_stock_csv.py` szkript előállítja:
1. `adobe_stock.csv`: Kötegelt feltöltéshez az Adobe Stock Contributor felületére.
2. `shutterstock.csv`: Kötegelt feltöltéshez a Shutterstock Contributor felületére.
3. `<fájlnév>_adobe.csv` és `<fájlnév>_shutterstock.csv`: Egyedi fájlkezelőkhöz / külső stock menedzser szoftverekhez (pl. StockSubmitter, Xpiks).

---

## 📂 Fájlstruktúra

```text
stock-workflow/
├── README.md                  # Ez a dokumentáció
├── create_thumbnails.py       # Előnézet-készítő és EXIF/GPS kinyerő szkript
├── generate_stock_csv.py      # Adobe Stock és Shutterstock CSV generáló szkript
└── bory_castle_example.json   # Referencia adatkészlet a Bory-vár fotóiról
```

---

## 🛠️ Használati Útmutató Új Fotósorozathoz

### 1. Képek kicsinyítése és metaadat kinyerése
Futtasd a szkriptet az új fotókat tartalmazó mappára:
```powershell
python "F:\AI-WORK\ai-workflows\stock-workflow\create_thumbnails.py" --input "F:\Kepek\Uj_Helyszin" --max-size 1024
```
*Ez létrehozza az `F:\Kepek\Uj_Helyszin\_temp` mappát az átméretezett képekkel és a `metadata_extracted.json` fájllal.*

### 2. AI Elemzés és Adatstruktúra
A `_temp` mappában lévő képeket az AI gyorsan és kis tokenfogyasztással be tudja olvasni, majd elkészíteni a JSON leírást (lásd a `bory_castle_example.json` mintát).

### 3. CSV fájlok legenerálása
Ha a JSON leírás elkészült, futtasd:
```powershell
python "F:\AI-WORK\ai-workflows\stock-workflow\generate_stock_csv.py" --json "F:\Kepek\Uj_Helyszin\image_data.json" --output "F:\Kepek\Uj_Helyszin"
```

---

## 📋 Stock Platform Szabványok Összegzése

| Tulajdonság | Adobe Stock | Shutterstock |
| :--- | :--- | :--- |
| **Kötegelt fájlnév** | `adobe_stock.csv` | `shutterstock.csv` |
| **Oszlopok** | `Filename,Title,Keywords,Category,Releases` | `Filename,Description,Keywords,Categories,Illustration,Mature content,Editorial` |
| **Editorial Jelölés** | A címben vagy a feltöltési felületen | `Editorial` oszlopban: `yes` / `no` |
| **Editorial Címforma** | Szabad leírás vagy `CITY, COUNTRY - DATE: ...` | `CITY, COUNTRY - MONTH DAY, YEAR: ...` |
| **Kulcsszavak száma** | Max. 49 (első 10 kiemelten fontos) | Min. 7, Max. 50 |
| **Kategória mező** | Kategória száma (pl. `2`) | Vesszővel elválasztott név (max 2) |
