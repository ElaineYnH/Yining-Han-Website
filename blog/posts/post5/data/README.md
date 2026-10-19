# Source snapshots

`raw/acsdt5y2024-b08201-philadelphia.dat` and `raw/acsdt5y2024-b19013-philadelphia.dat` contain unmodified rows and headers from the corresponding official **2024 ACS five-year table-based summary files**, covering 2020–2024. Each includes 408 Philadelphia tracts and one Philadelphia County row. These are public aggregate estimates, not individual records. The pipe separator and Census column names are preserved.

`raw/philadelphia_tracts_2024.geojson` contains the 408 matching 2024 Philadelphia census-tract polygons from the Census Pennsylvania cartographic boundary file, with selected attributes and coordinates converted from EPSG:4269 to EPSG:4326. The boundary file's tract identifiers are joined to the final 11 digits of the ACS `GEO_ID`. The map is projected to EPSG:26918 in the analysis script.

`sources.json` records source URLs, retrieval time and SHA-256 checksums of the retained files. `variables.json` preserves labels for the selected Census API variables; API IDs and summary-file column notation differ, as explained in the main README. `_E001` is an estimate, `_M001` its published 90% margin of error. Negative sentinel codes denote unavailable values and are converted to missing; zero households are not used as a denominator.

The original state ZIP and full national tables are not needed for offline replication and are not bundled. `code/download_data.py` reacquires and subsets them from the public Census download site when requested.
