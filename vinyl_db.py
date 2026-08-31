#!/usr/bin/env python3
"""
vinyl_db.py — P1-7 из ТЗ v2: SQLite вместо CSV + полный жизненный цикл сделки.

ЗАЧЕМ (проблема, которую решает):
decisions_log.csv дедупит по listing_url и потому ломается на РЕЛИСТИНГАХ —
продавец снял лот и выставил заново с новым URL, и это записывается как новый
лот, хотя пластинка та же. Считать по такому логу конверсию, срок оборота или
инфляцию грейда по продавцам невозможно в принципе. Без этой таблицы
калибровка (P2-8) не имеет входных данных.

ЧТО НЕ ДЕЛАЕТ: не заменяет candidates_<дата>.csv (тот остаётся снимком
конкретного прогона, удобно смотреть глазами) и не переписывает
decisions_log.csv задним числом — старый CSV импортируется один раз
(import_decisions_log_csv), дальше пишется и туда, и в базу, пока не решим
отключить CSV.

Жизненный цикл сделки (P1-7):
    seen -> bid -> won | lost -> shipped -> received -> graded -> listed -> sold | unsold
Переходы не форсируются жёстким конечным автоматом (реальность грязнее: лот
можно получить без ставки, «купить сейчас»), но нелегальный статус отвергается.
"""
import csv
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "vinyl.db"

DEAL_STATUSES = [
    "seen", "bid", "won", "lost", "shipped",
    "received", "graded", "listed", "sold", "unsold",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    mode          TEXT,              -- mode1 / mode2 / mode3_auction / mode3_bin / golden
    config_json   TEXT,              -- снимок порогов, чтобы вердикт был воспроизводим
    n_queries     INTEGER DEFAULT 0,
    n_items_seen  INTEGER DEFAULT 0,
    n_candidates  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS releases (
    release_id      INTEGER PRIMARY KEY,   -- Discogs release id
    artist          TEXT,
    title           TEXT,
    catno           TEXT,
    country         TEXT,
    year            TEXT,
    label           TEXT,
    format_json     TEXT,
    have_count      INTEGER,
    want_count      INTEGER,
    world_low       REAL,
    world_median    REAL,
    world_high      REAL,
    pricing_source  TEXT,
    updated_at      TEXT NOT NULL
);

-- Ключ items — НЕ url (он меняется при релистинге), а ebay_item_id.
-- Плюс fingerprint (продавец+нормализованный заголовок) ловит релистинг
-- с новым item_id: тот же продавец, та же пластинка, новый номер лота.
CREATE TABLE IF NOT EXISTS items (
    ebay_item_id    TEXT PRIMARY KEY,
    fingerprint     TEXT,
    listing_url     TEXT,
    title           TEXT,
    seller          TEXT,
    price_usd       REAL,
    shipping_usd    REAL,
    item_end_date   TEXT,
    buying_options  TEXT,
    release_id      INTEGER REFERENCES releases(release_id),
    first_seen_at   TEXT NOT NULL,
    last_seen_at    TEXT NOT NULL,
    times_seen      INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_items_fingerprint ON items(fingerprint);
CREATE INDEX IF NOT EXISTS idx_items_seller      ON items(seller);

-- Вердикт отдельной таблицей: один и тот же лот оценивается заново в каждом
-- прогоне (цена аукциона растёт, курс меняется) — история оценок нужна, чтобы
-- потом сверить «что скрипт думал тогда» с фактическим исходом (P2-8 бэктест).
CREATE TABLE IF NOT EXISTS verdicts (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                 INTEGER REFERENCES runs(id),
    ebay_item_id           TEXT REFERENCES items(ebay_item_id),
    created_at             TEXT NOT NULL,
    verdict                TEXT,
    margin_world           REAL,
    margin_ru              REAL,
    landed_standalone_usd  REAL,
    landed_marginal_usd    REAL,
    weight_kg              REAL,
    weight_estimated       INTEGER,
    resolution_confidence  TEXT,
    candidate_count        INTEGER,
    pricing_source         TEXT,
    expected_profit_rub    REAL,
    p_sale_90d             REAL,
    notes                  TEXT
);
CREATE INDEX IF NOT EXISTS idx_verdicts_item ON verdicts(ebay_item_id);

-- Российские компы (P0-1). Отдельная таблица с TTL: цены РФ-рынка не
-- меняются за ночь, а запросов к сайтам должно быть как можно меньше.
CREATE TABLE IF NOT EXISTS ru_comps (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id          INTEGER REFERENCES releases(release_id),
    fetched_at          TEXT NOT NULL,
    ru_ask_median_rub   REAL,
    ru_ask_n            INTEGER,
    ru_supply_count     INTEGER,
    ru_sold_median_rub  REAL,
    ru_sold_n           INTEGER,
    ru_sold_last_date   TEXT,
    ru_price_source     TEXT,   -- meshok_sold | marketvinila_ask | segment_model | none
    ru_confidence       TEXT,   -- high | medium | low | none
    raw_json            TEXT
);
CREATE INDEX IF NOT EXISTS idx_ru_comps_release ON ru_comps(release_id, fetched_at);

CREATE TABLE IF NOT EXISTS deals (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ebay_item_id          TEXT REFERENCES items(ebay_item_id),
    release_id            INTEGER REFERENCES releases(release_id),
    status                TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    max_bid_usd           REAL,
    bought_price_usd      REAL,
    actual_shipping_usd   REAL,
    actual_weight_kg      REAL,
    final_price_usd       REAL,   -- за сколько ушёл лот (в т.ч. ПРОИГРАННЫЙ):
                                  -- показывает реальную конкуренцию и потолок рынка
                                  -- по сегменту. Раньше эта информация терялась
                                  -- полностью, а она бесплатная.
    promised_grade        TEXT,
    actual_grade          TEXT,   -- для инфляции грейда по продавцам (P2-8)
    listed_price_rub      REAL,
    sold_price_rub        REAL,
    sold_date             TEXT,
    days_to_sale          INTEGER,
    notes                 TEXT
);
CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status);

-- P1-4 через очередь ручного разбора (vision_queue.py). Поколение пресса,
-- прочитанное с фото — то, что снимает главный потолок точности: при
-- коллизии catno скрипт вместо понижения доверия делает выбор.
CREATE TABLE IF NOT EXISTS press_ids (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ebay_item_id      TEXT REFERENCES items(ebay_item_id),
    created_at        TEXT NOT NULL,
    press_generation  TEXT,   -- original | early_repress | later_repress | unknown
    press_confidence  TEXT,   -- high | medium | low
    catno_on_label    TEXT,
    rim_text          TEXT,
    deep_groove       INTEGER,
    runout            TEXT,
    mono_stereo       TEXT,
    condition_notes   TEXT,
    press_evidence    TEXT,   -- JSON-массив наблюдений
    chosen_release_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_press_ids_item ON press_ids(ebay_item_id);

CREATE TABLE IF NOT EXISTS deal_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id     INTEGER REFERENCES deals(id),
    at          TEXT NOT NULL,
    status      TEXT NOT NULL,
    payload     TEXT
);
"""


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=None):
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
    return db_path or DB_PATH


def make_fingerprint(seller, title):
    """Ловит релистинг: тот же продавец + то же (грубо нормализованное)
    название = та же пластинка, даже если ebay_item_id новый. Намеренно
    грубо: убираем всё, кроме букв/цифр, и режем до 60 символов — продавцы
    при релистинге правят пунктуацию и хвосты вроде 'NEW LISTING'."""
    import re
    t = re.sub(r"[^a-z0-9]+", "", (title or "").lower())[:60]
    return f"{(seller or '').lower()}|{t}"


def upsert_release(conn, release_id, **fields):
    fields = {k: v for k, v in fields.items() if v is not None}
    if isinstance(fields.get("format_json"), (list, dict)):
        fields["format_json"] = json.dumps(fields["format_json"], ensure_ascii=False)
    fields["updated_at"] = utcnow()
    cols = ["release_id"] + list(fields)
    vals = [release_id] + list(fields.values())
    updates = ", ".join(f"{c}=excluded.{c}" for c in fields)
    conn.execute(
        f"INSERT INTO releases ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
        f"ON CONFLICT(release_id) DO UPDATE SET {updates}",
        vals,
    )


def upsert_item(conn, ebay_item_id, **fields):
    """Возвращает True, если лот виден впервые (для отчёта 'новых лотов N')."""
    now = utcnow()
    fields = {k: v for k, v in fields.items() if v is not None}
    if "seller" in fields or "title" in fields:
        fields.setdefault("fingerprint", make_fingerprint(fields.get("seller"), fields.get("title")))
    row = conn.execute("SELECT ebay_item_id FROM items WHERE ebay_item_id=?", (ebay_item_id,)).fetchone()
    if row:
        sets = ", ".join(f"{c}=?" for c in fields)
        conn.execute(
            f"UPDATE items SET {sets}, last_seen_at=?, times_seen=times_seen+1 WHERE ebay_item_id=?",
            list(fields.values()) + [now, ebay_item_id],
        )
        return False
    cols = ["ebay_item_id"] + list(fields) + ["first_seen_at", "last_seen_at"]
    vals = [ebay_item_id] + list(fields.values()) + [now, now]
    conn.execute(
        f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals
    )
    return True


def record_verdict(conn, run_id, ebay_item_id, **fields):
    fields = {k: v for k, v in fields.items() if v is not None}
    cols = ["run_id", "ebay_item_id", "created_at"] + list(fields)
    vals = [run_id, ebay_item_id, utcnow()] + list(fields.values())
    cur = conn.execute(
        f"INSERT INTO verdicts ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals
    )
    return cur.lastrowid


def start_run(conn, mode, config_json=None):
    cur = conn.execute(
        "INSERT INTO runs (started_at, mode, config_json) VALUES (?,?,?)",
        (utcnow(), mode, json.dumps(config_json, ensure_ascii=False) if config_json else None),
    )
    return cur.lastrowid


def finish_run(conn, run_id, n_queries=0, n_items_seen=0, n_candidates=0):
    conn.execute(
        "UPDATE runs SET finished_at=?, n_queries=?, n_items_seen=?, n_candidates=? WHERE id=?",
        (utcnow(), n_queries, n_items_seen, n_candidates, run_id),
    )


# ---------- сделки ----------

def record_press_id(conn, ebay_item_id, answer: dict):
    """Кладёт разбор по фото. Возвращает id записи."""
    dg = answer.get("deep_groove")
    cur = conn.execute(
        "INSERT INTO press_ids (ebay_item_id, created_at, press_generation, "
        "press_confidence, catno_on_label, rim_text, deep_groove, runout, "
        "mono_stereo, condition_notes, press_evidence, chosen_release_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (str(ebay_item_id), utcnow(), answer.get("press_generation"),
         answer.get("press_confidence"), answer.get("catno_on_label"),
         answer.get("rim_text"), None if dg is None else int(bool(dg)),
         answer.get("runout"), answer.get("mono_stereo"),
         answer.get("condition_notes"),
         json.dumps(answer.get("press_evidence") or [], ensure_ascii=False),
         answer.get("chosen_release_id")),
    )
    return cur.lastrowid


def latest_press_id(conn, ebay_item_id):
    return conn.execute(
        "SELECT * FROM press_ids WHERE ebay_item_id=? ORDER BY created_at DESC LIMIT 1",
        (str(ebay_item_id),)).fetchone()


def create_deal(conn, ebay_item_id, release_id=None, status="seen", **fields):
    now = utcnow()
    if status not in DEAL_STATUSES:
        raise ValueError(f"Неизвестный статус сделки: {status!r}. Допустимые: {DEAL_STATUSES}")
    fields = {k: v for k, v in fields.items() if v is not None}
    cols = ["ebay_item_id", "release_id", "status", "created_at", "updated_at"] + list(fields)
    vals = [ebay_item_id, release_id, status, now, now] + list(fields.values())
    cur = conn.execute(
        f"INSERT INTO deals ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals
    )
    deal_id = cur.lastrowid
    conn.execute("INSERT INTO deal_events (deal_id, at, status) VALUES (?,?,?)", (deal_id, now, status))
    return deal_id


def update_deal(conn, deal_id, status=None, **fields):
    if status is not None and status not in DEAL_STATUSES:
        raise ValueError(f"Неизвестный статус сделки: {status!r}. Допустимые: {DEAL_STATUSES}")
    now = utcnow()
    fields = {k: v for k, v in fields.items() if v is not None}
    if status:
        fields["status"] = status
    if not fields:
        return
    # days_to_sale считаем сами, если пришла дата продажи и есть дата покупки
    if fields.get("sold_date"):
        row = conn.execute("SELECT created_at FROM deals WHERE id=?", (deal_id,)).fetchone()
        if row:
            try:
                d0 = datetime.fromisoformat(row["created_at"]).date()
                d1 = datetime.fromisoformat(fields["sold_date"]).date()
                fields.setdefault("days_to_sale", (d1 - d0).days)
            except ValueError:
                pass
    sets = ", ".join(f"{c}=?" for c in fields)
    conn.execute(f"UPDATE deals SET {sets}, updated_at=? WHERE id=?", list(fields.values()) + [now, deal_id])
    if status:
        conn.execute(
            "INSERT INTO deal_events (deal_id, at, status, payload) VALUES (?,?,?,?)",
            (deal_id, now, status, json.dumps(fields, ensure_ascii=False)),
        )


# ---------- разовый импорт истории ----------

def import_decisions_log_csv(conn, csv_path):
    """Переносит накопленный decisions_log.csv в базу. Идемпотентно:
    повторный запуск не плодит дубли (ключ — ebay_item_id из URL)."""
    import re
    path = Path(csv_path)
    if not path.exists():
        return 0
    imported = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = row.get("listing_url", "")
            m = re.search(r"/itm/(\d+)", url)
            item_id = m.group(1) if m else url
            if not item_id:
                continue
            def num(key):
                try:
                    return float(row.get(key) or "")
                except ValueError:
                    return None
            is_new = upsert_item(
                conn, item_id,
                listing_url=url, title=row.get("title"),
                price_usd=num("current_price"),
            )
            record_verdict(
                conn, None, item_id,
                verdict=row.get("verdict"),
                margin_world=num("margin_condition_adjusted"),
                landed_standalone_usd=num("landed_cost"),
                resolution_confidence=row.get("resolution_confidence") or None,
                pricing_source=row.get("pricing_source") or None,
                notes=(row.get("notes_outcome") or None),
            )
            imported += 1
    return imported


if __name__ == "__main__":
    p = init_db()
    print(f"Схема создана/актуализирована: {p}")

# ───────── кандидаты обхода («Установки 01.09.2026» §5.4 / §6) ─────────
# Раньше кандидаты жили только в логе, и любая проверка гипотезы стоила
# нового прогона на 40 минут. Хуже того: без них невозможно исполнить
# ПРАВИЛО 2 устава («ноль находок проверяется так же придирчиво, как
# находка») — нечем ответить, посмотрела система или нет.
SWEEP_SCHEMA = """
CREATE TABLE IF NOT EXISTS sweep_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    positions   INTEGER,
    candidates  INTEGER,
    sellers     INTEGER,
    bundles     INTEGER,
    details     INTEGER,
    findings    INTEGER,
    params      TEXT
);
CREATE TABLE IF NOT EXISTS sweep_candidates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER REFERENCES sweep_runs(run_id),
    ebay_item_id TEXT,
    title        TEXT,
    seller       TEXT,
    price_usd    REAL,
    shipping_usd REAL,
    country      TEXT,
    url          TEXT,
    wl_artist    TEXT,
    wl_album     TEXT,
    wl_median_rub INTEGER,
    wl_sold_n    INTEGER,
    in_bundle    INTEGER,
    grade        TEXT,
    ru_price_rub INTEGER,
    target       REAL,
    tier         TEXT,
    margin_ru    REAL,
    max_bid_usd  REAL,
    profit_rub   REAL,
    manual_review INTEGER,
    passed       INTEGER NOT NULL,
    reject_why   TEXT,
    seen_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sc_run    ON sweep_candidates(run_id);
CREATE INDEX IF NOT EXISTS idx_sc_passed ON sweep_candidates(passed);
CREATE INDEX IF NOT EXISTS idx_sc_why    ON sweep_candidates(reject_why);
"""


def init_sweep(conn):
    conn.executescript(SWEEP_SCHEMA)


def start_sweep(conn, params) -> int:
    init_sweep(conn)
    cur = conn.execute(
        "INSERT INTO sweep_runs (started_at, params) VALUES (?,?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), json.dumps(
            params, ensure_ascii=False)))
    conn.commit()
    return cur.lastrowid


def finish_sweep(conn, run_id, **counts):
    fields = ", ".join(f"{k}=?" for k in counts)
    conn.execute(
        f"UPDATE sweep_runs SET finished_at=?, {fields} WHERE run_id=?",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),
         *counts.values(), run_id))
    conn.commit()


def record_candidate(conn, run_id, *, lot, entry, verdict, in_bundle):
    """Пишется КАЖДЫЙ кандидат, и прошедший, и отклонённый, вместе с
    причиной отказа. Отказы здесь важнее находок: по ним видно, чем именно
    режет контур, и не режет ли он по ошибке."""
    conn.execute(
        "INSERT INTO sweep_candidates (run_id,ebay_item_id,title,seller,price_usd,"
        "shipping_usd,country,url,wl_artist,wl_album,wl_median_rub,wl_sold_n,"
        "in_bundle,grade,ru_price_rub,target,tier,margin_ru,max_bid_usd,profit_rub,"
        "manual_review,passed,reject_why,seen_at) VALUES (" + ",".join("?" * 24) + ")",
        (run_id, lot.get("item_id"), lot.get("title"), lot.get("seller"),
         lot.get("price"), lot.get("shipping"), lot.get("country"), lot.get("url"),
         entry.get("artist"), entry.get("album"), entry.get("median_rub"),
         entry.get("sold_n"), int(bool(in_bundle)), verdict.get("grade"),
         verdict.get("ru_price_rub"), verdict.get("target"), verdict.get("tier"),
         verdict.get("margin_ru"), verdict.get("max_bid"), verdict.get("profit_rub"),
         int(bool(verdict.get("manual_review"))), int(bool(verdict.get("ok"))),
         verdict.get("gate_why") or ("" if verdict.get("ok") else "цена выше потолка"),
         datetime.now(timezone.utc).isoformat(timespec="seconds")))


# Классы отказа. Группировать надо по НИМ, а не по тексту: в тексте стоят
# конкретные числа, и «кратность 1.90x ниже 3.5x» превращалась в отдельную
# строку разбора для каждого лота — читать такое невозможно, а правило 2
# требует именно читаемого ответа.
REJECT_CLASSES = (
    ("кратность ниже целевой", ("кратность",)),
    ("прибыль ниже пола", ("прибыль", "не окупает")),
    ("нет российской цены", ("нет российской", "не посчитан")),
    ("цена выше потолка ставки", ("цена выше потолка",)),
)


def classify_reject(why: str) -> str:
    low = (why or "").lower()
    for name, keys in REJECT_CLASSES:
        if any(k in low for k in keys):
            return name
    return "прочее"


def sweep_audit(conn, run_id=None) -> dict:
    """ПРАВИЛО 2 устава: ответ на вопрос «посмотрела система или нет»,
    без перепрогона.

    Разбивка по классам отказа отвечает на него прямо: если всё упирается
    в кратность или прибыль — система посмотрела и отказала. Если в «нет
    российской цены» или «прочее» — не посмотрела, и это дефект.
    """
    init_sweep(conn)
    where, args = ("WHERE run_id=?", (run_id,)) if run_id else ("", ())
    total = conn.execute(f"SELECT COUNT(*) FROM sweep_candidates {where}", args).fetchone()[0]
    joiner = " AND" if where else "WHERE"
    passed = conn.execute(
        f"SELECT COUNT(*) FROM sweep_candidates {where}{joiner} passed=1", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT reject_why FROM sweep_candidates {where}{joiner} passed=0", args).fetchall()
    counts = {}
    for (why,) in rows:
        k = classify_reject(why)
        counts[k] = counts.get(k, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    # «Посмотрела и отказала» — это отказ по экономике. Всё остальное
    # означает, что до экономики дело не дошло.
    economic = sum(n for k, n in ranked
                   if k in ("кратность ниже целевой", "прибыль ниже пола",
                            "цена выше потолка ставки"))
    return {"candidates": total, "passed": passed,
            "rejected_by": [{"why": k, "n": n} for k, n in ranked],
            "looked_and_declined": economic,
            "did_not_look": total - passed - economic}
