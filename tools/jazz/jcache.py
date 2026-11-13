"""Запись общих кэшей (Discogs и др.), когда прогонов несколько.

Прогон 25.10.2026: калибровка и проход по лейблам писали один и тот же
cache/discogs_catno.json через один «.tmp» — второй os.replace не нашёл
файла, и проход упал на 325-м лоте из 600 вместе с находкой. Кроме того,
каждый процесс затирал записи другого своими. Здесь: замок на время
записи, слияние с тем, что уже на диске (свежие записи процесса главнее),
свой временный файл у каждого процесса.
"""
import fcntl
import json
import os


def save_merged(path, db):
    """Слить db с файлом path и записать атомарно; db пополняется
    записями с диска (другие прогоны)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            with open(path, encoding="utf-8") as f:
                disk = json.load(f)
        except (OSError, ValueError):
            disk = {}
        if isinstance(disk, dict):
            for k, v in disk.items():
                db.setdefault(k, v)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False)
        os.replace(tmp, path)
