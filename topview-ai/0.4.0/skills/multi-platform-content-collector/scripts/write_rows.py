#!/usr/bin/env python3
"""逐行写入飞书表格，支持重试和断点续写"""
import subprocess
import json
import time
import tempfile
import os
import sys

MAX_RETRIES = 3
RETRY_DELAY = 2

def append_row(sheet_url, sheet_id, row, retries=MAX_RETRIES):
    data_json = json.dumps([row], ensure_ascii=False)

    for attempt in range(1, retries + 1):
        if len(data_json) > 50000:
            fd, tmp = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data_json)
            cmd = f'lark-cli sheets +append --as user --url "{sheet_url}" --sheet-id "{sheet_id}" --values "$(cat {tmp})"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            os.unlink(tmp)
        else:
            cmd = [
                "lark-cli", "sheets", "+append",
                "--as", "user", "--url", sheet_url,
                "--sheet-id", sheet_id, "--values", data_json,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return True

        if attempt < retries:
            print(f"  Retry {attempt}/{retries} after error: {result.stderr.strip()}")
            time.sleep(RETRY_DELAY * attempt)
        else:
            print(f"  FAILED after {retries} attempts: {result.stderr.strip()}")
            return False

    return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 write_rows.py <sheet_url> <sheet_id> <rows_json_file> [start_index]")
        sys.exit(1)

    SHEET_URL = sys.argv[1]
    SHEET_ID = sys.argv[2]
    ROWS_FILE = sys.argv[3]
    START_INDEX = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    with open(ROWS_FILE, 'r', encoding='utf-8') as f:
        rows = json.load(f)

    if START_INDEX > 0:
        print(f"Resuming from row {START_INDEX + 1}")

    success = 0
    failed = []

    for i, row in enumerate(rows):
        if i < START_INDEX:
            continue
        last_cell_len = len(str(row[-1])) if row else 0
        print(f"[{i+1}/{len(rows)}] Writing: {row[0]} | {row[1]} | last cell {last_cell_len} chars")
        if append_row(SHEET_URL, SHEET_ID, row):
            success += 1
        else:
            failed.append(i)
        time.sleep(0.5)

    print(f"\nDone! {success}/{len(rows)} rows written successfully.")
    if failed:
        print(f"Failed rows (0-indexed): {failed}")
        print(f"To retry: python3 write_rows.py '{SHEET_URL}' '{SHEET_ID}' '{ROWS_FILE}' {failed[0]}")
