"""Map Steam screenshot filenames to game folders and move them."""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return Path(__file__).resolve().parent


HERE = app_dir()
SETTINGS = HERE / "settings.json"
PREVIEW = HERE / "last_preview.json"

INVALID = str.maketrans({
    "<": "＜",
    ">": "＞",
    ":": "：",
    '"': "＂",
    "/": "／",
    "\\": "＼",
    "|": "｜",
    "?": "？",
    "*": "＊",
})


class SorterError(Exception):
    pass


def load_settings():
    if not SETTINGS.exists():
        return {}
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(updates):
    data = load_settings()
    data.update(updates)
    SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_steam():
    try:
        import winreg
    except ImportError:
        return None
    keys = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    for root, key, value_name in keys:
        try:
            with winreg.OpenKey(root, key) as handle:
                raw, _ = winreg.QueryValueEx(handle, value_name)
        except OSError:
            continue
        folder = normalize_steam(Path(raw))
        if (folder / "appcache" / "appinfo.vdf").exists():
            return folder
    return None


def normalize_steam(folder):
    folder = Path(folder)
    if (folder / "appcache" / "appinfo.vdf").exists():
        return folder
    if folder.name.lower() in {"steamapps", "appcache"} and (folder.parent / "appcache" / "appinfo.vdf").exists():
        return folder.parent
    return folder


def steam_files(steam):
    if not steam:
        return None, None
    root = normalize_steam(Path(steam))
    appinfo = root / "appcache" / "appinfo.vdf"
    library = root / "steamapps" / "libraryfolders.vdf"
    return (appinfo if appinfo.exists() else None), (library if library.exists() else None)


def read_string_table(data, offset):
    count = int.from_bytes(data[offset : offset + 4], "little")
    pos = offset + 4
    strings = []
    for _ in range(count):
        end = data.index(0, pos)
        strings.append(data[pos:end].decode("utf-8", "replace"))
        pos = end + 1
    return strings


def skip_wstring(data, pos, end):
    while pos + 1 < end:
        if data[pos] == 0 and data[pos + 1] == 0:
            return pos + 2
        pos += 2
    raise ValueError("unterminated wstring")


def extract_name(data, pos, end, strings, parent=""):
    """Return the string common/name. Caller jumps to the next app by size."""
    while pos < end:
        kind = data[pos]
        pos += 1
        if kind == 0x08:
            return pos, None
        if pos + 4 > end:
            raise ValueError("truncated key")
        key_i = int.from_bytes(data[pos : pos + 4], "little")
        pos += 4
        key = strings[key_i] if key_i < len(strings) else ""
        if kind == 0x00:
            pos, found = extract_name(data, pos, end, strings, key)
            if found:
                return pos, found
        elif kind == 0x01:
            term = data.index(0, pos, end)
            value = data[pos:term].decode("utf-8", "replace")
            pos = term + 1
            if parent == "common" and key == "name" and value:
                return pos, value
        elif kind in (0x02, 0x03, 0x04, 0x06):
            pos += 4
        elif kind in (0x07, 0x0A):
            pos += 8
        elif kind == 0x05:
            pos = skip_wstring(data, pos, end)
        else:
            raise ValueError(f"unknown vdf type {kind:#x} at {pos}")
    return pos, None


def names_from_appinfo(appinfo, wanted):
    data = Path(appinfo).read_bytes()
    magic = int.from_bytes(data[0:4], "little")
    if magic != 0x07564429:
        raise SorterError("無法讀取 Steam 遊戲清單")
    table_off = int.from_bytes(data[8:16], "little")
    strings = read_string_table(data, table_off)
    found = {}
    pos = 16
    while pos + 8 <= table_off:
        appid = int.from_bytes(data[pos : pos + 4], "little")
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        pos += 8
        if appid == 0 or size < 60 or pos + size > len(data):
            break
        if str(appid) in wanted:
            try:
                _, name = extract_name(data, pos + 60, pos + size, strings)
            except Exception:
                name = None
            if name:
                found[str(appid)] = name
        pos += size
        if len(found) == len(wanted):
            break
    return found


def names_from_manifests(library):
    text = Path(library).read_text(encoding="utf-8", errors="replace")
    apps = {}
    for raw in re.findall(r'"path"\s+"([^"]+)"', text):
        try:
            folder = Path(raw.encode("utf-8").decode("unicode_escape")) / "steamapps"
        except UnicodeDecodeError:
            folder = Path(raw.replace("\\\\", "\\")) / "steamapps"
        if not folder.exists():
            continue
        for acf in folder.glob("appmanifest_*.acf"):
            body = acf.read_text(encoding="utf-8", errors="replace")
            appid = re.search(r'"appid"\s+"(\d+)"', body)
            name = re.search(r'"name"\s+"([^"]*)"', body)
            if appid and name and name.group(1):
                apps[appid.group(1)] = name.group(1)
    return apps


def names_from_store(appids, on_status=None):
    found = {}
    net_errors = 0
    for index, appid in enumerate(appids, 1):
        if on_status:
            on_status(f"正在查詢 Steam 商店 {index}/{len(appids)}")
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic"
        req = urllib.request.Request(url, headers={"User-Agent": "screenshot-sorter"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            block = payload.get(str(appid), {})
            if block.get("success") and block.get("data", {}).get("name"):
                found[str(appid)] = block["data"]["name"]
                net_errors = 0
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            net_errors += 1
            if net_errors >= 3 and not found:
                break
    return found


def sanitize(name, appid):
    cleaned = name.replace(" : ", "：").replace(": ", "：").replace(":", "：")
    cleaned = "".join(c for c in cleaned.translate(INVALID) if ord(c) >= 32)
    cleaned = cleaned.rstrip(" .")
    if len(cleaned) > 120:
        cleaned = cleaned[:120].rstrip(" .")
    return cleaned or str(appid)


def collect_loose(root):
    counts = {}
    for entry in Path(root).iterdir():
        if not entry.is_file():
            continue
        part = entry.name.split("_", 1)[0]
        if part.isdigit():
            counts[part] = counts.get(part, 0) + 1
    return counts


def folder_for(appid, raw_name, taken):
    base = sanitize(raw_name, appid) if raw_name else str(appid)
    key = base.casefold()
    owner = taken.get(key)
    if owner is None or owner == "existing" or owner == appid:
        taken[key] = appid
        return base
    unique = f"{base} ({appid})"
    taken[unique.casefold()] = appid
    return unique


def resolve(root, steam=None, on_status=None):
    root = Path(root)
    if not root.is_dir():
        raise SorterError("找不到外部螢幕截圖資料夾")

    def status(message):
        if on_status:
            on_status(message)

    status("正在掃描")
    counts = collect_loose(root)
    wanted = set(counts)
    names = {}
    appinfo, library = steam_files(steam)
    if appinfo:
        status("正在讀取遊戲名稱")
        names.update(names_from_appinfo(appinfo, wanted))
    if library:
        manifests = names_from_manifests(library)
        for appid in wanted:
            if appid not in names and appid in manifests:
                names[appid] = manifests[appid]
    missing = sorted(wanted - set(names), key=int)
    if missing:
        names.update(names_from_store(missing, on_status))
    unknown = sorted(wanted - set(names), key=int)

    existing = {p.name.casefold(): p.name for p in root.iterdir() if p.is_dir()}
    taken = {name.casefold(): "existing" for name in existing.values()}
    apps = {}
    for appid in sorted(wanted, key=lambda item: (-counts[item], int(item))):
        raw = names.get(appid)
        folder = folder_for(appid, raw, taken)
        if folder.casefold() in existing:
            folder = existing[folder.casefold()]
        apps[appid] = {"name": raw, "folder": folder, "files": counts[appid]}
    return {
        "unknown": unknown,
        "apps": apps,
        "files": sum(counts.values()),
        "used_appinfo": appinfo is not None,
    }


def move_files(root, apps, log_path, on_status=None):
    root = Path(root)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    folders = {}
    for appid, info in apps.items():
        folder = root / info["folder"]
        folder.mkdir(exist_ok=True)
        folders[appid] = folder

    total = sum(info["files"] for info in apps.values())
    moved = skipped = errors = 0
    with log_path.open("w", encoding="utf-8") as log:
        for entry in list(root.iterdir()):
            if not entry.is_file():
                continue
            part = entry.name.split("_", 1)[0]
            if part not in folders:
                continue
            dest = folders[part] / entry.name
            if dest.exists():
                skipped += 1
                log.write(json.dumps({"skip": str(entry), "dest": str(dest)}, ensure_ascii=False) + "\n")
                continue
            try:
                entry.rename(dest)
                moved += 1
                if on_status and (moved % 200 == 0 or moved == total):
                    on_status(f"已移動 {moved} / {total}")
                log.write(json.dumps({"src": str(entry), "dest": str(dest)}, ensure_ascii=False) + "\n")
            except OSError as exc:
                errors += 1
                log.write(json.dumps({"error": str(entry), "msg": str(exc)}, ensure_ascii=False) + "\n")
    return {"moved": moved, "skipped": skipped, "errors": errors, "log": str(log_path), "total": total}


def new_log_path():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return HERE / "logs" / f"move-{stamp}.jsonl"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        from gui import run

        run()
        return 0

    parser = argparse.ArgumentParser(description="Steam 截圖整理工具")
    parser.add_argument("--root", help="外部螢幕截圖資料夾")
    parser.add_argument("--steam", help="Steam 目錄")
    parser.add_argument("--move", action="store_true", help="移動檔案")
    args = parser.parse_args(argv)

    settings = load_settings()
    root = args.root or settings.get("screenshots") or r"D:\SteamScreenshots"
    steam = args.steam or settings.get("steam") or detect_steam()
    result = resolve(root, steam, on_status=print)
    PREVIEW.write_text(
        json.dumps({"unknown": result["unknown"], "apps": result["apps"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"games {len(result['apps'])} files {result['files']} unknown {len(result['unknown'])}")
    print(f"preview {PREVIEW}")
    if not args.move:
        return 0
    if result["files"] == 0:
        print("nothing to move")
        return 0
    outcome = move_files(root, result["apps"], new_log_path(), on_status=print)
    print(f"moved {outcome['moved']} skipped {outcome['skipped']} errors {outcome['errors']}")
    print(f"log {outcome['log']}")
    return 0 if outcome["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
