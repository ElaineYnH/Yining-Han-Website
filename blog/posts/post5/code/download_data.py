"""Download official Census files; retain only Philadelphia rows and polygons.

Run from any directory: python path/to/post5/code/download_data.py
No API key is required for the public Census summary-file downloads.
"""

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TABLE_BASE = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/2024/"
    "table-based-SF/data/5YRData/"
)
BOUNDARY_URL = (
    "https://www2.census.gov/geo/tiger/GENZ2024/shp/"
    "cb_2024_42_tract_500k.zip"
)


def response(url):
    return urlopen(Request(url, headers={"User-Agent": "AEDS6400 student project"}), timeout=120)


def save_table(table):
    """Stream the national file; preserve original header and selected rows."""
    url = TABLE_BASE + f"acsdt5y2024-{table}.dat"
    path = RAW / f"acsdt5y2024-{table}-philadelphia.dat"
    with response(url) as src:
        kept = [src.readline()]
        for line in src:
            # 140 = census tract; 050 = county. Philadelphia County FIPS: 42101.
            if line.startswith((b"1400000US42101", b"0500000US42101")):
                kept.append(line)
    if len(kept) != 410:
        raise ValueError(f"Expected 408 tracts plus county; found {len(kept)-1} rows in {table}")
    payload = b"".join(kept)
    path.write_bytes(payload)
    if path.read_bytes() != payload:
        raise IOError(f"Could not save the complete {table} snapshot")
    return {"source_url": url, "local_file": str(path.relative_to(ROOT)), "rows": len(kept)-1}


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    sources = [save_table(t) for t in ("b08201", "b19013")]
    with response(BOUNDARY_URL) as src:
        geometries = gpd.read_file(io.BytesIO(src.read()))
    geometries = geometries.loc[
        geometries["COUNTYFP"].eq("101"), ["GEOID", "NAME", "ALAND", "AWATER", "geometry"]
    ].sort_values("GEOID")
    if len(geometries) != 408 or geometries["GEOID"].duplicated().any():
        raise ValueError("Unexpected or duplicated Philadelphia tract boundaries")
    path = RAW / "philadelphia_tracts_2024.geojson"
    # Original cartographic file: NAD83 / EPSG:4269. GeoJSON: WGS84 / EPSG:4326.
    geometries.to_crs(4326).to_file(path, driver="GeoJSON")
    sources.append({"source_url": BOUNDARY_URL, "local_file": str(path.relative_to(ROOT)), "rows": 408})
    for item in sources:
        item["sha256"] = hashlib.sha256((ROOT / item["local_file"]).read_bytes()).hexdigest()
    manifest = {
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "release": "2024 ACS 5-year estimates (2020–2024), 2024 inflation-adjusted dollars",
        "geography": "Philadelphia County, Pennsylvania; FIPS 42101; 408 census tracts",
        "sources": sources,
        "notes": "DAT rows are unaltered subsets of official Census files. GeoJSON is a county subset and CRS conversion of official cartographic boundaries.",
    }
    (ROOT / "data" / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Downloaded official tables and boundaries. Run code/analyze.py to regenerate the post.")


if __name__ == "__main__":
    main()
