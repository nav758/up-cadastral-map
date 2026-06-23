#!/usr/bin/env python3
"""
Build SQLite search index from UP Cadastral GeoJSONL
for fast district / tehsil / village / plot lookup + zoom-to.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path


def detect_schema_keys(props):
    """Auto-detect common cadastral property keys."""
    keys = {k.lower(): k for k in props.keys()}
    schema = {}

    def pick(candidates):
        for c in candidates:
            if c in keys:
                return keys[c]
        return None

    schema["district"] = pick(["district", "dist", "dt_name", "districtname"])
    schema["tehsil"] = pick(["tehsil", "taluka", "th", "tehsilname", "block"])
    schema["village"] = pick(["village", "vill", "vl", "villagename", "vname"])
    schema["plot"] = pick([
        "plot_no", "plotno", "plot", "khasra_no", "khasra",
        "survey_no", "survey", "gisplotno", "parcel_id"
    ])
    schema["area"] = pick(["area", "area_ac", "areaha", "plotsize"])
    return schema


def _centroid(geom):
    """Return approximate centroid [lon, lat] for Point, Polygon, or MultiPolygon."""
    try:
        gt = geom.get("type")
        coords = geom.get("coordinates", [])
        if gt == "Point":
            return coords[:2]
        if gt == "Polygon":
            ring = coords[0] if coords else []
            n = len(ring)
            return [sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n] if n else [None, None]
        if gt == "MultiPolygon":
            all_pts = [pt for poly in coords for pt in poly[0]]
            n = len(all_pts)
            return [sum(p[0] for p in all_pts) / n, sum(p[1] for p in all_pts) / n] if n else [None, None]
    except Exception:
        pass
    return [None, None]


def build_index(input_path, output_path, limit=None):
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"❌ File not found: {input_file}")
        sys.exit(1)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if output_file.exists():
        output_file.unlink()

    conn = sqlite3.connect(str(output_file))
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE plots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT NOT NULL,
            tehsil TEXT NOT NULL,
            village TEXT NOT NULL,
            plot_no TEXT,
            area TEXT,
            lon REAL,
            lat REAL,
            properties TEXT
        );
        CREATE INDEX idx_district ON plots(district);
        CREATE INDEX idx_tehsil ON plots(tehsil);
        CREATE INDEX idx_village ON plots(village);
        CREATE INDEX idx_plot ON plots(plot_no);
        CREATE INDEX idx_composite ON plots(district, tehsil, village, plot_no);
    """)

    print(f"Reading {input_file.name}...")
    schema = None
    total = 0
    batch = []

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            total += 1
            line = line.strip()
            if not line:
                continue
            try:
                feature = json.loads(line)
            except json.JSONDecodeError:
                continue

            props = feature.get("properties", {})
            geom = feature.get("geometry", {})

            if schema is None:
                schema = detect_schema_keys(props)
                print(f"  Detected schema: {schema}")
                if not schema["district"]:
                    print("⚠️  Could not auto-detect district key. Please inspect first few lines.")

            district = str(props.get(schema.get("district", ""), "")).strip()
            tehsil = str(props.get(schema.get("tehsil", ""), "")).strip()
            village = str(props.get(schema.get("village", ""), "")).strip()
            plot = str(props.get(schema.get("plot", ""), "")).strip()
            area = str(props.get(schema.get("area", ""), "")).strip()
            lon, lat = _centroid(geom)

            batch.append((district, tehsil, village, plot, area, lon, lat, json.dumps(props, ensure_ascii=False)))

            if len(batch) >= 5000:
                cur.executemany(
                    "INSERT INTO plots (district, tehsil, village, plot_no, area, lon, lat, properties) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch
                )
                batch.clear()

            if total % 50000 == 0:
                sys.stdout.write(f"\r  Processed: {total:,}")
                sys.stdout.flush()

            if limit and total >= limit:
                break

    if batch:
        cur.executemany(
            "INSERT INTO plots (district, tehsil, village, plot_no, area, lon, lat, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch
        )

    conn.commit()

    # Summary
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT district), COUNT(DISTINCT tehsil), COUNT(DISTINCT village) FROM plots")
    row = cur.fetchone()
    conn.close()

    print(f"\n✅ Index built: {output_file}")
    print(f"   Plots:    {row[0]:,}")
    print(f"   Districts:{row[1]:,}")
    print(f"   Tehsils:  {row[2]:,}")
    print(f"   Villages: {row[3]:,}")


def main():
    parser = argparse.ArgumentParser(description="Build SQLite search index from UP Cadastral GeoJSONL")
    parser.add_argument("--input", default="up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl", help="Input GeoJSONL")
    parser.add_argument("--output", default="up_cadastral_data/search_index.sqlite", help="Output SQLite file")
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N records (for testing)")

    args = parser.parse_args()
    build_index(args.input, args.output, args.limit)


if __name__ == "__main__":
    main()
