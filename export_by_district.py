#!/usr/bin/env python3
"""
District Bulk Exporter for UP Cadastral GeoJSONL
Streams the file once and outputs one GeoJSON per district.
"""
import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict


def export_by_district(input_path, output_dir, min_features=10):
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"❌ File not found: {input_file}")
        sys.exit(1)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading {input_file.name}...")
    print(f"Output directory: {output_dir.resolve()}\n")

    district_features = defaultdict(list)
    total = 0
    districts_found = set()

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
            district = str(props.get("district", "UNKNOWN")).strip()

            if not district or district.lower() in ("none", "null", "nan"):
                district = "UNKNOWN"

            districts_found.add(district)
            district_features[district].append(feature)

            if total % 100000 == 0:
                sys.stdout.write(
                    f"\r  Processed: {total:,} records | Districts found: {len(districts_found)}"
                )
                sys.stdout.flush()

    print(f"\n  Total records: {total:,}")
    print(f"  Districts found: {len(districts_found)}\n")

    written = 0
    skipped = 0

    for district in sorted(districts_found):
        features = district_features[district]

        if len(features) < min_features:
            skipped += 1
            continue

        safe_name = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in district
        ).lower()
        filename = output_dir / f"{safe_name}_cadastral.geojson"

        geojson = {
            "type": "FeatureCollection",
            "name": district,
            "features": features
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)

        written += 1
        print(f"  ✓ {district:<25} → {filename.name} ({len(features):,} features)")

    summary_file = output_dir / "_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_records": total,
            "districts_found": len(districts_found),
            "districts_written": written,
            "districts_skipped": skipped,
            "min_features_threshold": min_features,
            "districts": {
                d: len(district_features[d])
                for d in sorted(districts_found)
            }
        }, f, indent=2)

    print(f"\n{'─' * 50}")
    print("✅ Export complete!")
    print(f"   Written:   {written} district files")
    print(f"   Skipped:   {skipped} districts (< {min_features} features)")
    print(f"   Summary:   {summary_file}")


def main():
    parser = argparse.ArgumentParser(description="Export UP Cadastral GeoJSONL by district")
    parser.add_argument(
        "--input", default="up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl",
        help="Input GeoJSONL file"
    )
    parser.add_argument(
        "--output", default="up_cadastral_by_district",
        help="Output directory for district files"
    )
    parser.add_argument(
        "--min-features", type=int, default=10,
        help="Skip districts with fewer than N features"
    )

    args = parser.parse_args()
    export_by_district(args.input, args.output, args.min_features)


if __name__ == "__main__":
    main()
