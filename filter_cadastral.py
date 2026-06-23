#!/usr/bin/env python3
"""
Filter UP Cadastral GeoJSONL by district, tehsil, village, or plot number.
Outputs a standard GeoJSON FeatureCollection.
"""
import sys
import json
import argparse
from pathlib import Path


def _normalize(value):
    return str(value).strip().lower() if value is not None else ""


def _plot_value(props):
    """Try common plot-number keys used in BhuNaksha data."""
    for key in ("plot_no", "plotno", "plot", "khasra_no", "khasra", "survey_no", "survey", "gisplotno"):
        if key in props and props[key] is not None:
            return str(props[key])
    return ""


def filter_geojsonl(input_path, output_path, district=None, tehsil=None, village=None, plot=None):
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"❌ File not found: {input_file}")
        sys.exit(1)

    print(f"Filtering {input_file.name}...")
    print(f"  District: {district or 'ALL'}")
    print(f"  Tehsil:   {tehsil or 'ALL'}")
    print(f"  Village:  {village or 'ALL'}")
    print(f"  Plot:     {plot or 'ALL'}")

    district_q = _normalize(district) if district else None
    tehsil_q = _normalize(tehsil) if tehsil else None
    village_q = _normalize(village) if village else None
    plot_q = _normalize(plot) if plot else None

    matched = 0
    total = 0

    with open(input_file, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        fout.write('{"type":"FeatureCollection","features":[\n')

        first = True
        for line in fin:
            total += 1
            line = line.strip()
            if not line:
                continue

            try:
                feature = json.loads(line)
            except json.JSONDecodeError:
                continue

            props = feature.get("properties", {})

            if district_q and district_q not in _normalize(props.get("district", "")):
                continue
            if tehsil_q and tehsil_q not in _normalize(props.get("tehsil", "")):
                continue
            if village_q and village_q not in _normalize(props.get("village", "")):
                continue
            if plot_q and plot_q not in _normalize(_plot_value(props)):
                continue

            matched += 1
            if not first:
                fout.write(",\n")
            fout.write(json.dumps(feature, ensure_ascii=False))
            first = False

            if total % 50000 == 0:
                sys.stdout.write(f"\r  Processed: {total:,} | Matched: {matched:,}")
                sys.stdout.flush()

        fout.write("\n]}\n")

    print(f"\n✓ Done! Matched {matched:,} features out of {total:,}")
    print(f"📁 Output saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Filter UP Cadastral GeoJSONL")
    parser.add_argument("--input", default="up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl", help="Input GeoJSONL file")
    parser.add_argument("--output", required=True, help="Output GeoJSON file")
    parser.add_argument("--district", help="Filter by district name (partial match)")
    parser.add_argument("--tehsil", help="Filter by tehsil name (partial match)")
    parser.add_argument("--village", help="Filter by village name (partial match)")
    parser.add_argument("--plot", help="Filter by plot / khasra / survey number (partial match)")

    args = parser.parse_args()
    filter_geojsonl(args.input, args.output, args.district, args.tehsil, args.village, args.plot)


if __name__ == "__main__":
    main()
