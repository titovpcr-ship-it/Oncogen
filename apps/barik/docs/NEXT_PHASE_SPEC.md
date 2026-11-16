# Barik Next-Phase Upgrade Specification & Runbook

## 1. Overview
This upgrade delivers four production enhancements across `apps/barik/` and `.github/workflows/`:
1. **3-Tier Price-Anchored Paywall & Dodo Payments Backend** (`Pro Monthly`, `Pro Annual`, `Heritage Lifetime`).
2. **Gemini API C1–C2 Example De-Templatization** (`tools/enrich_c1_c2_gemini.py`).
3. **Google Indexing Acceleration for 123k+ Static Pages** (`DefinedTerm` + `AudioObject`, `LearningResource`, pre-JS example text, and 6–8 cluster links).
4. **CI/CD & Differential Release Optimization** (eliminating duplicate full builds, parallel hashing, hardlink media staging, and browser/pip caching).

---

## 2. Task 1 — 3-Tier Dodo Payments & Paywall
### Pricing Matrix
| Tier | Internal `plan` | Label / Default | Price | Billing Model |
| :--- | :--- | :--- | :--- | :--- |
| **Pro Monthly** | `month` | Price anchor | `$12` / month | Recurring (`subscription.active` / `subscription.renewed`) |
| **Pro Annual** | `year` | **Most Popular** (selected by default) | `$59` / year (`$4.92 / month`, Save 59%) | Recurring (`subscription.active` / `subscription.renewed`) |
| **Heritage Lifetime** | `life` | **One-Time Payment** | `$129` one-time | Non-recurring (`payment.succeeded` via `/payments/{id}`) |

### Backend Architecture (`server/api/lib.php`, `server/api/index.php`, `server/config.example.php`, `tools/dodo_setup.py`)
- `pay_info()` exposes `month`, `year`, `life`, plus `mLabel` (`$12`), `yLabel` (`$59`), `lLabel` (`$129`).
- `checkout` validates `plan in ['month', 'year', 'life']`, rejects active subscribers (`409 active`) and Lifetime holders (`409 have`), selects the corresponding `DODO_PRODUCT_{MONTH,YEAR,LIFE}` product ID, and passes signed `uid`/`sig`/`plan` metadata plus `return_url` (`?lang=...&pay=card&plan=...`).
- `dodo_sync()` resolves both monthly and annual subscriptions from `/subscriptions/{id}`, records `sub_plan` (`month` or `year`), and never overwrites an existing permanent `life` grant.
- `dodo_payment_sync()` verifies one-time purchases via `GET /payments/{id}`, checks `status === 'succeeded'` and `DODO_PRODUCT_LIFE`, resolves the account (`metadata.uid/sig` -> `pd_customer` -> `customer.email`), and writes permanent entitlement (`pd_sub = ''`, `sub_status = 'active'`, `sub_plan = 'life'`, `sub_until = NULL`).
- `dodo_webhook()` (`r=dodo`) handles both Standard Webhooks recurring subscription events and `payment.succeeded` Lifetime events idempotently; `pay_check` accepts both `sub` (`subscription_id`) and `payment_id` on redirect return.

### Frontend & 6-Locale Copy (`www/js/app/account.js`, `main.js`, `landing.js`, `www/css/app.css`, `www/js/i18n*.js`, `tools/build_site.py`)
- Updated paywall radio cards, landing `.pr-prem` comparison strip, legal docs (`doc_project`, `doc_refund`, `doc_terms_web`, `faq`), and `WebApplication` JSON-LD `offers` across all 6 languages (`en`, `fr`, `de`, `es`, `pt`, `ru`).
- Theme-safe CSS contrast tokens (`--accent`/`--on-accent`, `--ok-soft`/`--ok`, `--lapis`/`--on-lapis`) maintain WCAG contrast across light/dark modes and `320px–768px` mobile viewports.

### Setup Commands
```bash
# Inspect / apply 3-tier Dodo config (test mode)
python3 tools/dodo_setup.py --check

# Apply product IDs & webhook secret in live mode
python3 tools/dodo_setup.py --live \
  --month pdt_xxx --year pdt_yyy --life pdt_zzz \
  --secret whsec_xxx
```

---

## 3. Task 2 — C1–C2 Example De-Templatization (`tools/enrich_c1_c2_gemini.py`)
Replaces template-generated sentences in `data/examples/gen_c1.txt` (1,912 templates / 2,023 rows) and `data/examples/gen_c2.txt` (569 templates / 571 rows) with idiomatic Eastern Armenian C1–C2 sentences and 6-language translations using `gemini-2.5-flash` via the `google-genai` SDK.

### Guardrails
- Imports and invokes `stem_candidates()`, `contains_word_stem()`, `HY`, and `LANGS` directly from `tools/build_examples.py`, plus `headword_in_sentence()`, `ok()`, and `rejection_reasons()` from `tools/gen_examples.py`.
- Validates Eastern Armenian orthography, trailing Armenian period `։`, stem presence, sentence length (5–8 words), non-template output, and valid 6-language translations without `|` or Armenian characters.
- Any item failing validation preserves the original valid line untouched so `tools/build_examples.py` remains 100% passing.

### Runbook
```bash
# 1. Install SDK & configure API key in apps/barik/.env
pip install google-genai
export GEMINI_API_KEY="your-key"

# 2. Preview template counts & verify stem checks (no API calls)
python3 apps/barik/tools/enrich_c1_c2_gemini.py --dry-run

# 3. Test on a small batch first
python3 apps/barik/tools/enrich_c1_c2_gemini.py --limit 60 --batch 30

# 4. Resume full enrichment safely using JSON checkpoint
python3 apps/barik/tools/enrich_c1_c2_gemini.py --resume --batch 40

# 5. Rebuild examples & synthesize only changed audio hashes (Azure)
python3 apps/barik/tools/build_examples.py
python3 apps/barik/tests/test_example_quality.py
python3 apps/barik/tools/gen_audio.py --only E
```

---

## 4. Task 3 — Google Indexing Acceleration (`tools/build_seo.py`)
- **Word Pages (`/{lang}/w/{slug}.html`)**:
  - Primary JSON-LD remains `DefinedTerm`, now enriched with an embedded `AudioObject` (`contentUrl` pointing to the verified word pronunciation MP3 in `audio/{vdir}/...`), followed by `BreadcrumbList`.
  - Pre-JS static HTML renders `.exs` / `.ex-tx` example sentences directly from the 20,121-word `www/ex/{lang}.json` shards (`noindex = 0`).
  - Internal cluster linking renders `6–8` neighboring words (`NEIGHBOURS = 8`) with deterministic same-CEFR-level fallback for tiny topics (`< 7` words).
- **Topic Pages (`/{lang}/t/{slug}.html`)**:
  - Updated primary JSON-LD schema from `DefinedTermSet` to `LearningResource` with `educationalLevel` (`A1`–`C2`), `inLanguage: ["hy", lang]`, `isAccessibleForFree`, and `BreadcrumbList`.

---

## 5. Task 4 — CI/CD & Differential Sync Optimizations
Measured bottlenecks in the ~19-minute `Release Barik` workflow and implemented non-breaking optimizations:
1. **Eliminated Duplicate Full Site Build**: Added `SHIP_REUSE_DIST=1` in `.github/workflows/barik-release.yml` and `tools/ship.sh` (guarded by `BARIK_WEB_PAID=1` / `WEB_ALL_FREE:false` + `sitemap.xml` verification) so `dist/site` built and verified by `check_all.sh --full` is deployed directly instead of deleted and rebuilt a second time.
2. **Zero-Copy Asset Staging (`tools/build_site.py`)**: `shutil.copytree` uses `os.link` hardlinks (with automatic `shutil.copy2` fallback) for immutable `.mp3`, `.webp`, and `.woff2` assets.
3. **O(1) Audio Lookup & Parallel `lastmod` (`tools/build_seo.py`)**: Pre-walks `site/audio/{vdir}` once into an in-memory set (eliminating ~370,000 `stat()` syscalls) and hashes `sitemap_lastmod()` pages with `ThreadPoolExecutor`.
4. **Parallel Hashing & Faster Zip Deflate (`tools/deploy_site.py`)**: Uses `ThreadPoolExecutor` for `release_plan()` SHA-1 scans and `guarded_release()` SHA-256 manifests, and `compresslevel=3` in `make_zips()` while keeping `.mp3`/`.webp`/`.png`/`.jpg`/`.woff2` `ZIP_STORED` and `state.json` differential upload intact.
5. **CI Dependency Caching (`.github/workflows/barik-release.yml`)**: Caches `~/.cache/pip` and `~/.cache/ms-playwright` cleanly via `actions/cache@v4`.
