#!/usr/bin/env python3
"""
PostGIS Bulk Loader for UP Cadastral GeoJSONL
Requirements: ogr2ogr, psql (or psycopg2 for pure-Python alternative)
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd, description):
    """Run a shell command and report status."""
    print(f"\n▶ {description}...")
    print(f"   $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        return False
    print(f"   ✓ Done.")
    return True


def create_database(db_name, user, password=None, host="localhost", port="5432"):
    """Ensure the database exists with PostGIS enabled."""
    env = {"PGPASSWORD": password} if password else None

    check = subprocess.run(
        ["psql", "-h", host, "-p", port, "-U", user, "-d", "postgres",
         "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"],
        capture_output=True, text=True, env=env
    )

    if "1" not in check.stdout:
        print(f"Creating database '{db_name}'...")
        subprocess.run(
            ["createdb", "-h", host, "-p", port, "-U", user, db_name],
            env=env
        )

    run_cmd(
        ["psql", "-h", host, "-p", port, "-U", user, "-d", db_name,
         "-c", "CREATE EXTENSION IF NOT EXISTS postgis;"],
        "Enabling PostGIS extension"
    )


def load_with_ogr2ogr(input_path, db_name, table_name,
                      user="postgres", password=None, host="localhost", port="5432"):
    """Load GeoJSON/GeoJSONL into PostGIS using ogr2ogr."""
    env = {"PGPASSWORD": password} if password else None

    cmd = [
        "ogr2ogr",
        "-f", "PostgreSQL",
        f"PG:host={host} port={port} dbname={db_name} user={user}",
        str(input_path),
        "-nln", table_name,
        "-overwrite",
        "-progress",
        "-lco", "GEOMETRY_NAME=geom",
        "-lco", "FID=id",
        "-lco", "PRECISION=NO",
        "-nlt", "PROMOTE_TO_MULTI",
        "-s_srs", "EPSG:4326",
        "-t_srs", "EPSG:4326"
    ]

    if not run_cmd(cmd, f"Loading {input_path} into {db_name}.{table_name}"):
        return False
    return True


def create_indexes(db_name, table_name, user, password=None, host="localhost", port="5432"):
    """Create spatial and attribute indexes for fast querying."""
    env = {"PGPASSWORD": password} if password else None

    indexes = [
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_geom ON {table_name} USING GIST(geom);",
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_district ON {table_name}((properties->>'district'));",
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_tehsil ON {table_name}((properties->>'tehsil'));",
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_village ON {table_name}((properties->>'village'));",
        f"VACUUM ANALYZE {table_name};"
    ]

    for sql in indexes:
        run_cmd(
            ["psql", "-h", host, "-p", port, "-U", user, "-d", db_name, "-c", sql],
            f"Running: {sql[:50]}..."
        )


def generate_stats(db_name, table_name, user, password=None, host="localhost", port="5432"):
    """Print summary statistics from the loaded table."""
    env = {"PGPASSWORD": password} if password else None

    sql = f"""
    SELECT
        COUNT(*) as total_features,
        COUNT(DISTINCT properties->>'district') as districts,
        COUNT(DISTINCT properties->>'tehsil') as tehsils,
        COUNT(DISTINCT properties->>'village') as villages
    FROM {table_name};
    """

    result = subprocess.run(
        ["psql", "-h", host, "-p", port, "-U", user, "-d", db_name, "-tAc", sql],
        capture_output=True, text=True, env=env
    )

    if result.returncode == 0:
        parts = result.stdout.strip().split("|")
        print("\n📊 Table Statistics:")
        print(f"   Total Features: {parts[0]}")
        print(f"   Districts:      {parts[1]}")
        print(f"   Tehsils:        {parts[2]}")
        print(f"   Villages:       {parts[3]}")


def main():
    parser = argparse.ArgumentParser(description="Load UP Cadastral data into PostGIS")
    parser.add_argument("--input", default="up_cadastral_data/NCOG_UttarPradesh_Cadastrals.geojsonl",
                        help="Input GeoJSONL file")
    parser.add_argument("--db", default="up_cadastral", help="PostgreSQL database name")
    parser.add_argument("--table", default="cadastral_plots", help="Target table name")
    parser.add_argument("--user", default="postgres", help="DB username")
    parser.add_argument("--password", default=None, help="DB password")
    parser.add_argument("--host", default="localhost", help="DB host")
    parser.add_argument("--port", default="5432", help="DB port")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        sys.exit(1)

    create_database(args.db, args.user, args.password, args.host, args.port)

    if load_with_ogr2ogr(input_path, args.db, args.table,
                        args.user, args.password, args.host, args.port):
        create_indexes(args.db, args.table, args.user, args.password, args.host, args.port)
        generate_stats(args.db, args.table, args.user, args.password, args.host, args.port)
        print("\n✅ PostGIS import complete!")
    else:
        print("\n❌ Import failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
