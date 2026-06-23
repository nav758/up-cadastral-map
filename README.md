# UP BhuNaksha Cadastral Map Viewer & Search Toolkit

> **Knowledge Transfer Document** — A complete guide to understanding, running, and extending the UP BhuNaksha (Land Record / Cadastral Map) scraping, indexing, and visualization toolkit.

---

## 1. Project Overview

This project provides a set of Python scripts and HTML maps to **download, filter, index, and visualize** Uttar Pradesh cadastral (plot-level) land maps from the official **BhuNaksha** portal (`upbhunaksha.gov.in`).

### What is BhuNaksha?
- **BhuNaksha** is India's official cadastral mapping system developed by **NIC** (National Informatics Centre).
- It stores digitized plots (Khasra boundaries) linked to Records of Rights (RoR) data.
- UP BhuNaksha covers **~95,000 villages** across 75 districts.

### Why this toolkit exists
The official portal does **not** expose raw GeoServer APIs or bulk download options. This toolkit bridges that gap by:
1. Consuming pre-scraped NCOG cadastral vector tiles
2. Building local SQLite/GeoJSON indexes for offline search
3. Providing standalone web maps with zero backend dependencies

---

## 2. Architecture & Tech Stack

### Backend / Data Layer
| Technology | Role |
|-----------|------|
| **NCOG (National Center of Geo-informatics)** | Original source of scraped cadastral vector data |
| **GeoJSON Lines** (`.geojsonl`) | Raw plot-level geometry + attributes (one feature per line) |
| **Mapbox Vector Tiles (PBF)** | Cloud-hosted tiles served from `indianopenmaps.com` |
| **SQLite / PostGIS** | Local search indexes built from GeoJSONL |

### Frontend Map Layer
| Technology | Role |
|-----------|------|
| **OpenLayers 9.1.0** | JavaScript map engine (rendering, zoom, pan, tile loading) |
| **MVT (Mapbox Vector Tile) Parser** | Decodes `.pbf` tiles into renderable vector geometries |
| **Nominatim (OpenStreetMap)** | Free geocoding API for district → lat/lon lookup |

### Python Toolkit
| Library | Purpose |
|---------|---------|
| `py7zr` | Extract 7z-compressed GeoJSONL archives |
| `sqlite3` (stdlib) | Build local plot-level search indexes |
| `json` (stdlib) | Stream-parse GeoJSONL files without loading into RAM |
| `subprocess` (stdlib) | Call `ogr2ogr` and `psql` for PostGIS bulk loading |
| `ogr2ogr` / `psql` | GDAL/Postgres CLI tools for spatial data import |

---

## 3. File-by-File Explanation

### `download_up_cadastral.py`
**Purpose:** Downloads the pre-scraped UP cadastral dataset from GitHub.

**What it does:**
- Downloads `NCOG_UttarPradesh_Cadastrals.geojsonl.7z` from the `ramSeraph/indian_cadastrals` release
- Shows real-time download progress (MB downloaded)
- Auto-installs `py7zr` if missing
- Extracts the archive to `./up_cadastral_data/`

**Key function:**
```python
def download()
    # 1. Downloads from GitHub release URL
    # 2. Extracts using py7zr.SevenZipFile
    # 3. Returns path to extracted .geojsonl
```

**Output:** `up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl`

---

### `filter_cadastral.py`
**Purpose:** Streams the massive GeoJSONL file and extracts only matching plots.

**Why streaming?**
The raw file can be **500 MB – 2 GB**. Loading it into memory would crash most machines. This script reads **one line at a time** (each line is one GeoJSON Feature).

**Logic:**
```python
for line in open(file):           # 1 line = 1 plot
    feature = json.loads(line)
    props = feature["properties"]
    
    # Check match (case-insensitive partial match)
    if district and district not in props["district"]: continue
    if tehsil  and tehsil  not in props["tehsil"]:  continue
    if village and village not in props["village"]: continue
    
    # Plot search tries multiple common key names:
    plot_val = props.get("plot_no") or props.get("plotno") \
               or props.get("khasra_no") or props.get("survey_no")
```

**Usage:**
```bash
python filter_cadastral.py \
  --output agra_etmadpur.geojson \
  --district "agra" \
  --tehsil "etmadpur" \
  --village "akbarpur" \
  --plot "123"
```

**Output:** Standard GeoJSON `FeatureCollection`

---

### `build_search_index.py`
**Purpose:** Creates a searchable SQLite database from GeoJSONL for instant plot lookup.

**Why SQLite?**
- GeoJSONL is **read-only sequential** — terrible for random search
- SQLite lets you `SELECT` by district/tehsil/village/plot in milliseconds
- Can be loaded in the browser via `sql.js` (WebAssembly SQLite)

**Auto-detected schema keys:**
The script reads the **first 100 features** and uses fuzzy matching to find:
- `district` / `dist` / `districtname`
- `tehsil` / `taluka` / `tehsilname`
- `village` / `vill` / `villagename`
- `plot_no` / `khasra_no` / `survey_no` / `gisplotno`

**Tables created:**
```sql
CREATE TABLE plots (
    id INTEGER PRIMARY KEY,
    district TEXT,
    tehsil TEXT,
    village TEXT,
    plot_no TEXT,
    area TEXT,
    lon REAL,
    lat REAL,
    properties TEXT
);
CREATE INDEX idx_composite ON plots(district, tehsil, village, plot_no);
```

**Centroid computation:**
Each plot's polygon geometry is analyzed and its center point (`lon`, `lat`) is pre-computed so the map can zoom directly to it.

**Output:** `search_index.sqlite`

---

### `export_by_district.py`
**Purpose:** Splits the monolithic GeoJSONL into one file per district.

**Algorithm:**
```python
# One-pass streaming read
district_features = defaultdict(list)

for line in geojsonl_file:
    feature = json.loads(line)
    district = feature["properties"]["district"]
    district_features[district].append(feature)
```

**Why use this?**
- QGIS handles smaller files faster
- Each district file is ~5-50 MB instead of 1 GB
- Enables per-district analysis and sharing

**Output structure:**
```
districts/
├── agra_cadastral.geojson
├── aligarh_cadastral.geojson
├── jhansi_cadastral.geojson
├── _summary.json
└── ...
```

---

### `load_to_postgis.py`
**Purpose:** One-command bulk import into PostgreSQL/PostGIS.

**Pipeline:**
```
GeoJSONL ──► ogr2ogr ──► PostgreSQL/PostGIS
```

**Key steps:**
1. Creates database if missing
2. Enables `postgis` extension
3. Runs `ogr2ogr` with:
   - `PROMOTE_TO_MULTI` (handles mixed polygon types)
   - `GEOMETRY_NAME=geom` (standard PostGIS geometry column)
   - `EPSG:4326` → `EPSG:4326` (WGS84)
4. Creates GIST spatial index + attribute indexes
5. Runs `VACUUM ANALYZE` for query optimization

**Indexes created:**
```sql
CREATE INDEX idx_geom ON plots USING GIST(geom);
CREATE INDEX idx_district ON plots((properties->>'district'));
CREATE INDEX idx_tehsil   ON plots((properties->>'tehsil'));
CREATE INDEX idx_village  ON plots((properties->>'village'));
```

---

### `load_to_qgis.py`
**Purpose:** Loads a GeoJSON into QGIS with BhuNaksha styling.

**How to use:**
1. Open QGIS → Python Console
2. Paste:
```python
exec(open('/path/to/load_to_qgis.py').read())
```

**What it does:**
- Creates a `QgsVectorLayer` from the GeoJSON file
- Applies styling: semi-transparent blue fill (`rgba(66,153,225,0.15)`), blue outline (`#2b6cb0`)
- Adds layer to current project
- Zooms canvas to layer extent

---

### `map.html`
**Purpose:** Minimal standalone PBF tile viewer.

**Stack:** HTML + OpenLayers (CDN)

**Layers:**
```javascript
// Layer 1: Faded OSM base map
new ol.layer.Tile({ source: new ol.source.OSM(), opacity: 0.4 })

// Layer 2: Cadastral PBF vector tiles
new ol.layer.VectorTile({
    source: new ol.source.VectorTile({
        format: new ol.format.MVT(),
        url: 'https://indianopenmaps.com/.../{z}/{x}/{y}.pbf'
    }),
    style: semi-transparent blue fill + outline
})
```

**Interactive features:**
- Click any plot → popup with full JSON properties

---

### `map_search.html`
**Purpose:** Full-featured search map with zero backend dependencies.

#### Two-Stage Search Architecture

**Stage 1 — District Geocoding (Nominatim)**
Since villages are not in OpenStreetMap, we use Nominatim only to find the **district** center:
```javascript
const result = await nominatimSearch("Jhansi, Uttar Pradesh, India");
// Returns: lon/lat + bounding box of Jhansi district
map.getView().animate({ center: [lon, lat], zoom: 12 });
```

**Stage 2 — Village/Plot Scanning (`getFeaturesInExtent`)**
After tiles load, we directly scan the **PBF vector features** that OpenLayers has already decoded into memory:

```javascript
// 1. Get every feature currently visible in the viewport
const allFeatures = cadastralSource.getFeaturesInExtent(viewportExtent);

// 2. Filter by village name (case-insensitive)
const villageFeatures = allFeatures.filter(f => 
    f.get('village').toLowerCase() === 'pali pahari'
);

// 3. Further filter by Khasra number
const plotFeatures = villageFeatures.filter(f => 
    f.get('khasra') === '453'
);
```

#### How Highlighting Works

**Step 1: Find bounding box**
```javascript
function computeExtent(features) {
    const ext = ol.extent.createEmpty();
    features.forEach(f => {
        const geom = f.getGeometry();
        if (geom) ol.extent.extend(ext, geom.getExtent());
    });
    return ext;
}
```

**Step 2: Animate zoom to the plot**
```javascript
map.getView().fit(plotExtent, { 
    padding: [120, 120, 120, 120],  // breathing room
    duration: 800                    // smooth animation
});
```

**Step 3: Clone and draw red overlay**
```javascript
function highlightFeatures(features) {
    highlightSource.clear();            // wipe previous highlight
    features.forEach(f => {
        const clone = f.clone();        // create independent copy
        highlightSource.addFeature(clone);
    });
}
```

Why `clone()`? The original features are **managed by OpenLayers' tile cache**. Modifying them directly would corrupt tile rendering. Cloning creates a safe copy for the overlay layer.

**Highlight styling:**
```javascript
const highlightLayer = new ol.layer.Vector({
    source: highlightSource,
    style: new ol.style.Style({
        fill: new ol.style.Fill({ color: 'rgba(255, 99, 71, 0.45)' }),  // red fill
        stroke: new ol.style.Stroke({ color: '#c53030', width: 2.5 })   // red border
    })
});
```

#### Rendering Order (Z-Index)
```
Top    → highlightLayer  (red overlay on matched plots)
Middle → cadastralLayer  (blue PBF tiles)
Bottom → osmLayer        (faded OpenStreetMap base)
```

---

## 4. Data Sources & Attribution

| Source | URL | License |
|--------|-----|---------|
| **UP Cadastral Data** | `indianopenmaps.com` (via NCOG) | CC0 1.0 |
| **BhuNaksha Official** | `upbhunaksha.gov.in` | Government of India |
| **OpenStreetMap Tiles** | `tile.openstreetmap.org` | ODbL |
| **Nominatim Geocoding** | `nominatim.openstreetmap.org` | ODbL |

---

## 5. Prerequisites

### System Requirements
- **OS:** Linux, macOS, or Windows with WSL
- **RAM:** 4 GB minimum (8 GB recommended for building SQLite index)
- **Disk:** 5 GB free (raw 7z extract ~1-2 GB)

### Required Software
```bash
# Python 3.9+
python3 --version

# py7zr (auto-installed by download script, or manually)
pip install py7zr

# Optional: GDAL/PostGIS stack (only for PostGIS loading)
# Ubuntu/Debian:
sudo apt-get install gdal-bin postgresql postgis
```

### Browser
Any modern browser with WebGL support (Chrome, Firefox, Edge, Safari).

---

## 6. Quick Start Guide

### Step 1: Download the data
```bash
python download_up_cadastral.py
# Output: up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl
```

### Step 2A: View the live search map (no download needed)
```bash
cd /path/to/project
python3 -m http.server 8080
# Open: http://localhost:8080/map_search.html
```

### Step 2B: Build local SQLite index (for offline plot search)
```bash
python build_search_index.py \
  --input up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl \
  --output up_cadastral_data/search_index.sqlite
```

### Step 3: Filter a specific area
```bash
python filter_cadastral.py \
  --input up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl \
  --output jhansi_pali_pahari.geojson \
  --district "jhansi" \
  --village "pali pahari" \
  --plot "453"
```

### Step 4: Import to PostGIS (optional)
```bash
python load_to_postgis.py \
  --input up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl \
  --db up_cadastral \
  --table plots
```

---

## 7. How the Map Renders Tiles

### MVT (Mapbox Vector Tile) Flow
```
1. OpenLayers requests tile URL:
   https://.../ncog/{z}/{x}/{y}.pbf
   
2. Server returns binary PBF (Protocol Buffer Format)

3. ol/format/MVT decodes PBF → array of ol.Feature objects

4. Features stored in VectorTileSource tile cache

5. VectorTileLayer renders visible features with style function
```

### Tile Pyramid (Zoom Levels)
| Zoom | Approx Area per Tile | Detail |
|------|---------------------|--------|
| 8-10 | ~50 km² | District-level overview |
| 12-14 | ~5 km² | Tehsil-level, parcels visible |
| 16-18 | ~0.1 km² | Village-level, individual plots clear |

---

## 8. Troubleshooting

### "Location not found" in map_search.html
- **Cause:** Village not in OpenStreetMap
- **Fix:** The new two-stage search automatically falls back to tile scanning. If still failing, the village may be outside the 34-district coverage.

### "Tile scanning not supported"
- **Cause:** Old OpenLayers version
- **Fix:** The CDN link uses OL 9.1.0 which fully supports `getFeaturesInExtent()`.

### No plots visible
- **Cause:** PBF tile server may be slow or blocked
- **Fix:** Check browser DevTools Network tab for 404/timeout on `.pbf` requests

### Plot not found after village zoom
- **Cause:** The property key might vary (`khasra` vs `plot_no` vs `survey_no`)
- **Fix:** Click any visible plot first to inspect its JSON properties and confirm the correct key name

### QGIS script fails
- **Cause:** Running outside QGIS
- **Fix:** Open QGIS → Plugins → Python Console → paste script

---

## 9. Extending the Project

### Add a new state
1. Find the state's GitHub release in `ramSeraph/indian_cadastrals`
2. Update `download_up_cadastral.py` with the new release URL
3. Update `map_search.html` PBF URL pattern

### Add plot labels on map
```javascript
// In the VectorTileLayer style, add:
new ol.style.Text({
    text: feature.get('khasra'),
    font: '10px sans-serif',
    fill: new ol.style.Fill({ color: '#000' })
})
```

### Export to shapefile
```bash
ogr2ogr -f "ESRI Shapefile" output.shp input.geojson
```

---

## 10. Credits & License

- **Data scraping:** `ramSeraph` / Indian Open Maps (`indianopenmaps.com`)
- **Original source:** NCOG (National Center of Geo-informatics), Government of India
- **Toolkit author:** Kimchi AI Code Assistant
- **License:** CC0 1.0 for cadastral data; ODbL for OpenStreetMap layers

---

*Last updated: 2024-06-23*
