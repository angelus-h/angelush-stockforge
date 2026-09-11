# Teljeskörű POD és Stock Fotó Sales Stratégia
*(Automatizált, Skálázható Értékesítés a Gemini Flash segítségével)*

## 1. A Platformok és a "Termék-Match" Stratégia
Nem minden kép való mindenhova. A siker kulcsa a megfelelő képi világ párosítása a megfelelő platformmal és közönséggel.

*   **Fine Art America (FAA) / Pixels:**
    *   *Fókusz:* Lakberendezés, irodai dekoráció, prémium fali képek (canvas, acrylic).
    *   *Tartalom:* Tájképek, infravörös fotók, "Healing Art" (nyugtató, pasztell színek), absztrakt természet.
    *   *Sztori/SEO:* "Jenny Rainbow" stratégia. Érzelmek, békesség, lakberendezési kulcsszavak (pl. "Bedroom decor", "Feng Shui").
*   **Microstock (Shutterstock, Adobe Stock, Pond5):**
    *   *Fókusz:* Kereskedelmi felhasználás, reklámügynökségek, weboldal készítők.
    *   *Tartalom:* Hagyományos utazási videók, B-roll anyagok (pl. Plumlov, Vranov drón/kameraképek), izolált tárgyak, mindennapi szituációk.
    *   *Sztori/SEO:* Szigorúan tényszerű, objektív kulcsszavak (helyszín, időjárás, cselekvés, objektumok).
*   **Merch / Ajándéktárgyak (Redbubble, Teespring, Merch by Amazon):**
    *   *Fókusz:* Pólók, bögrék, telefontokok, matricák.
    *   *Tartalom:* Grafikus elemek, tipográfia, vicces feliratok, izolált (vektoros/átlátszó hátterű) művészeti formák. (Egy szimpla tájkép rosszul mutat egy pólón).
    *   *Sztori/SEO:* Popkultúra, niche hobbik, humor, trendek.

## 2. A "Jenny Rainbow / Matt Payne" FAA Masterclass (A Belsőépítészeti Fókusz)
A Fine Art értékesítés pszichológiája: az emberek nem képet vesznek, hanem *érzést* és *megoldást* egy üres falra.

*   **A "Katalógus" helyett "Kollekciók":** Ne "Csehország" legyen a galéria neve. Legyen "Romantic Bohemian Gardens" vagy "Ethereal Infrared Landscapes".
*   **A 3 Bekezdéses Szabály (A Leírás Pszichológiája):**
    1.  *Érzelem & Téma:* Mi van a képen és milyen érzést (pl. békét, nyugalmat) áraszt.
    2.  *Belsőépítészet (A Horog):* Melyik szobába illik (pl. "Perfect for a serene master bedroom or executive office").
    3.  *Minőség & Bizalom:* Múzeumi minőség, 30 napos garancia (hogy bátran merjenek rendelni).
*   **A Cím (Title) Képlete:** `[Fő téma/Érzelem] + [Fény/Hangulat] + [Helyszín] + [Wall Art/Decor megjelölés]`. (Soha ne legyen benne sorszám, pl. #1!).

## 3. A Munkafolyamat (Workflow) Automatizálása
Az időd a legdrágább. Mivel egyszerre kis adagokban (batch) dolgozol, a jelenlegi *OpenCode + Gemini Flash* kombó a leghatékonyabb:

*   **Stock Videók / Microstock (A "Tényszerű" Batch):**
    *   *Folyamat:* Mappa bedobása OpenCode-ba -> Gemini Flash elemzi a `.mp4` / `.jpg` fájlokat -> CSV generálás a Shutterstock/Adobe/Pond5 oszlopszerkezete szerint.
*   **Fine Art / POD (Az "Érzelmi" Batch):**
    *   *Folyamat:* A `FAA-prompt.txt` használata OpenCode-ban (vagy a Python szkript bevonása). A Gemini Flash itt a *Jenny Rainbow stratégiát* alkalmazza: JSON-be vagy CSV-be köpi a SEO címet, a 3 bekezdést és a (szigorúan 500 karakter alatti, relevancia szerint csökkenő) tageket.

## 4. Jövőkép: Pólóminták és Niche Termékek
Ha belépsz a póló/ajándék piacra, az új workflowt igényel:
*   A képeket (pl. infravörös fák) AI upscalerrel és háttéreltávolítóval (pl. Photoroom/Clipdrop) le kell választani, hogy jól mutassanak a ruhákon.
*   A Gemini Flash promptot át kell állítani: ott a "funny", "gift for him/her", "trending" és a specifikus hobbi kulcsszavak fognak eladni, nem a belsőépítészet.

---
*Mentve: 2026. Szeptember 1.*

## 5. A B2B és Intézményi Vásárlók Pszichológiája (A Recent Sales Elemzés)
Az eladások (különösen a Fine Art America platformon) jelentős részét nem magánszemélyek impulzusvásárlásai teszik ki, hanem **belsőépítészek, lakberendezők és intézményi beszerzők (B2B)** nagy volumenű megrendelései.

A "Recent Sales" elemzéséből származó 3 aranyköpés a portfólió építéséhez:

1.  **A "Szálloda/Kórház Effektus" (Tömeges Vásárlás):**
    *   A lakberendezők (pl. az elemzésbeli kanadai vásárló) nem egy képet vesznek, hanem 30-40 darab, *színben és hangulatban harmonizáló* alkotást egy adott projekthez (kórház folyosó, boutique hotel, irodaház).
    *   *Akció:* Amikor egy sorozatot töltesz fel (pl. infravörös cseh tájak), a képeknek vizuálisan koherensnek kell lenniük. A leírásokban emeld ki a **"Healing Art"** és **"Ethereal/Calming Space"** szavakat, hogy a kórházak/hotelek belsőépítészei rátaláljanak.
2.  **A Funkcionális Fali Dekoráció (Étel, Wellness, Tudomány):**
    *   Az éttermeknek spárga- és lazacfotók kellenek a falra. A kutatóintézeteknek baktérium illusztrációk. A te portfóliódból a természetfotók tökéletesek **Wellness és Spa** központok falaira.
    *   *Akció:* Soha ne csak "tájképként" add el. Használd a "Spa Decor", "Waiting Room Art", "Therapeutic Nature Photography" kifejezéseket a leírások (P2) bekezdésében.
3.  **A Niche Kötődés (Földrajz és Nosztalgia):**
    *   Az emberek ragaszkodnak ahhoz a helyhez, ahonnan származnak, vagy ahol egy csodálatos nyaralást/nászutat töltöttek.
    *   *Akció:* A "Hardegg", "Cesky Krumlov", "Moravia" kulcsszavak és geolokációk szentek. Ezek nem tömegvonzó szavak, de akik erre keresnek (mert ott nőttek fel, vagy ott volt a nászútjuk), azok *nagyon magas konverzióval* vásárolnak prémium terméket.

## 6. Jövőbeli Fejlesztés: Fine Art America REST API (Automatizált Feltöltés)
A Fine Art America / Pixels rendelkezik egy hivatalos REST API-val, ami a teljes munkafolyamat automatizálásának (feltöltés + metaadat beállítás) végső állomása.

**Amire az FAA API képes:**
1.  **Képfeltöltés (Upload):** Közvetlen, programozott képfeltöltés a szerverre (elkerülve a lassú webes felületet).
2.  **Metaadatok Frissítése (Update):** A Gemini Flash által generált JSON adatok (Title, Description, Tags) egyetlen POST kéréssel történő beküldése.
3.  **Kollekciók (Galleries) Kezelése:** A képek hozzárendelése a "Healing Art" vagy "Romantic Gardens" mappákhoz.

**Az Automata Pipeline Tervezete (Python):**
1.  `gemini_metadata_generator.py` beolvassa a képet, és visszaad egy JSON-t (Cím, 3 bekezdés, Tagek, Kollekció ID).
2.  A Python script Base64/Multipart formátumban felküldi a képet az FAA REST API `upload` végpontjára.
3.  A sikeres feltöltés után (a kapott Image ID-val) a script meghívja a `metadata_update` végpontot, és ráilleszti a Gemini által írt SEO szövegeket.

*Cél:* Egyetlen parancs kiadásával (`python upload_batch.py /path/to/images`) egy teljes mappa feltöltésre kerül, SEO-zva, a megfelelő kollekciókba rendezve.
