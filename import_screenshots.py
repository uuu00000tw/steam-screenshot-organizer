"""Import pictures into a Steam screenshots folder.

This follows Steam Screenshots Manager 1.1: each picture becomes a JPEG,
plus a second file named "<name>_vr.jpg". A picture whose _vr.jpg is already
present is left alone.
"""
import shutil
from pathlib import Path

from PIL import Image

from sort_screenshots import SorterError

IMAGE_EXTS = {".bmp", ".jpeg", ".jpg", ".png"}


def _images(folder):
    found = []
    for entry in Path(folder).iterdir():
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTS and not entry.stem.lower().endswith("_vr"):
            found.append(entry)
    return found


def _groups(folder):
    groups = {}
    for path in _images(folder):
        groups.setdefault(path.stem, []).append(path)
    return groups


def _write_jpeg(src, dest):
    with Image.open(src) as image:
        if image.mode in {"RGBA", "LA", "P"}:
            rgba = image.convert("RGBA")
            flat = Image.new("RGB", rgba.size, (0, 0, 0))
            flat.paste(rgba, mask=rgba.getchannel("A"))
            image = flat
        elif image.mode != "RGB":
            image = image.convert("RGB")
        image.save(dest, "JPEG", quality=90)


def _check_dirs(source, dest):
    source = Path(source)
    dest = Path(dest)
    if not source.is_dir():
        raise SorterError("Image source was not found.")
    if not dest.is_dir():
        raise SorterError("Game screenshots folder was not found.")
    return source, dest, source.resolve() == dest.resolve()


def preview_import(source, dest):
    source, dest, same = _check_dirs(source, dest)
    rows = []
    pending = skipped = 0
    for stem, paths in _groups(source).items():
        status = "skip" if (dest / f"{stem}_vr.jpg").exists() else "import"
        if status == "skip":
            skipped += len(paths)
        else:
            pending += len(paths)
        for path in paths:
            rows.append({"name": path.name, "status": status})
    return {"pending": pending, "skipped": skipped, "same_folder": same, "rows": rows}


def import_images(source, dest, on_status=None):
    source, dest, same = _check_dirs(source, dest)
    groups = [
        (stem, paths)
        for stem, paths in _groups(source).items()
        if not (dest / f"{stem}_vr.jpg").exists()
    ]
    skipped = sum(len(paths) for paths in _groups(source).values()) - sum(len(paths) for _stem, paths in groups)
    made = errors = 0
    total = len(groups)
    done = 0
    for stem, paths in groups:
        done += 1
        if on_status:
            on_status(f"Importing {done}/{total}")
        jpg_path = dest / f"{stem}.jpg"
        vr_path = dest / f"{stem}_vr.jpg"
        master = next((path for path in paths if path.suffix.lower() in {".jpg", ".jpeg"}), paths[0])
        try:
            if master.suffix.lower() in {".jpg", ".jpeg"}:
                source_jpg = master
                if master.resolve() != jpg_path.resolve() and not jpg_path.exists():
                    shutil.copy2(master, jpg_path)
                    source_jpg = jpg_path
                shutil.copy2(source_jpg, vr_path)
            else:
                _write_jpeg(master, jpg_path)
                shutil.copy2(jpg_path, vr_path)
            if same:
                for path in paths:
                    if path.suffix.lower() not in {".jpg", ".jpeg"} and path.exists() and path.resolve() != jpg_path.resolve():
                        path.unlink()
            made += len(paths)
        except OSError:
            errors += len(paths)
    return {"made": made, "skipped": skipped, "errors": errors, "total": total, "same_folder": same}
