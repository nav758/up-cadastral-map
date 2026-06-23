#!/usr/bin/env python3
"""
Download and extract UP Cadastral data from ramSeraph/indian_cadastrals
"""
import os
import sys
import urllib.request
from pathlib import Path

RELEASE_URL = (
    "https://github.com/ramSeraph/indian_cadastrals/releases/download/"
    "uttar-pradesh/NCOG_UttarPradesh_Cadastrals.geojsonl.7z"
)
OUTPUT_DIR = Path("up_cadastral_data")
ARCHIVE_NAME = "NCOG_UttarPradesh_Cadastrals.geojsonl.7z"


class ProgressHook:
    def __init__(self):
        self.downloaded = 0

    def __call__(self, block_num, block_size, total_size):
        self.downloaded += block_size
        percent = min(self.downloaded * 100 / total_size, 100)
        sys.stdout.write(
            f"\r  ↓ Downloading: {percent:.1f}% "
            f"({self.downloaded // 1024 // 1024} MB / {total_size // 1024 // 1024} MB)"
        )
        sys.stdout.flush()


def download():
    OUTPUT_DIR.mkdir(exist_ok=True)
    archive_path = OUTPUT_DIR / ARCHIVE_NAME

    if archive_path.exists():
        print(f"✓ Archive already exists: {archive_path}")
    else:
        print("Starting download...")
        urllib.request.urlretrieve(RELEASE_URL, archive_path, ProgressHook())
        print("\n✓ Download complete.")

    extract_path = OUTPUT_DIR / "NCOG_UttarPradesh_Cadastrals.geojsonl"
    if extract_path.exists():
        print(f"✓ Already extracted: {extract_path}")
        return str(extract_path)

    print("Extracting 7z archive...")
    try:
        import py7zr
    except ImportError:
        print("\n⚠️  py7zr not installed. Installing...")
        os.system(f"{sys.executable} -m pip install py7zr -q")
        import py7zr

    with py7zr.SevenZipFile(archive_path, mode="r") as sz:
        sz.extractall(path=OUTPUT_DIR)
    print(f"✓ Extracted to: {extract_path}")
    return str(extract_path)


if __name__ == "__main__":
    file_path = download()
    print(f"\n📁 Data ready at: {file_path}")
