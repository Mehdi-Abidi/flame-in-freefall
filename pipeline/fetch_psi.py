"""Download the PSI combustion catalog, investigation metadata and experimental tables.

Usage: python pipeline/fetch_psi.py [--out data/raw]
"""

import argparse
import collections
import json
import os
import time
import urllib.parse
import urllib.request

BASE = "https://psi.nasa.gov/geode-py/ws"
SEARCH = BASE + "/repo/search?data_source=psi&data_type=investigation&size=200&ffield=Research%20Area&fvalue=combustion%20science"
HEADERS = {"User-Agent": "flame-in-freefall-hackathon/0.1"}
DETAIL_FIELDS_TO_DROP = {"added", "removed", "images", "dirty"}


def get(url, as_json=True, retries=3):
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
            return json.loads(body) if as_json else body
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def save_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def file_manifest_summary(accession):
    versions = get(f"{BASE}/repo/investigations/{accession}/versions")
    files = [f for version in versions.get("versions", []) for f in version.get("added", [])]
    by_extension = collections.Counter(os.path.splitext(f["file_name"])[1].lower() or "(none)" for f in files)
    by_folder = collections.Counter(f["remote_path"].split("/")[4] if f["remote_path"].count("/") > 4 else "" for f in files)
    return {
        "file_count": len(files),
        "total_bytes": int(sum(f.get("file_size") or 0 for f in files)),
        "by_extension": dict(by_extension.most_common()),
        "by_folder": dict(by_folder.most_common()),
    }


def download_experimental_tables(accession, detail, out_dir):
    saved = []
    for table in detail.get("experimentalTable") or []:
        file_id = table["_id"]["$oid"]
        version = table.get("version", 1)
        query = urllib.parse.urlencode({"file": file_id, "version": version, "redirect": "false"})
        signed_url = get(f"{BASE}/studies/{accession}/download?{query}", as_json=False).decode().strip()
        content = get(signed_url, as_json=False)
        target = os.path.join(out_dir, "tables", table["file_name"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(content)
        saved.append(table["file_name"])
    return saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/raw")
    args = parser.parse_args()

    catalog = get(SEARCH)
    hits = sorted((hit["_source"] for hit in catalog["hits"]["hits"]), key=lambda s: int(s["Accession"].split("-")[1]))
    save_json(os.path.join(args.out, "catalog.json"), hits)
    print(f"catalog: {len(hits)} combustion investigations")

    index = []
    for source in hits:
        accession = source["Accession"]
        detail = get(f"{BASE}/repo/investigations/{accession}")
        trimmed = {k: v for k, v in detail.items() if k not in DETAIL_FIELDS_TO_DROP}
        save_json(os.path.join(args.out, "investigations", f"{accession}.json"), trimmed)
        manifest = file_manifest_summary(accession)
        tables = download_experimental_tables(accession, detail, args.out)
        index.append({
            "accession": accession,
            "acronym": source.get("Acronym") or "",
            "title": source.get("Title", ""),
            "project_type": source.get("Project Type", ""),
            "sub_research_area": source.get("SubResearch Area", ""),
            "hardware": detail.get("experimentHardware", ""),
            "experimental_tables": tables,
            "files": manifest,
        })
        print(f"{accession:8} {source.get('Acronym') or '-':22} tables={len(tables)} files={manifest['file_count']}")

    save_json(os.path.join(args.out, "index.json"), index)


if __name__ == "__main__":
    main()
