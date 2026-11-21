"""Barik Roots (Արմատներ) — статическая энциклопедия и анализатор армянских фамилий (/{L}/s/)."""
import html
import json
import os
import re
import unicodedata

LANGS = ("ru", "en", "fr", "es", "de", "pt")

SN_CSS = """
.sn-hy{font:700 clamp(38px,9vw,60px)/1.12 A,serif;color:var(--ink);margin:6px 0 8px;letter-spacing:.01em;overflow-wrap:anywhere}
.sn-lead{font-size:17px;color:var(--mut);margin:0 0 18px}
.sn-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0}
@media (max-width:520px){.sn-grid2{grid-template-columns:1fr}}
.sn-box{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px}
.sn-k{margin:0 0 4px;font:700 12px/1.3 G,sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--mut)}
.sn-v{margin:0;font:700 20px/1.25 G,sans-serif;color:var(--ink);overflow-wrap:anywhere}
.sn-v-hy{font:700 24px/1.2 A,serif;color:var(--ink);margin:2px 0 0;overflow-wrap:anywhere}
.sn-sfx{margin:12px 0 0;padding:14px 16px;background:var(--card2);border:1px solid var(--line);border-radius:16px;font-size:15.5px;color:var(--ink)}
.sn-root{margin:16px 0;padding:18px;border-radius:20px;background:var(--card);border:1px solid var(--line)}
.sn-root-top{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.sn-root-hy{font:700 30px/1.15 A,serif;color:var(--ink)}
.sn-root-tr{font-size:17px;color:var(--mut);margin-left:8px}
.sn-root-tx{margin:6px 0 0;font-size:16px;font-weight:600;color:var(--ink)}
.sn-voices{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 0;align-items:center}
.sn-vbtn{display:inline-flex;align-items:center;gap:8px;padding:8px 14px;border-radius:99px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:600 14px/1.2 G,sans-serif;cursor:pointer}
.sn-vbtn:hover,.sn-vbtn.on{border-color:var(--acc);color:var(--acc)}
.sn-vbtn svg{width:18px;height:18px}
.sn-wlink{display:inline-block;margin:12px 0 0;font-weight:700;color:var(--acc);text-decoration:underline;text-underline-offset:3px}
.sn-hist{margin:16px 0;padding:16px 18px;border-radius:18px;background:var(--card);border:1px solid var(--line)}
.sn-hist p{margin:0 0 8px}.sn-hist p:last-child{margin:0}
.sn-card-act{margin:18px 0}
.btn-card{display:inline-flex;align-items:center;justify-content:center;gap:10px;width:100%;max-width:540px;padding:14px 20px;border-radius:16px;border:1.5px solid #C9963A;background:#0E1330;color:#FBF6F1;font:700 16px/1.3 G,sans-serif;cursor:pointer;text-align:center}
.btn-card:hover{background:#161E4A}
.sn-card-st{margin:8px 0 0;font-size:14px;color:var(--mut);min-height:1.2em}
.surname-gift-cta{margin:22px 0 10px;padding:22px 20px;border-radius:22px;background:#0E1330;color:#FBF6F1;border:1px solid rgba(212,175,94,.42)}
.surname-gift-cta h2{margin:0 0 14px;font:700 clamp(20px,4vw,24px)/1.28 A,serif;color:#FBF6F1;letter-spacing:0}
.sn-cta-acts{display:grid;gap:10px}
.sn-cta-radio,.sn-cta-gift{display:flex;align-items:center;justify-content:center;gap:8px;padding:13px 16px;border-radius:14px;font:700 15.5px/1.3 G,sans-serif;text-decoration:none;text-align:center}
.sn-cta-radio{background:rgba(255,255,255,.12);color:#FBF6F1;border:1px solid rgba(255,255,255,.2)}
.sn-cta-radio:hover{background:rgba(255,255,255,.18);text-decoration:none}
.sn-cta-gift{background:#D4AF5E;color:#0E1330}
.sn-cta-gift:hover{background:#E0BE74;text-decoration:none}
.sn-search{width:100%;box-sizing:border-box;padding:13px 16px;border-radius:14px;border:1.5px solid var(--line);background:var(--card);color:var(--ink);font:500 16px/1.3 G,sans-serif;margin:12px 0}
.sn-search:focus{outline:2px solid var(--acc);outline-offset:2px}
.sn-cats{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 14px}
.sn-cat{padding:8px 13px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--ink);font:600 14px/1.2 G,sans-serif;cursor:pointer}
.sn-cat[aria-pressed="true"]{background:var(--acc);color:#fff;border-color:var(--acc)}
.sn-cnt{margin:6px 0 12px;font-size:14px;color:var(--mut)}
.sn-list{list-style:none;padding:0;margin:10px 0 20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.sn-list a{display:flex;flex-direction:column;gap:4px;padding:13px 15px;border-radius:16px;background:var(--card);border:1px solid var(--line);text-decoration:none;color:var(--ink);height:100%;box-sizing:border-box}
.sn-list a:hover{border-color:var(--acc);text-decoration:none}
.sn-li-hy{font:700 22px/1.2 A,serif;color:var(--ink)}
.sn-li-lat{font:700 16px/1.25 G,sans-serif;color:var(--ink)}
.sn-li-m{font-size:14px;color:var(--mut);margin-top:2px}
.sn-dyn{margin:16px 0 22px;padding:18px;border-radius:20px;background:var(--card);border:1.5px solid #C9963A}
.sn-dyn[hidden]{display:none}
.sn-dyn-k{margin:0 0 6px;font:700 12px/1.3 G,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--pom)}
.sn-parts{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 12px}
.sn-part{padding:8px 12px;border-radius:12px;background:var(--bg);border:1px solid var(--line);font-size:14.5px}
.sn-part b{display:block;font-size:16px;color:var(--ink)}
.sn-part small{color:var(--mut)}
.sn-related{margin:22px 0 10px}
.sn-related h2{margin:0 0 10px;font-size:19px}
.sn-rel{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
.sn-rel a{display:flex;flex-direction:column;gap:2px;padding:10px 12px;border-radius:14px;background:var(--card);border:1px solid var(--line);text-decoration:none;color:var(--ink);height:100%;box-sizing:border-box}
.sn-rel a:hover{border-color:var(--acc);text-decoration:none}
.sn-rel-hy{font:700 18px/1.2 A,serif;color:var(--ink);overflow-wrap:anywhere}
.sn-rel-lat{font:600 13.5px/1.25 G,sans-serif;color:var(--mut);overflow-wrap:anywhere}
@media (prefers-color-scheme:dark){
  .btn-card{background:#18204B;color:#FBF6F1;border-color:#D4AF5E}
  .surname-gift-cta{background:#161C3B;border-color:rgba(212,175,94,.45)}
}
"""

SN_TXT = {
    "ru": {
        "nav": "Армянские фамилии",
        "idx_t": "Barik Roots (Արմատներ) — энциклопедия и анализатор армянских фамилий | Barik",
        "idx_d": "{total} армянских фамилий и живой морфологический анализатор редких фамилий: корень слова, озвучка от Anahit и Hayk, семейный герб-карточка.",
        "idx_h": "Энциклопедия армянских фамилий",
        "idx_sub": "Barik Roots (Արմատներ): найдите свою фамилию среди {total} исторических родов или введите любую редкую фамилию — анализатор разберёт приставку, корень и суффикс.",
        "search_lbl": "Поиск фамилии на русском, латинице или армянском",
        "search_ph": "Введите фамилию: Кардашьян, Ter-Petrosyan, Hacikyan, Դարբինյան…",
        "cats": {"all": "Все", "craft": "Ремёсла", "noble": "Княжеские", "nature": "Природа", "heritage": "Духовные", "trait": "Характер", "place": "Земли и города"},
        "cnt_tpl": "Найдено в энциклопедии: {n}",
        "no_res": "Ниже работает живой анализатор для редких и составных фамилий.",
        "dyn_k": "Живой морфологический разбор",
        "dyn_h": "Разбор фамилии «{q}»",
        "dyn_pfx": "Приставка",
        "dyn_root": "Корень в словаре",
        "dyn_sfx": "Суффикс",
        "dyn_open_w": "Открыть корень «{a}» в словаре →",
        "dyn_listen": "Слушать корень",
        "dyn_no_root": "Корень не найден напрямую в базовом списке — попробуйте убрать суффикс или сравнить с однокоренными словами.",
        "pfx_map": {
            "ter": "Тер- (Տեր) — духовный род священника, «господин / отец»",
            "melik": "Мелик- (Մելիք) — владетельный князь горной Армении",
            "kara": "Кара- — старинный тюркско-армянский эпитет («могучий / чёрный»)",
            "mirza": "Мирза- — почётный титул писца и просвещённого вельможи",
        },
        "sfx_map": {
            "yan": "-ян / -ian (от грабарского -եան) — «сын, потомок рода»",
            "uni": "-уни (-ունի) — древний царско-нахарарский родовой суффикс",
            "tsi": "-ци (-ցի) — географический суффикс («родом из…»)",
            "ents": "-енц / -онц (-ենց) — горный патронимический суффикс Сюника и Арцаха («дом / клан»)",
        },
        "title": "{lat} ({hy}) — значение и происхождение фамилии | Barik Roots",
        "desc": "Что означает армянская фамилия {lat} ({hy}): восточноармянское и западное написание, корень «{root}» [{rtr}], живая озвучка и семейный герб.",
        "h1": "{lat} ({hy}) — происхождение фамилии",
        "cat_lbl": "Категория рода",
        "anat_h": "1. Анатомия фамилии и написание в диаспоре",
        "east_lbl": "Восточноармянская форма",
        "west_lbl": "Западноармянская и диаспора",
        "sfx_h": "Родовой суффикс",
        "sfx_yan": "Классический патронимический суффикс -յան восходит к древнеармянскому (грабар) -եան и означает «из рода, потомок». В Армении транслитерируется как -yan, в западной диаспоре (Франция, США, Ливан) — традиционно как -ian.",
        "sfx_uni": "Древнейший родовой суффикс -ունի (-uni) маркирует нахарарские и царские династии Великой Армении — один из старейших типов армянских фамилий в мире.",
        "root_h": "2. Живой корень фамилии",
        "voice_f": "Голос Анаит (ж)",
        "voice_m": "Голос Айк (м)",
        "root_link": "Открыть карточку слова «{a}» в словаре →",
        "anc_words_h": "Словарь ремесла и духа твоих предков",
        "hist_h": "3. История и наследие рода",
        "hist_cat": {
            "craft": "Фамилия восходит к созидательным ремесленным цехам исторической Армении. Потомственное мастерство передавалось от отца к сыну вместе с именем рода и особым уважением в общине.",
            "noble": "Это имя связано с древней армянской аристократией — нахарарами, меликами и полководцами, которые веками берегли государственность, замки и культурные традиции нагорья.",
            "nature": "Образ природы армянского нагорья — гор, солнца, плодов и благородных символов жизни — стал основой этого фамильного имени, соединив род с землёй предков.",
            "heritage": "Духовное имя хранит память о христианском и культурном наследии Армении — преемственности семьи, верности домашнему очагу и живой истории народа.",
            "trait": "Фамилия закрепляет благородную черту характера или призвание основателя рода — мудрость, стойкость, лидерство или светлое сердце.",
            "place": "Родовое имя указывает на географические истоки семьи — древний город, крепость или провинцию исторической Армении, откуда род унёс память через поколения.",
        },
        "card_btn": "🛡 Скачать семейный герб-карточку / Поделиться в семейном чате",
        "card_root": "Корень рода",
        "card_prep": "Создаём семейную карточку…",
        "card_dl": "Карточка 1080×1350 PNG скачана на устройство.",
        "card_sh": "Семейная карточка готова к отправке!",
        "cta_h": "Фамилия {name} хранит многовековую историю. Сохрани родной язык в своей семье",
        "cta_radio": "🎧 Слушать слова предков в режиме Радио",
        "cta_gift": "🎁 Оформить именной семейный доступ Heritage Lifetime ($129) для семьи {name}",
        "guilds": {"all": "Все роды", "craft": "⚒ Ремесла и Созидатели", "noble": "👑 Княжеские и Благородные роды", "nature": "🏔 Природа и Стихии", "place": "🗺 Древние города и Земли", "heritage_trait": "✝ Духовное наследие и Качества"},
        "rel_h": "Родственные фамилии этой же гильдии / региона",
        "all_sn": "← Все {total} фамилий и анализатор Barik Roots",
    },
    "en": {
        "nav": "Armenian surnames",
        "idx_t": "Barik Roots (Արմատներ) — Armenian Surname Encyclopedia & Analyzer | Barik",
        "idx_d": "Explore {total} iconic Armenian surnames and analyze any rare surname dynamically: Armenian root audio by Anahit & Hayk, suffix anatomy, and family crest PNG.",
        "idx_h": "Armenian Surname Encyclopedia",
        "idx_sub": "Barik Roots (Արմատներ): search {total} heritage surnames or enter any rare Armenian surname to break down its prefix, ancestral root, and patronymic suffix.",
        "search_lbl": "Search by surname in English, Russian Cyrillic, or Armenian",
        "search_ph": "Try: Kardashian, Ter-Petrosyan, Hacikyan, Դարբինյան…",
        "cats": {"all": "All", "craft": "Crafts", "noble": "Noble", "nature": "Nature", "heritage": "Heritage", "trait": "Virtues", "place": "Homelands"},
        "cnt_tpl": "Encyclopedia entries shown: {n}",
        "no_res": "Instant morphological analysis runs below for rare and compound surnames.",
        "dyn_k": "Live morphological analyzer",
        "dyn_h": "Analysis for “{q}”",
        "dyn_pfx": "Prefix",
        "dyn_root": "Matched Barik Root",
        "dyn_sfx": "Suffix",
        "dyn_open_w": "Open root word “{a}” in dictionary →",
        "dyn_listen": "Listen to root",
        "dyn_no_root": "No direct root match yet — check spelling variations (Western b/d/g vs Eastern p/t/k) or browse the {total} heritage houses below.",
        "pfx_map": {
            "ter": "Ter- (Տեր) — priestly lineage (“lord / parish father”)",
            "melik": "Melik- (Մելիք) — sovereign highland prince of Syunik or Artsakh",
            "kara": "Kara- — historical honorific epithet (“mighty / dark”)",
            "mirza": "Mirza- — scholarly scribe & noble courtier title",
        },
        "sfx_map": {
            "yan": "-yan / -ian (from Classical Armenian -եան) — “child / descendant of”",
            "uni": "-uni (-ունի) — ancient Nakharar royal dynastic clan suffix",
            "tsi": "-tsi (-ցի) — geographic origin suffix (“native of…”)",
            "ents": "-ents / -onts (-ենց) — highland Syunik & Artsakh clan suffix (“house of…”)",
        },
        "title": "{lat} ({hy}) — Armenian Surname Meaning & Origin | Barik Roots",
        "desc": "Meaning and origin of the Armenian surname {lat} ({hy}): Eastern & Western diaspora spelling, root “{root}” [{rtr}], live audio, and family crest.",
        "h1": "{lat} ({hy}) — surname origin & meaning",
        "cat_lbl": "Lineage category",
        "anat_h": "1. Surname anatomy & diaspora spelling",
        "east_lbl": "Eastern Armenian form",
        "west_lbl": "Western / diaspora spelling",
        "sfx_h": "Ancestral suffix",
        "sfx_yan": "The patronymic ending -յան descends from Classical Armenian -եան (-ean), meaning “from the lineage of”. Eastern Armenian transliterates it as -yan, while Western Armenian diaspora communities traditionally spell it -ian.",
        "sfx_uni": "The ancient dynastic ending -ունի (-uni) identifies royal Nakharar houses of historical Armenia — among the oldest recorded hereditary surnames in the world.",
        "root_h": "2. Living ancestral root",
        "voice_f": "Anahit voice (F)",
        "voice_m": "Hayk voice (M)",
        "root_link": "Open “{a}” in Barik dictionary →",
        "anc_words_h": "Vocabulary of your ancestors’ craft & spirit",
        "hist_h": "3. History & family heritage",
        "hist_cat": {
            "craft": "This surname preserves the guild heritage of historic Armenian artisans, whose mastery was passed down alongside the family name and civic honor.",
            "noble": "This lineage recalls ancient Armenian nobility — Nakharars, Meliks, and commanders who safeguarded mountain strongholds and statecraft for centuries.",
            "nature": "Rooted in the landscapes and living emblems of the Armenian highlands, this name binds a family’s memory to sun, stone, flora, and enduring vitality.",
            "heritage": "Deeply tied to Armenia’s spiritual and cultural continuity, this surname honors family hearth, faith, and memory across generations.",
            "trait": "This hereditary name commemorates a defining virtue of its founder — wisdom, steadfastness, courage, or generosity of spirit.",
            "place": "A geographic lineage tracing the family’s ancestral homeland back to historic Armenian cities, fortresses, and provinces.",
        },
        "card_btn": "🛡 Download Family Crest Card / Share to Family Chat",
        "card_root": "Ancestral Root",
        "card_prep": "Generating family crest PNG…",
        "card_dl": "1080×1350 PNG crest downloaded.",
        "card_sh": "Family crest shared!",
        "cta_h": "The {name} name carries centuries of history. Keep Armenian alive in your family",
        "cta_radio": "🎧 Listen to ancestral words in Radio mode",
        "cta_gift": "🎁 Gift Heritage Lifetime ($129) for the {name} family",
        "guilds": {"all": "All lineages", "craft": "⚒ Crafts & Builders", "noble": "👑 Noble & Princely", "nature": "🏔 Nature & Elements", "place": "🗺 Historic Cities & Lands", "heritage_trait": "✝ Heritage & Virtues"},
        "rel_h": "Related surnames of the same guild / region",
        "all_sn": "← All {total} surnames & Barik Roots analyzer",
    },
    "fr": {
        "nav": "Noms arméniens",
        "idx_t": "Barik Roots (Արմատներ) — encyclopédie des noms arméniens | Barik",
        "idx_d": "{total} grands noms arméniens et analyseur dynamique : racine arménienne avec audio d’Anahit et Hayk, graphie orientale/occidentale et blason familial.",
        "idx_h": "Encyclopédie des noms arméniens",
        "idx_sub": "Barik Roots (Արմատներ) : explorez {total} lignées historiques ou saisissez n’importe quel nom rare pour analyser son préfixe, sa racine et son suffixe.",
        "search_lbl": "Rechercher un nom en alphabet latin, cyrillique ou arménien",
        "search_ph": "Ex. : Aznavourian, Ter-Petrosyan, Hacikyan, Դարբինյան…",
        "cats": {"all": "Tous", "craft": "Métiers", "noble": "Noblesse", "nature": "Nature", "heritage": "Héritage", "trait": "Vertus", "place": "Terres"},
        "cnt_tpl": "Noms affichés : {n}",
        "no_res": "L’analyseur morphologique ci-dessous décompose les noms rares et composés.",
        "dyn_k": "Analyse morphologique en direct",
        "dyn_h": "Analyse de « {q} »",
        "dyn_pfx": "Préfixe",
        "dyn_root": "Racine identifiée",
        "dyn_sfx": "Suffixe",
        "dyn_open_w": "Voir le mot « {a} » dans le dictionnaire →",
        "dyn_listen": "Écouter la racine",
        "dyn_no_root": "Aucune correspondance exacte trouvée — vérifiez les variantes d’orthographe ou parcourez les {total} lignées ci-dessous.",
        "pfx_map": {
            "ter": "Ter- (Տեր) — lignée sacerdotale (« seigneur / prêtre »)",
            "melik": "Melik- (Մելիք) — prince souverain des hauts plateaux",
            "kara": "Kara- — épithète historique honorifique",
            "mirza": "Mirza- — titre de lettré et de dignitaire",
        },
        "sfx_map": {
            "yan": "-yan / -ian (du grabar -եան) — « descendant de »",
            "uni": "-uni (-ունի) — suffixe des anciennes maisons princières nakharar",
            "tsi": "-tsi (-ցի) — origine géographique (« originaire de… »)",
            "ents": "-ents / -onts (-ենց) — suffixe clanique du Syunik et de l’Artsakh",
        },
        "title": "{lat} ({hy}) — origine et signification du nom arménien | Barik Roots",
        "desc": "Origine du nom arménien {lat} ({hy}) : formes orientale et occidentale, racine « {root} » [{rtr}], audio natif et blason familial.",
        "h1": "{lat} ({hy}) — histoire et sens du nom",
        "cat_lbl": "Lignée",
        "anat_h": "1. Anatomie du nom et graphies",
        "east_lbl": "Arménien oriental",
        "west_lbl": "Arménien occidental / diaspora",
        "sfx_h": "Suffixe familial",
        "sfx_yan": "La terminaison -յան vient de l’arménien classique -եան (« issu de la lignée de »). On l’écrit -yan en arménien oriental et -ian dans la diaspora occidentale.",
        "sfx_uni": "L’ancien suffixe -ունի (-uni) désigne les grandes dynasties nakharar de l’Arménie antique.",
        "root_h": "2. Racine vivante du nom",
        "voice_f": "Voix d’Anahit (F)",
        "voice_m": "Voix de Hayk (H)",
        "root_link": "Ouvrir « {a} » dans le dictionnaire →",
        "anc_words_h": "Vocabulaire du métier et de l’esprit des ancêtres",
        "hist_h": "3. Histoire et patrimoine",
        "hist_cat": {
            "craft": "Ce nom perpétue le savoir-faire des guildes d’artisans arméniens transmis de génération en génération.",
            "noble": "Cette lignée évoque l’ancienne noblesse arménienne — nakharars, méliks et bâtisseurs.",
            "nature": "Inspiré des montagnes, de la lumière et des symboles vivants d’Arménie, ce nom unit la famille à sa terre.",
            "heritage": "Ancré dans l’héritage spirituel et familial arménien, ce patronyme célèbre la mémoire du foyer.",
            "trait": "Ce nom rend hommage à une vertu fondatrice : sagesse, constance, courage ou générosité.",
            "place": "Un nom géographique qui conserve la mémoire d’une cité ou d’une province historique d’Arménie.",
        },
        "card_btn": "🛡 Télécharger le blason familial / Partager",
        "card_root": "Racine du nom",
        "card_prep": "Création de la carte blason…",
        "card_dl": "Carte PNG 1080×1350 téléchargée.",
        "card_sh": "Carte prête à partager !",
        "cta_h": "Le nom {name} porte des siècles d’histoire. Gardez la langue vivante dans votre famille",
        "cta_radio": "🎧 Écouter les mots des ancêtres en mode Radio",
        "cta_gift": "🎁 Offrir Heritage À vie (129 $) pour la famille {name}",
        "guilds": {"all": "Toutes les lignées", "craft": "⚒ Métiers & Bâtisseurs", "noble": "👑 Noblesse & Princes", "nature": "🏔 Nature & Éléments", "place": "🗺 Cités & Terres anciennes", "heritage_trait": "✝ Héritage spirituel & Vertus"},
        "rel_h": "Noms apparentés de la même guilde / région",
        "all_sn": "← Les {total} noms et l’analyseur Barik Roots",
    },
    "es": {
        "nav": "Apellidos armenios",
        "idx_t": "Barik Roots (Արմատներ) — enciclopedia de apellidos armenios | Barik",
        "idx_d": "{total} apellidos armenios y analizador morfológico en vivo: raíz armenia con audio de Anahit y Hayk, variantes oriental/occidental y escudo familiar.",
        "idx_h": "Enciclopedia de apellidos armenios",
        "idx_sub": "Barik Roots (Արմատներ): explora {total} apellidos históricos o escribe cualquier apellido poco común para analizar su prefijo, raíz y sufijo.",
        "search_lbl": "Buscar apellido en alfabeto latino, cirílico o armenio",
        "search_ph": "Ej.: Kardashian, Ter-Petrosyan, Hacikyan, Դարբինյան…",
        "cats": {"all": "Todos", "craft": "Oficios", "noble": "Nobleza", "nature": "Naturaleza", "heritage": "Legado", "trait": "Virtudes", "place": "Lugares"},
        "cnt_tpl": "Apellidos mostrados: {n}",
        "no_res": "El analizador morfológico de abajo descompone apellidos raros o compuestos.",
        "dyn_k": "Análisis morfológico en vivo",
        "dyn_h": "Análisis de «{q}»",
        "dyn_pfx": "Prefijo",
        "dyn_root": "Raíz encontrada",
        "dyn_sfx": "Sufijo",
        "dyn_open_w": "Abrir «{a}» en el diccionario →",
        "dyn_listen": "Escuchar raíz",
        "dyn_no_root": "No hubo coincidencia directa — revisa variantes de escritura o explora los {total} apellidos abajo.",
        "pfx_map": {
            "ter": "Ter- (Տեր) — linaje sacerdotal («señor / padre»)",
            "melik": "Melik- (Մելիք) — príncipe soberano armenio",
            "kara": "Kara- — epíteto histórico honorífico",
            "mirza": "Mirza- — título de erudito y dignatario",
        },
        "sfx_map": {
            "yan": "-yan / -ian (del armenio clásico -եան) — «descendiente de»",
            "uni": "-uni (-ունի) — sufijo de antiguas dinastías najarar",
            "tsi": "-tsi (-ցի) — procedencia geográfica («originario de…»)",
            "ents": "-ents / -onts (-ենց) — sufijo de clan de Syunik y Artsaj",
        },
        "title": "{lat} ({hy}) — significado y origen del apellido armenio | Barik Roots",
        "desc": "Origen del apellido armenio {lat} ({hy}): escritura oriental y occidental, raíz «{root}» [{rtr}], audio real y escudo familiar.",
        "h1": "{lat} ({hy}) — origen del apellido",
        "cat_lbl": "Categoría",
        "anat_h": "1. Anatomía del apellido y grafía",
        "east_lbl": "Armenio oriental",
        "west_lbl": "Armenio occidental / diáspora",
        "sfx_h": "Sufijo ancestral",
        "sfx_yan": "La terminación -յան proviene del armenio clásico -եան («descendiente de»). Se escribe -yan en armenio oriental y -ian en la diáspora occidental.",
        "sfx_uni": "El antiguo sufijo -ունի (-uni) distingue a las casas reales y najarar de la Armenia histórica.",
        "root_h": "2. Raíz viva del apellido",
        "voice_f": "Voz de Anahit (F)",
        "voice_m": "Voz de Hayk (M)",
        "root_link": "Abrir «{a}» en el diccionario →",
        "anc_words_h": "Vocabulario del oficio y espíritu ancestral",
        "hist_h": "3. Historia y legado",
        "hist_cat": {
            "craft": "Este apellido conserva la tradición de los antiguos gremios de artesanos armenios transmitida entre generaciones.",
            "noble": "Este linaje remite a la nobleza armenia histórica — príncipes najarar, méliks y defensores.",
            "nature": "Inspirado en los símbolos naturales del altiplano armenio, este apellido une a la familia con su tierra.",
            "heritage": "Ligado al patrimonio espiritual y al hogar armenio, honra la continuidad familiar.",
            "trait": "Este apellido recuerda una virtud esencial del fundador: sabiduría, firmeza o nobleza de corazón.",
            "place": "Un linaje geográfico que guarda la memoria de una ciudad o región histórica de Armenia.",
        },
        "card_btn": "🛡 Descargar escudo familiar / Compartir",
        "card_root": "Raíz ancestral",
        "card_prep": "Generando tarjeta PNG…",
        "card_dl": "Escudo 1080×1350 PNG descargado.",
        "card_sh": "¡Tarjeta familiar lista!",
        "cta_h": "El apellido {name} guarda siglos de historia. Mantén viva la lengua en tu familia",
        "cta_radio": "🎧 Escuchar palabras ancestrales en modo Radio",
        "cta_gift": "🎁 Regalar acceso Heritage De por vida ($129) para la familia {name}",
        "guilds": {"all": "Todos los linajes", "craft": "⚒ Oficios y Creadores", "noble": "👑 Nobleza y Príncipes", "nature": "🏔 Naturaleza y Elementos", "place": "🗺 Ciudades y Tierras", "heritage_trait": "✝ Legado espiritual y Virtudes"},
        "rel_h": "Apellidos relacionados del mismo gremio / región",
        "all_sn": "← Todos los {total} apellidos y analizador Barik Roots",
    },
    "de": {
        "nav": "Armenische Nachnamen",
        "idx_t": "Barik Roots (Արմատներ) — Enzyklopädie armenischer Nachnamen | Barik",
        "idx_d": "{total} berühmte armenische Nachnamen und Live-Analysator: Wortwurzel mit Audio von Anahit & Hayk, Schreibweisen und Familienwappen als PNG.",
        "idx_h": "Enzyklopädie armenischer Nachnamen",
        "idx_sub": "Barik Roots (Արմատներ): durchsuchen Sie {total} Geschlechter oder geben Sie jeden seltenen Nachnamen ein, um Vorsilbe, Wurzel und Endung zu entschlüsseln.",
        "search_lbl": "Nachnamen in Latein, Kyrillisch oder Armenisch suchen",
        "search_ph": "Z. B. Kardashian, Ter-Petrosyan, Hacikyan, Դարբինյան…",
        "cats": {"all": "Alle", "craft": "Handwerk", "noble": "Adel", "nature": "Natur", "heritage": "Erbe", "trait": "Tugend", "place": "Orte"},
        "cnt_tpl": "Angezeigte Einträge: {n}",
        "no_res": "Der Live-Analysator unten zerlegt seltene und zusammengesetzte Nachnamen.",
        "dyn_k": "Live-Wortanalyse",
        "dyn_h": "Analyse für „{q}“",
        "dyn_pfx": "Vorsilbe",
        "dyn_root": "Wortwurzel",
        "dyn_sfx": "Endung",
        "dyn_open_w": "Wort „{a}“ im Wörterbuch öffnen →",
        "dyn_listen": "Wurzel anhören",
        "dyn_no_root": "Keine direkte Wurzel gefunden — prüfen Sie Schreibweisen oder entdecken Sie die {total} Stammhäuser unten.",
        "pfx_map": {
            "ter": "Ter- (Տեր) — Priestergeschlecht („Herr / Gemeindepriester“)",
            "melik": "Melik- (Մելիք) — souveräner armenischer Hochlandfürst",
            "kara": "Kara- — historischer Ehrenbeiname",
            "mirza": "Mirza- — Titel für Gelehrte und Würdenträger",
        },
        "sfx_map": {
            "yan": "-yan / -ian (altarmenisch -եան) — „Nachkomme von“",
            "uni": "-uni (-ունի) — Endung alter fürstlicher Nacharar-Dynastien",
            "tsi": "-tsi (-ցի) — Herkunftssuffix („stammend aus…“)",
            "ents": "-ents / -onts (-ենց) — Klan-Endung aus Sjunik und Arzach",
        },
        "title": "{lat} ({hy}) — Bedeutung & Herkunft des Nachnamens | Barik Roots",
        "desc": "Herkunft des armenischen Nachnamens {lat} ({hy}): ost- und westarmenische Schreibweise, Wurzel „{root}“ [{rtr}], Audio und Familienwappen.",
        "h1": "{lat} ({hy}) — Herkunft des Namens",
        "cat_lbl": "Kategorie",
        "anat_h": "1. Aufbau und Schreibweisen",
        "east_lbl": "Ostarmenische Form",
        "west_lbl": "Westarmenisch / Diaspora",
        "sfx_h": "Familienendung",
        "sfx_yan": "Die Endung -յան stammt vom altarmenischen -եան („aus dem Geschlecht von“). Im Ostarmenischen schreibt man -yan, in der westlichen Diaspora traditionell -ian.",
        "sfx_uni": "Das archaische Suffix -ունի (-uni) kennzeichnet fürstliche Nacharar-Häuser der armenischen Geschichte.",
        "root_h": "2. Lebendige Wortwurzel",
        "voice_f": "Stimme Anahit (w)",
        "voice_m": "Stimme Hayk (m)",
        "root_link": "„{a}“ im Wörterbuch öffnen →",
        "anc_words_h": "Wortschatz von Handwerk & Geist der Vorfahren",
        "hist_h": "3. Geschichte und Erbe",
        "hist_cat": {
            "craft": "Dieser Name bewahrt die stolze Handwerkstradition historischer armenischer Zünfte über Generationen.",
            "noble": "Dieses Geschlecht erinnert an den armenischen Hochadel — Nacharars, Meliks und Heerführer.",
            "nature": "Geprägt von Bergen, Sonne und Symbolen Armeniens verbindet der Name die Familie mit ihrer Heimat.",
            "heritage": "Tief im geistigen und kulturellen Erbe Armeniens verwurzelt, ehrt der Name Haus und Gemeinschaft.",
            "trait": "Der Name hält eine besondere Tugend des Stammvaters fest — Weisheit, Standhaftigkeit oder Mut.",
            "place": "Ein geographischer Herkunftsname, der das Andenken an eine historische Stadt oder Region bewahrt.",
        },
        "card_btn": "🛡 Familienwappen als Karte laden / Teilen",
        "card_root": "Wortwurzel",
        "card_prep": "Wappen-Karte wird erstellt…",
        "card_dl": "PNG-Wappen (1080×1350) heruntergeladen.",
        "card_sh": "Familienkarte geteilt!",
        "cta_h": "Der Name {name} trägt jahrhundertealte Geschichte. Bewahre die Sprache in deiner Familie",
        "cta_radio": "🎧 Wörter der Vorfahren im Radio-Modus hören",
        "cta_gift": "🎁 Heritage Lebenslang (129 $) für Familie {name} sichern",
        "guilds": {"all": "Alle Geschlechter", "craft": "⚒ Handwerk & Erbauer", "noble": "👑 Adel & Fürstenhäuser", "nature": "🏔 Natur & Elemente", "place": "🗺 Historische Städte & Länder", "heritage_trait": "✝ Geistiges Erbe & Tugenden"},
        "rel_h": "Verwandte Nachnamen derselben Gilde / Region",
        "all_sn": "← Alle {total} Nachnamen & Barik Roots Analysator",
    },
    "pt": {
        "nav": "Sobrenomes armênios",
        "idx_t": "Barik Roots (Արմատներ) — enciclopédia de sobrenomes armênios | Barik",
        "idx_d": "{total} sobrenomes armênios e analisador ao vivo: raiz armênia com áudio de Anahit e Hayk, formas oriental/ocidental e brasão familiar PNG.",
        "idx_h": "Enciclopédia de sobrenomes armênios",
        "idx_sub": "Barik Roots (Արմատներ): explore {total} linhagens históricas ou digite qualquer sobrenome raro para analisar prefixo, raiz e sufixo.",
        "search_lbl": "Buscar sobrenome em alfabeto latino, cirílico ou armênio",
        "search_ph": "Ex.: Kardashian, Ter-Petrosyan, Hacikyan, Դարբինյան…",
        "cats": {"all": "Todos", "craft": "Ofícios", "noble": "Nobreza", "nature": "Natureza", "heritage": "Legado", "trait": "Virtudes", "place": "Lugares"},
        "cnt_tpl": "Sobrenomes exibidos: {n}",
        "no_res": "O analisador morfológico abaixo interpreta sobrenomes raros e compostos.",
        "dyn_k": "Análise morfológica ao vivo",
        "dyn_h": "Análise de “{q}”",
        "dyn_pfx": "Prefixo",
        "dyn_root": "Raiz encontrada",
        "dyn_sfx": "Sufixo",
        "dyn_open_w": "Abrir “{a}” no dicionário →",
        "dyn_listen": "Ouvir raiz",
        "dyn_no_root": "Nenhuma correspondência direta — tente variantes ortográficas ou veja os {total} sobrenomes abaixo.",
        "pfx_map": {
            "ter": "Ter- (Տեր) — linhagem sacerdotal (“senhor / pároco”)",
            "melik": "Melik- (Մելիք) — príncipe soberano armênio",
            "kara": "Kara- — epíteto histórico honorífico",
            "mirza": "Mirza- — título de escriba e nobre instruído",
        },
        "sfx_map": {
            "yan": "-yan / -ian (do armênio clássico -եան) — “descendente de”",
            "uni": "-uni (-ունի) — sufixo de antigas dinastias nakharar",
            "tsi": "-tsi (-ցի) — origem geográfica (“natural de…”)",
            "ents": "-ents / -onts (-ենց) — sufixo clânico de Syunik e Artsakh",
        },
        "title": "{lat} ({hy}) — origem e significado do sobrenome armênio | Barik Roots",
        "desc": "Significado do sobrenome armênio {lat} ({hy}): grafia oriental e ocidental, raiz “{root}” [{rtr}], áudio nativo e brasão da família.",
        "h1": "{lat} ({hy}) — origem do sobrenome",
        "cat_lbl": "Categoria",
        "anat_h": "1. Anatomia do sobrenome e grafias",
        "east_lbl": "Armênio oriental",
        "west_lbl": "Armênio ocidental / diáspora",
        "sfx_h": "Sufixo ancestral",
        "sfx_yan": "A terminação -յան vem do armênio clássico -եան (“descendente de”). É grafada -yan no armênio oriental e -ian na diáspora ocidental.",
        "sfx_uni": "O antigo sufixo -ունի (-uni) identifica antigas casas principescas nakharar da Armênia histórica.",
        "root_h": "2. Raiz viva do sobrenome",
        "voice_f": "Voz de Anahit (F)",
        "voice_m": "Voz de Hayk (M)",
        "root_link": "Abrir “{a}” no dicionário →",
        "anc_words_h": "Vocabulário do ofício e espírito dos ancestrais",
        "hist_h": "3. História e legado",
        "hist_cat": {
            "craft": "Este sobrenome preserva o orgulho das antigas guildas de artesãos armênios transmitido por gerações.",
            "noble": "Esta linhagem remonta à nobreza armênia — príncipes nakharar, meliks e comandantes.",
            "nature": "Ligado às paisagens e símbolos vivos da Armênia, este sobrenome une a família às suas raízes.",
            "heritage": "Profundamente unido ao legado espiritual e ao lar armênio, celebra a continuidade familiar.",
            "trait": "Este sobrenome eterniza uma virtude marcante: sabedoria, firmeza, coragem ou generosidade.",
            "place": "Um sobrenome geográfico que guarda a memória de uma cidade ou província histórica armênia.",
        },
        "card_btn": "🛡 Baixar brasão da família / Compartilhar",
        "card_root": "Raiz ancestral",
        "card_prep": "Gerando cartão PNG…",
        "card_dl": "Brasão 1080×1350 PNG baixado.",
        "card_sh": "Brasão pronto para enviar!",
        "cta_h": "O sobrenome {name} guarda séculos de história. Mantenha o idioma vivo em sua família",
        "cta_radio": "🎧 Ouvir palavras ancestrais no modo Rádio",
        "cta_gift": "🎁 Presentear Heritage Vitalício ($129) para a família {name}",
        "guilds": {"all": "Todas as linhagens", "craft": "⚒ Ofícios e Construtores", "noble": "👑 Nobreza e Príncipes", "nature": "🏔 Natureza e Elementos", "place": "🗺 Cidades e Terras antigas", "heritage_trait": "✝ Legado espiritual e Virtudes"},
        "rel_h": "Sobrenomes relacionados da mesma guilda / região",
        "all_sn": "← Todos os {total} sobrenomes e analisador Barik Roots",
    },
}

ROOT_ALIAS = {
    "երևան": "երևանյան",
    "արարատ": "արարատյան",
    "ոսկերիչ": "ոսկի",
    "մկրտիչ": "մկրտել",
    "վան": "վանք",
    "բեկ": "իշխան",
    "արամ": "հայ",
    "հայկ": "հայ",
    "տիգրան": "թագավոր",
    "արշակ": "Արշակունիներ",
    "ռուբեն": "Ռուբինյաններ",
    "գրիգոր": "եկեղեցի",
    "միքայել": "հրեշտակ",
    "սպենդիար": "երգ",
}

CAT_WORDS = {
    "craft": ["քար", "դարբին", "ոսկերիչ", "ոսկի", "հաց", "գինի", "ժամ", "բժիշկ", "գործ", "վարպետ", "աշխատանք", "արվեստ"],
    "noble": ["իշխան", "թագավոր", "պարոն", "ազատություն", "հայրենիք", "պատիվ", "գահ", "իշխանություն", "մելիք", "բերդ", "առաջնորդ", "փառք"],
    "nature": ["վարդ", "արծիվ", "առյուծ", "արև", "լույս", "սար", "գետ", "ծաղիկ", "նուռ", "ծով", "երկինք", "լեռ"],
    "heritage": ["խաչ", "եկեղեցի", "աղոթք", "հարություն", "ընտանիք", "արմատ", "օջախ", "ավանդույթ", "սերունդ", "հիշողություն", "հայրենիք", "ազգ"],
    "trait": ["սեր", "հաղթանակ", "իմաստուն", "ուժ", "հույս", "ճշմարտություն", "ազնիվ", "բարի", "խաղաղություն", "քաջ", "համարձակ", "պատիվ"],
    "place": ["երևանյան", "արարատյան", "քաղաք", "գյուղ", "լեռ", "ձոր", "գետ", "ճանապարհ", "տուն", "բերդ", "հայրենիք", "աշխարհ"],
}

RU_LAT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"],
))

CURATED_ROOTS = {
    "hac": ("հաց", "hats", "haci"),
    "hats": ("հաց", "hats", "haci"),
    "petros": ("պետրոս", "petros", ""),
    "poghos": ("պողոս", "poghos", ""),
    "sahak": ("սահակ", "sahak", ""),
    "aram": ("արամ", "aram", ""),
    "tigran": ("տիգրան", "tigran", ""),
    "levon": ("լևոն", "levon", ""),
    "mesrop": ("մեսրոպ", "mesrop", ""),
    "ashot": ("աշոտ", "ashot", ""),
    "mush": ("մուշ", "mush", ""),
    "kars": ("կարս", "kars", ""),
    "sasun": ("սասուն", "sasun", ""),
}


def esc(x):
    return html.escape(x or "", quote=True)


def slug_norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


def ru_translit(s):
    return "".join(RU_LAT.get(c, RU_LAT.get(c.lower(), c)) for c in (s or ""))


def eastern_lat(it):
    sl = it["slug"].lower()
    if sl == "kardashian":
        return "Kardashyan"
    if sl == "aznavourian":
        return "Aznavuryan"
    if sl == "orbelian":
        return "Orbelyan"
    if sl == "komitas":
        return "Komitasyan"
    if sl.endswith("ian"):
        return sl[:-3].capitalize() + "yan"
    return "-".join(p.capitalize() for p in sl.split("-"))


def ru_display_name(lat):
    # Clean Cyrillic helper only where standard, paired clearly with Latin
    pairs = {
        "Kardashian": "Кардашьян", "Darbinyan": "Дарбинян", "Voskerchyan": "Воскерчян",
        "Aznavourian": "Азнавурян", "Bagratyan": "Багратян", "Mamikonyan": "Мамиконян",
        "Amatuni": "Аматуни", "Orbelian": "Орбелян", "Melikyan": "Меликян",
        "Ishkhanyan": "Ишханян", "Vardanyan": "Варданян", "Sargsyan": "Саргсян",
        "Grigoryan": "Григорян", "Harutyunyan": "Арутюнян", "Hakobyan": "Акопян",
        "Khachatryan": "Хачатрян", "Petrosyan": "Петросян", "Hovhannisyan": "Оганнисян",
        "Gevorgyan": "Геворгян", "Avetisyan": "Аветисян", "Manukyan": "Манукян",
        "Martirosyan": "Мартиросян", "Stepanyan": "Степанян", "Karapetyan": "Карапетян",
        "Mkrtchyan": "Мкртчян", "Nalbandyan": "Налбандян", "Hatsagortsyan": "Ацагорцян",
        "Ginegortsyan": "Гинегорцян", "Zhamkochyan": "Жамкочян", "Bzhishkyan": "Бжишкян",
        "Shirakyan": "Ширакян", "Vanetsyan": "Ванецян", "Yerevantsyan": "Ереванцян",
        "Artsruni": "Арцруни", "Aryutzyan": "Арютцян", "Arevshatyan": "Аревшатян",
        "Lousinyan": "Лусинян", "Saribekyan": "Сарибекян", "Getikyan": "Гетикян",
        "Tsaghikyan": "Цагикян", "Nranyan": "Нранян", "Shirvanyan": "Ширванян",
        "Tumanyan": "Туманян", "Komitas": "Комитасян", "Paronyan": "Паронян",
        "Serobyan": "Серобян", "Haghtanakyan": "Ахтанакян", "Imastunyan": "Имастунян",
        "Bekyan": "Бекян", "Araratyan": "Араратян",
        "Saroyan": "Сароян", "Tankyan": "Танкян", "Balakyan": "Балакян",
        "Gulbenkyan": "Гульбенкян", "Mikoyan": "Микоян", "Spendiaryan": "Спендиарян",
        "Saryan": "Сарьян", "Ayvazyan": "Айвазян", "Aramyan": "Арамян",
        "Haykyan": "Айкян", "Tigranyan": "Тигранян", "Mashtotsyan": "Маштоцян",
        "Shirazyan": "Ширазян", "Sevakyan": "Севакян", "Charentsyan": "Чаренцян",
        "Ter-Petrosyan": "Тер-Петросян", "Ter-Grigoryan": "Тер-Григорян",
        "Ter-Hakobyan": "Тер-Акопян", "Melik-Shahnazaryan": "Мелик-Шахназарян",
        "Arshakuni": "Аршакуни", "Rubinyan": "Рубинян", "Hetumyan": "Хетумян",
        "Gnuni": "Гнуни", "Rshtuni": "Рштуни", "Mokatsyan": "Мокацян",
        "Loris-Melikyan": "Лорис-Меликян", "Syunetsyan": "Сюнецян",
        "Artsakhtsyan": "Арцахцян", "Sevanetsyan": "Севанецян", "Anietsyan": "Аниецян",
        "Dvinyan": "Двинян", "Gorgagortsyan": "Горгагорцян", "Brutyan": "Брутян",
        "Zinvoryan": "Зинворян", "Dpiryan": "Дпирян", "Vardapetyan": "Вардапетян",
        "Ashughyan": "Ашугян", "Nkarichyan": "Нкарчян", "Shinakanyan": "Шинаканян",
        "Aygegortsyan": "Айгегорцян", "Tsiranyan": "Циранян", "Khndzoryan": "Хндзорян",
        "Masisyan": "Масисян", "Aragatsyan": "Арагацян", "Astghikyan": "Астхикян",
        "Erknyan": "Еркнян", "Barekamyan": "Барекамян", "Azatyan": "Азатян",
        "Koryunyan": "Корюнян", "Shirakatsyan": "Ширакацян", "Narekatsyan": "Нарекацян",
        "Aghasyan": "Агасян", "Cheronyan": "Черонян", "Malakyan": "Малакян",
        "Kirkoryan": "Керкорян", "Davtyan": "Давтян", "Poghosyan": "Погосян",
        "Sahakyan": "Саакян", "Gasparyan": "Гаспарян", "Minasyan": "Минасян",
        "Voskanyan": "Восканян", "Babayan": "Бабаян", "Mirzoyan": "Мирзоян",
        "Abrahanyan": "Абрамян", "Abrahamyan": "Абрамян", "Yesayan": "Есаян",
        "Ghazaryan": "Казарян", "Hovsepyan": "Овсепян", "Ohanyan": "Оганян",
        "Khachaturyan": "Хачатурян", "Hambardzumyan": "Амбарцумян",
        "Baghdasaryan": "Багдасарян", "Arustamyan": "Арустамян", "Malkhasyan": "Малхасян",
        "Echmiadznyan": "Эчмиадзинян", "Akhtamaryan": "Ахтамарян",
        "Gharabaghtsyan": "Карабахцян", "Qajyan": "Каджян", "Qamyan": "Камян",
    }
    if lat in pairs:
        return pairs[lat]
    def tr_part(p):
        s = p.lower()
        rules = [
            ("shch", "щ"), ("khand", "ханд"), ("kh", "х"), ("sh", "ш"), ("ch", "ч"),
            ("zh", "ж"), ("ts", "ц"), ("dz", "дз"), ("gh", "г"), ("ph", "п"),
            ("th", "т"), ("ya", "я"), ("yu", "ю"), ("ye", "е"), ("yo", "ё"),
            ("ay", "ай"), ("ey", "ей"), ("oy", "ой"), ("iy", "ий"), ("ou", "у"),
            ("a", "а"), ("b", "б"), ("c", "к"), ("d", "д"), ("e", "е"),
            ("f", "ф"), ("g", "г"), ("h", "х"), ("i", "и"), ("j", "дж"),
            ("k", "к"), ("l", "л"), ("m", "м"), ("n", "н"), ("o", "о"),
            ("p", "п"), ("q", "к"), ("r", "р"), ("s", "с"), ("t", "т"),
            ("u", "у"), ("v", "в"), ("w", "в"), ("x", "кс"), ("y", "и"), ("z", "з"),
        ]
        out, i = [], 0
        while i < len(s):
            for k, v in rules:
                if s.startswith(k, i):
                    if k == "h" and i == 0:
                        v = "" if s.startswith(("harut", "hakob", "hov")) else "г"
                    out.append(v)
                    i += len(k)
                    break
            else:
                out.append(s[i])
                i += 1
        res = "".join(out).replace("ьи", "ьи")
        return res[:1].upper() + res[1:] if res else p
    return "-".join(tr_part(p) for p in lat.split("-"))


SURNAME_JS = r"""// Shared opt-out across the app and standalone SEO/Roots pages.
(function(){
  var mode=new URLSearchParams(location.search).get('notrack');
  if(mode==='1'||mode==='0')window.__barikNotrack=mode==='1';
  try{if(mode==='1')localStorage.setItem('barik_notrack','1');else if(mode==='0')localStorage.removeItem('barik_notrack');}catch(e){/* Keep the explicit choice in memory if storage is blocked. */}
  window.barikNotrack=function(){try{return localStorage.getItem('barik_notrack')==='1'||window.__barikNotrack===true;}catch(e){return window.__barikNotrack===true;}};
  function badge(){
    var b=document.getElementById('barik-nt');
    if(!window.barikNotrack()){if(b)b.remove();return;}
    if(!window.__barikNtLogged){console.info('[Barik] notrack active (barik_notrack=1)');window.__barikNtLogged=true;}
    if(!b&&document.body){b=document.createElement('span');b.id='barik-nt';b.textContent='NT';b.style.cssText='position:fixed;bottom:6px;left:6px;z-index:9999;font:10px/1 monospace;padding:2px 5px;border-radius:4px;background:rgba(0,0,0,.55);color:#fff;pointer-events:none;opacity:.6';document.body.appendChild(b);}
  }
  badge();if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',badge,{once:true});
})();
(function(){
'use strict';
var _tz='';try{_tz=Intl.DateTimeFormat().resolvedOptions().timeZone||'';}catch(e){/* Time zone is optional. */}
var slugFromPath=(location.pathname.match(/\/s\/([^/.]+)\.html$/)||[])[1]||'';
if(slugFromPath==='index')slugFromPath='';
function snHit(ev,fam){
  if(window.barikNotrack()||location.protocol==='file:')return;
  var payload=JSON.stringify({e:ev,v:2,l:document.documentElement.lang||'en',tz:_tz,fam:fam||'',s:'family'});
  try{if(navigator.sendBeacon&&navigator.sendBeacon('/api/?r=hit',payload))return;}catch(e){/* Retry with fetch. */}
  if(typeof fetch==='function')fetch('/api/?r=hit',{method:'POST',body:payload,keepalive:true}).catch(function(){/* Best-effort telemetry. */});
}
snHit('family_visit',slugFromPath||'index');
document.addEventListener('click',function(e){
  var a=e.target.closest&&e.target.closest('.sn-cta-radio,.sn-cta-gift');if(!a)return;
  var fam=new URL(a.href,location.href).searchParams.get('family')||slugFromPath;
  snHit(a.classList.contains('sn-cta-radio')?'family_listen':'family_gift',fam);
});

function escH(s){return String(s||'').replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function normLat(s){
  return String(s||'').toLowerCase()
    .replace(/\u02b0/g,'').replace(/[\u0300-\u036f]/g,'')
    .replace(/['’ʼ`]/g,'').replace(/ou/g,'u').replace(/[^a-z0-9-]/g,'');
}
var RU_MAP={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'};
var HY_MAP={'ա':'a','բ':'b','գ':'g','դ':'d','ե':'e','զ':'z','է':'e','ը':'y','թ':'t','ժ':'zh','ի':'i','լ':'l','խ':'kh','ծ':'ts','կ':'k','հ':'h','ձ':'dz','ղ':'gh','ճ':'ch','մ':'m','յ':'y','ն':'n','շ':'sh','ո':'o','չ':'ch','պ':'p','ջ':'j','ռ':'r','ս':'s','վ':'v','տ':'t','ր':'r','ց':'ts','ւ':'u','փ':'p','ք':'k','օ':'o','ֆ':'f','և':'ev'};
function toLat(s){
  s=String(s||'').trim().toLowerCase().replace(/ու/g,'u');
  var out='';
  for(var i=0;i<s.length;i++){
    var ch=s[i];
    if(RU_MAP[ch]!==undefined) out+=RU_MAP[ch];
    else if(HY_MAP[ch]!==undefined) out+=HY_MAP[ch];
    else out+=ch;
  }
  return out;
}
function westFold(s){
  return normLat(s).replace(/dz/g,'ts').replace(/gh/g,'r').replace(/c/g,'ts').replace(/b/g,'p').replace(/d/g,'t').replace(/g/g,'k');
}

function drawPomegranate(ctx,cx,cy,r){
  ctx.save();
  ctx.translate(cx,cy);
  ctx.beginPath();
  ctx.arc(0,0,r+14,0,Math.PI*2);
  ctx.strokeStyle='rgba(212,175,94,0.45)';
  ctx.lineWidth=2;
  ctx.stroke();

  // Calyx crown
  ctx.beginPath();
  ctx.moveTo(-r*0.28,-r*0.72);
  ctx.lineTo(-r*0.36,-r*1.12);
  ctx.lineTo(-r*0.11,-r*0.92);
  ctx.lineTo(0,-r*1.20);
  ctx.lineTo(r*0.11,-r*0.92);
  ctx.lineTo(r*0.36,-r*1.12);
  ctx.lineTo(r*0.28,-r*0.72);
  ctx.closePath();
  ctx.fillStyle='#D4AF5E';
  ctx.fill();

  // Pomegranate body
  var g=ctx.createRadialGradient(-r*0.22,-r*0.2,r*0.15,0,0,r*0.98);
  g.addColorStop(0,'#C92A45');
  g.addColorStop(0.65,'#9F1D35');
  g.addColorStop(1,'#670E1F');
  ctx.beginPath();
  ctx.moveTo(0,-r*0.78);
  ctx.bezierCurveTo(r*0.78,-r*0.76,r*0.96,r*0.04,r*0.64,r*0.58);
  ctx.bezierCurveTo(r*0.38,r*0.94,-r*0.38,r*0.94,-r*0.64,r*0.58);
  ctx.bezierCurveTo(-r*0.96,r*0.04,-r*0.78,-r*0.76,0,-r*0.78);
  ctx.closePath();
  ctx.fillStyle=g;
  ctx.fill();
  ctx.lineWidth=2.5;
  ctx.strokeStyle='#D4AF5E';
  ctx.stroke();

  // 7 gleaming seeds
  var pts=[[0,-r*0.25],[-r*0.24,-r*0.06],[r*0.24,-r*0.06],[-r*0.3,r*0.22],[0,r*0.18],[r*0.3,r*0.22],[0,r*0.44]];
  for(var i=0;i<pts.length;i++){
    ctx.beginPath();
    ctx.arc(pts[i][0],pts[i][1],r*0.085,0,Math.PI*2);
    ctx.fillStyle='#FBF6F1';
    ctx.fill();
    ctx.strokeStyle='rgba(212,175,94,0.85)';
    ctx.lineWidth=1.4;
    ctx.stroke();
  }
  ctx.restore();
}

function wrapText(ctx,text,maxW,maxLines){
  var words=String(text||'').split(/\s+/).filter(Boolean),lines=[],cur='';
  for(var i=0;i<words.length;i++){
    var next=cur?(cur+' '+words[i]):words[i];
    if(ctx.measureText(next).width<=maxW) cur=next;
    else { if(cur) lines.push(cur); cur=words[i]; if(lines.length>=maxLines) break; }
  }
  if(cur&&lines.length<maxLines) lines.push(cur);
  return lines;
}

function makeBlob(canvas,cb){
  if(canvas.toBlob){
    canvas.toBlob(function(b){ cb(b); },'image/png');
    return;
  }
  var u=canvas.toDataURL('image/png'),arr=u.split(','),mime=arr[0].match(/:(.*?);/)[1],bs=atob(arr[1]),n=bs.length,u8=new Uint8Array(n);
  while(n--) u8[n]=bs.charCodeAt(n);
  cb(new Blob([u8],{type:mime}));
}

function renderCard(btn){
  var stEl=btn.parentNode&&btn.parentNode.querySelector('.sn-card-st');
  var statusPrep=btn.getAttribute('data-st-prep')||'Generating crest…';
  var statusDl=btn.getAttribute('data-st-dl')||'PNG crest downloaded.';
  var statusSh=btn.getAttribute('data-st-sh')||'Crest ready!';
  if(stEl) stEl.textContent=statusPrep;
  var meta={
    hy:btn.getAttribute('data-hy')||'',
    lat:btn.getAttribute('data-lat')||'',
    west:btn.getAttribute('data-west')||'',
    root:btn.getAttribute('data-root')||'',
    rtr:btn.getAttribute('data-rtr')||'',
    meaning:btn.getAttribute('data-meaning')||'',
    rootLbl:btn.getAttribute('data-root-lbl')||'Ancestral Root',
    slug:btn.getAttribute('data-slug')||'barik-family'
  };
  var ready=(document.fonts&&document.fonts.ready)?Promise.race([document.fonts.ready,new Promise(function(r){setTimeout(r,350);})]):Promise.resolve();
  ready.then(function(){
    var W=1080,H=1350,c=document.createElement('canvas');
    c.width=W; c.height=H;
    var ctx=c.getContext('2d');

    // Deep heritage navy gradient
    var bg=ctx.createRadialGradient(W/2,H*0.36,60,W/2,H*0.45,780);
    bg.addColorStop(0,'#1A2352');
    bg.addColorStop(0.55,'#0E1330');
    bg.addColorStop(1,'#090D22');
    ctx.fillStyle=bg;
    ctx.fillRect(0,0,W,H);

    // Ornate double gold frame
    ctx.strokeStyle='#D4AF5E';
    ctx.lineWidth=3.5;
    ctx.strokeRect(42,42,W-84,H-84);
    ctx.strokeStyle='rgba(212,175,94,0.45)';
    ctx.lineWidth=1.5;
    ctx.strokeRect(58,58,W-116,H-116);

    // Corner diamonds
    var corners=[[58,58],[W-58,58],[58,H-58],[W-58,H-58]];
    for(var i=0;i<corners.length;i++){
      ctx.save(); ctx.translate(corners[i][0],corners[i][1]); ctx.rotate(Math.PI/4);
      ctx.fillStyle='#D4AF5E'; ctx.fillRect(-7,-7,14,14); ctx.restore();
    }

    // Top brand badge
    ctx.textAlign='center';
    ctx.fillStyle='#D4AF5E';
    ctx.font='700 26px "Golos Text", system-ui, sans-serif';
    ctx.fillText('BARIK.AM  •  ARMENIAN HERITAGE',W/2,126);

    // Crest pomegranate
    drawPomegranate(ctx,W/2,265,68);

    // Armenian Surname centerpiece
    var fs=102;
    while(fs>46){
      ctx.font='700 '+fs+'px A, "Noto Serif Armenian", Georgia, serif';
      if(ctx.measureText(meta.hy).width<=900) break;
      fs-=4;
    }
    ctx.fillStyle='#FBF6F1';
    ctx.fillText(meta.hy,W/2,475);

    // Dual Latin variants
    var latLine=(meta.west&&meta.west.toLowerCase()!==meta.lat.toLowerCase())
      ?(meta.lat.toUpperCase()+'   •   '+meta.west.toUpperCase())
      :meta.lat.toUpperCase();
    ctx.fillStyle='#D4AF5E';
    ctx.font='700 34px "Golos Text", system-ui, sans-serif';
    ctx.fillText(latLine,W/2,545);

    // Gold diamond divider
    ctx.strokeStyle='rgba(212,175,94,0.55)';
    ctx.lineWidth=2;
    ctx.beginPath(); ctx.moveTo(220,605); ctx.lineTo(W-220,605); ctx.stroke();
    ctx.save(); ctx.translate(W/2,605); ctx.rotate(Math.PI/4);
    ctx.fillStyle='#D4AF5E'; ctx.fillRect(-8,-8,16,16); ctx.restore();

    // Root card box
    var bx=94,by=665,bw=W-188,bh=480;
    ctx.fillStyle='rgba(255,255,255,0.045)';
    ctx.strokeStyle='rgba(212,175,94,0.38)';
    ctx.lineWidth=2;
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(bx,by,bw,bh,28); else ctx.rect(bx,by,bw,bh);
    ctx.fill(); ctx.stroke();

    ctx.fillStyle='#D4AF5E';
    ctx.font='700 24px "Golos Text", system-ui, sans-serif';
    ctx.fillText(meta.rootLbl.toUpperCase(),W/2,732);

    ctx.fillStyle='#FBF6F1';
    ctx.font='700 48px A, "Noto Serif Armenian", Georgia, serif';
    ctx.fillText(meta.root+(meta.rtr?('  ['+meta.rtr+']'):''),W/2,808);

    ctx.fillStyle='#E8E1D6';
    ctx.font='500 33px "Golos Text", system-ui, sans-serif';
    var lines=wrapText(ctx,meta.meaning,bw-88,5);
    var ly=890;
    for(var k=0;k<lines.length;k++){
      ctx.fillText(lines[k],W/2,ly+k*46);
    }

    // Bottom emblem
    ctx.fillStyle='#D4AF5E';
    ctx.font='700 24px A, "Golos Text", sans-serif';
    ctx.fillText('ԱՐՄԱՏՆԵՐ  •  ROOTS OF ARMENIA  •  BARIK.AM',W/2,1244);

    makeBlob(c,function(blob){
      if(!blob) return;
      btn.setAttribute('data-card-done','1');
      window.__BARIK_LAST_CARD={width:W,height:H,hy:meta.hy,slug:meta.slug,bytes:blob.size};
      var fname=(meta.slug||'barik-family')+'-barik-crest.png';
      var dl=function(){
        var url=c.toDataURL('image/png'),a=document.createElement('a');
        a.href=url; a.download=fname; document.body.appendChild(a); a.click();
        setTimeout(function(){if(a.parentNode) a.parentNode.removeChild(a);},200);
        if(stEl) stEl.textContent=statusDl;
      };
      try{
        var f=typeof File==='function'?new File([blob],fname,{type:'image/png'}):null;
        if(f&&navigator.canShare&&navigator.share&&navigator.canShare({files:[f]})){
          navigator.share({files:[f],title:meta.lat+' ('+meta.hy+')',text:meta.meaning})
            .then(function(){if(stEl) stEl.textContent=statusSh;})
            .catch(function(err){if(err&&err.name==='AbortError') return; dl();});
          return;
        }
      }catch(x){}
      dl();
    });
  });
}

document.addEventListener('click',function(e){
  var b=e.target.closest&&e.target.closest('[data-act="surnameCard"]');
  if(b){
    e.preventDefault();
    snHit('surname_card',b.getAttribute('data-slug')||slugFromPath||'custom');
    renderCard(b);
  }
});

// Explorer search & Dynamic Analyzer on /{lang}/s/
var search=document.getElementById('snSearch');
if(search){
  var catBtns=document.querySelectorAll('.sn-cat[data-cat]');
  var items=document.querySelectorAll('.sn-list li[data-k]');
  var cntEl=document.getElementById('snCount');
  var dynEl=document.getElementById('snDyn');
  var lang=document.documentElement.lang||'en';
  var curCat='all';

  function parsePrefixes(lat){
    var rules=[['ter',/^ter[\s-]+(.+)$/],['ter',/^der[\s-]+(.+)$/],['melik',/^melik[\s-]+(.+)$/],['kara',/^kara[\s-]+(.+)$/],['mirza',/^mirza[\s-]+(.+)$/]];
    for(var i=0;i<rules.length;i++){
      var m=rules[i][1].exec(lat);
      if(m) return {pfx:rules[i][0],rest:m[1]};
    }
    return {pfx:'',rest:lat};
  }
  function parseSuffix(lat){
    var norm=lat.replace(/[^a-z0-9]/g,'');
    var rules=[['uni',/(.{2,})uni$/],['tsi',/(.{2,})(?:tsi|tsyan|tsian)$/],['ents',/(.{2,})(?:ents|onts|ants)$/],['yan',/(.{2,})(?:yan|ian|ean)$/]];
    for(var i=0;i<rules.length;i++){
      var m=rules[i][1].exec(norm);
      if(m) return {sfx:rules[i][0],stem:m[1]};
    }
    return {sfx:'',stem:norm};
  }
  function findRoot(stem){
    var D=window.BARIK_SN_ROOTS;
    if(!D||!D.r||stem.length<2) return null;
    var cands=[stem];
    if(stem.length>3) cands.push(stem.replace(/[aeiou]+$/,''));
    if(stem.length>4&&/(ik|uk|ak|ot|ek)$/.test(stem)) cands.push(stem.slice(0,-2));
    var f=westFold(stem);
    if(f!==stem){
      cands.push(f);
      if(f.length>3) cands.push(f.replace(/[aeiou]+$/,''));
    }
    for(var i=0;i<cands.length;i++){
      var k=cands[i];
      if(!k) continue;
      if(D.r[k]) return D.r[k];
      var kf=westFold(k);
      if(D.wf&&D.wf[kf]&&D.r[D.wf[kf]]) return D.r[D.wf[kf]];
    }
    for(var key in D.r){
      if(key.length>=3&&stem.indexOf(key)===0) return D.r[key];
    }
    return null;
  }
  function analyze(raw){
    if(!dynEl) return;
    var q=String(raw||'').trim();
    if(q.length<3){ dynEl.hidden=true; dynEl.innerHTML=''; return; }
    var D=window.BARIK_SN_ROOTS||{};
    var cfg=D.ui||{};
    var qLat=toLat(q);
    var qNorm=normLat(qLat);
    var exactSeed=false;
    for(var i=0;i<items.length;i++){
      var ks=(items[i].getAttribute('data-k')||'').split('|');
      for(var j=0;j<ks.length;j++){
        if(ks[j]===qNorm||ks[j]===q.toLowerCase()){ exactSeed=true; break; }
      }
      if(exactSeed) break;
    }
    if(exactSeed&&q.indexOf('-')<0){ dynEl.hidden=true; dynEl.innerHTML=''; return; }

    var pp=parsePrefixes(qLat.toLowerCase());
    var sp=parseSuffix(pp.rest);
    if(!pp.pfx&&!sp.sfx&&sp.stem.length<3){ dynEl.hidden=true; dynEl.innerHTML=''; return; }
    var rootMatch=findRoot(sp.stem);
    var parts=[];
    if(pp.pfx&&cfg.pfx&&cfg.pfx[pp.pfx]){
      parts.push('<div class="sn-part"><b>'+escH(pp.pfx.toUpperCase()+'-')+'</b><small>'+escH(cfg.pfx[pp.pfx])+'</small></div>');
    }
    if(rootMatch){
      parts.push('<div class="sn-part"><b lang="hy">'+escH(rootMatch.hy)+' ['+escH(rootMatch.tr)+']</b><small>'+escH((rootMatch.m&&rootMatch.m[lang])||rootMatch.m.en||'')+'</small></div>');
    } else {
      parts.push('<div class="sn-part"><b>'+escH(sp.stem)+'</b><small>'+escH(cfg.rootLbl||'Root')+'</small></div>');
    }
    if(sp.sfx&&cfg.sfx&&cfg.sfx[sp.sfx]){
      parts.push('<div class="sn-part"><b>-'+escH(sp.sfx)+'</b><small>'+escH(cfg.sfx[sp.sfx])+'</small></div>');
    }
    var dispLat=q.split(/([\s-])/).map(function(x){return /^[\s-]$/.test(x)?x:(x.charAt(0).toUpperCase()+x.slice(1));}).join('');
    var dynSlug=normLat(qLat).replace(/[^a-z0-9-]/g,'')||'armenia';
    var audioBtn='';
    if(rootMatch&&rootMatch.af){
      audioBtn='<button type="button" class="sn-vbtn" data-src="../../audio/'+escH(rootMatch.af)+'">🔊 '+escH(cfg.listen||'Listen')+'</button>';
    }
    if(rootMatch&&rootMatch.am){
      audioBtn+=' <button type="button" class="sn-vbtn" data-src="../../audio/'+escH(rootMatch.am)+'">🔊 '+escH(cfg.listen||'Listen')+' (Hayk)</button>';
    }
    var wLink=rootMatch&&rootMatch.slug
      ?'<p><a class="sn-wlink" href="../w/'+escH(rootMatch.slug)+'.html">'+escH((cfg.openW||'Open “{a}” →').replace('{a}',rootMatch.hy))+'</a></p>'
      :(!rootMatch?'<p class="sn-cnt">'+escH(cfg.noRoot||'')+'</p>':'');

    var hyTitle=/[\u0531-\u0587]/.test(q)?q:((rootMatch&&rootMatch.hy?rootMatch.hy+' ('+dispLat+')':dispLat));
    var meaningStr=rootMatch?((rootMatch.m&&rootMatch.m[lang])||rootMatch.m.en||''):(sp.sfx&&cfg.sfx&&cfg.sfx[sp.sfx])||(cfg.noRoot||'Armenian ancestral lineage');
    dynEl.hidden=false;
    dynEl.innerHTML='<p class="sn-dyn-k">'+escH(cfg.k||'Analyzer')+'</p>'
      +'<h2>'+escH((cfg.h||'Analysis: {q}').replace('{q}',dispLat))+'</h2>'
      +'<div class="sn-parts">'+parts.join('')+'</div>'
      +(audioBtn?'<div class="sn-voices">'+audioBtn+'</div>':'')
      +wLink
      +'<div class="sn-card-act"><button type="button" class="btn-card" data-act="surnameCard"'
      +' data-hy="'+escH(hyTitle)+'" data-lat="'+escH(dispLat)+'" data-west="'+escH(dispLat)+'"'
      +' data-root="'+escH(rootMatch?rootMatch.hy:sp.stem)+'" data-rtr="'+escH(rootMatch?rootMatch.tr:sp.stem)+'"'
      +' data-meaning="'+escH(meaningStr)+'" data-root-lbl="'+escH(cfg.cardRoot||'Root')+'"'
      +' data-st-prep="'+escH(cfg.cardPrep||'')+'" data-st-dl="'+escH(cfg.cardDl||'')+'" data-st-sh="'+escH(cfg.cardSh||'')+'"'
      +' data-slug="'+escH(dynSlug)+'">'+escH(cfg.cardBtn||'Download Crest Card')+'</button><p class="sn-card-st" role="status" aria-live="polite"></p></div>'
      +'<div class="surname-gift-cta"><h2>'+escH((cfg.ctaH||'').replace(/\{name\}/g,dispLat))+'</h2>'
      +'<div class="sn-cta-acts"><a class="sn-cta-radio" href="../../?lang='+escH(lang)+'&amp;listen=1&amp;family='+escH(dynSlug)+((rootMatch&&rootMatch.slug)?('&amp;root='+escH(rootMatch.slug)):'')+'&amp;ftrk=1">'+escH(cfg.ctaRadio||'Radio')+'</a>'
      +'<a class="sn-cta-gift" href="../../?lang='+escH(lang)+'&amp;paywall=gift&amp;family='+escH(dynSlug)+'&amp;ftrk=1">'+escH((cfg.ctaGift||'').replace(/\{name\}/g,dispLat))+'</a></div></div>';
  }

  function applyFilter(){
    var qRaw=search.value.trim(),qLat=normLat(toLat(qRaw)),qLow=qRaw.toLowerCase(),shown=0;
    for(var i=0;i<items.length;i++){
      var li=items[i];
      var catOk=(curCat==='all'||curCat.split(',').indexOf(li.getAttribute('data-cat')||'')>=0);
      var k=li.getAttribute('data-k')||'';
      var qOk=!qRaw||k.indexOf(qLow)>=0||(qLat&&k.indexOf(qLat)>=0);
      var vis=catOk&&qOk;
      li.hidden=!vis;
      if(vis) shown++;
    }
    if(cntEl){
      var tpl=cntEl.getAttribute('data-tpl')||'{n}';
      cntEl.textContent=shown?tpl.replace('{n}',String(shown)):(cntEl.getAttribute('data-empty')||'0');
    }
    analyze(qRaw);
  }

  search.addEventListener('input',applyFilter);
  for(var c=0;c<catBtns.length;c++){
    catBtns[c].addEventListener('click',function(){
      curCat=this.getAttribute('data-cat')||'all';
      for(var j=0;j<catBtns.length;j++) catBtns[j].setAttribute('aria-pressed',catBtns[j]===this?'true':'false');
      applyFilter();
    });
  }
}
})();"""


def load_surnames(app_dir):
    p = os.path.join(app_dir, "data", "surnames", "surnames.txt")
    rows = []
    for raw in open(p, encoding="utf-8"):
        raw = raw.strip()
        if not raw:
            continue
        cols = [c.strip() for c in raw.split("|")]
        if len(cols) != 12:
            raise ValueError(f"Expected 12 columns in surnames.txt, got {len(cols)}: {raw[:80]}")
        rows.append({
            "slug": cols[0],
            "hy": cols[1],
            "west": cols[2],
            "hy_root": cols[3],
            "rtr": cols[4],
            "cat": cols[5],
            "m": dict(zip(LANGS, cols[6:12])),
        })
    return rows


def build_surnames(site, base, d, wslug, inw, audio_rel, page_fn, crumbs_ld_fn, spk_svg, family_fn, txt_dict, app_dir):
    rows = load_surnames(app_dir)
    words = d["words"]
    TX = {"ru": "r", "en": "e", "fr": "f", "es": "s", "de": "de", "pt": "pt"}
    TR = {"ru": "tr", "en": "lt", "fr": "ft", "es": "st", "de": "dt", "pt": "ptr"}

    # Build client-side roots dictionary (seed surname roots + curated + frequent dictionary words)
    roots_map = {}
    wf_map = {}

    def put_root(key_lat, hy, tr, meanings, slug_w=""):
        k = slug_norm(key_lat)
        if not k:
            return
        af = audio_rel(hy)
        am = audio_rel(hy, "hayk")
        roots_map[k] = {
            "hy": hy,
            "tr": tr,
            "m": meanings,
            "slug": slug_w or "",
            "af": af[len("audio/"):] if af.startswith("audio/") else "",
            "am": am[len("audio/"):] if am.startswith("audio/") else "",
        }
        fk = re.sub(r"[^a-z0-9]", "", key_lat.lower().replace("dz", "ts").replace("gh", "r").replace("c", "ts").replace("b", "p").replace("d", "t").replace("g", "k"))
        if fk and fk != k and fk not in wf_map:
            wf_map[fk] = k

    # Dictionary words -> root map (add 1-word entries for high-recall dynamic analyzer)
    for w in words:
        hy = w["a"]
        lt = (w.get("lt") or "").replace("ʰ", "")
        if " " in hy or len(slug_norm(lt)) < 2:
            continue
        k = slug_norm(lt)
        if k not in roots_map:
            m = {L: w[TX[L]] for L in LANGS}
            put_root(lt, hy, lt, m, wslug.get(hy, ""))

    # Seed surnames' roots override/enrich meanings
    for it in rows:
        rw_hy = ROOT_ALIAS.get(it["hy_root"], it["hy_root"])
        w_obj = inw.get(it["hy_root"]) or inw.get(rw_hy)
        sw = wslug.get(w_obj["a"], "") if w_obj else ""
        put_root(it["rtr"], it["hy_root"], it["rtr"], it["m"], sw)
        if it["slug"].endswith(("yan", "ian")):
            stem = re.sub(r"(?:yan|ian)$", "", it["slug"])
            if stem and stem not in roots_map:
                put_root(stem, it["hy_root"], it["rtr"], it["m"], sw)

    for alias_k, (hy_r, tr_r, _) in CURATED_ROOTS.items():
        if hy_r in inw:
            w = inw[hy_r]
            put_root(alias_k, hy_r, tr_r, {L: w[TX[L]] for L in LANGS}, wslug.get(hy_r, ""))

    open(os.path.join(site, "surnames.js"), "w", encoding="utf-8").write(SURNAME_JS)

    files = 0
    sm = []

    def voice_btns(hy_text, lang_t):
        out = []
        af = audio_rel(hy_text)
        am = audio_rel(hy_text, "hayk")
        if af:
            out.append(f'<button type="button" class="sn-vbtn" data-src="../../{af}">{spk_svg}<span>{esc(lang_t["voice_f"])}</span></button>')
        if am:
            out.append(f'<button type="button" class="sn-vbtn" data-src="../../{am}">{spk_svg}<span>{esc(lang_t["voice_m"])}</span></button>')
        return " ".join(out)

    def anc_words_for(it):
        rw = inw.get(it["hy_root"]) or inw.get(ROOT_ALIAS.get(it["hy_root"], ""))
        out = []
        if rw:
            out.extend(x for x in family_fn(rw["a"]) if x in inw)
        for cw in CAT_WORDS.get(it["cat"], CAT_WORDS["craft"]):
            if cw in inw and cw not in out and (not rw or cw != rw["a"]):
                out.append(cw)
        if rw and len(out) < 6:
            out = [x for x in out if x != rw["a"]]
        return rw, out[:6]

    by_cat = {}
    for it in rows:
        by_cat.setdefault(it["cat"], []).append(it)

    for L in LANGS:
        T = SN_TXT[L]
        BT = txt_dict[L]
        tx, trk = TX[L], TR[L]

        # Shared roots index for client analyzer (UI strings match page language when inline or injected cleanly per page)
        idx_alts = {l: f"{l}/s/index.html" for l in LANGS}

        cards_html = []
        for idx, it in enumerate(rows):
            sl = it["slug"]
            east = eastern_lat(it)
            disp = ru_display_name(east) if L == "ru" else east
            meaning = it["m"][L]
            rel = f"{L}/s/{sl}.html"
            alts = {l: f"{l}/s/{sl}.html" for l in LANGS}
            cat_label = T["cats"].get(it["cat"], it["cat"])

            # Root lookup & dictionary link + voices
            rw, near_words = anc_words_for(it)
            # Direct link MUST resolve in /{L}/w/
            link_word = rw if rw else (inw[near_words[0]] if near_words else words[0])
            root_link_href = f"../w/{wslug[link_word['a']]}.html"
            root_link_text = T["root_link"].format(a=link_word["a"])
            root_meaning_tx = rw[tx] if rw else meaning

            # Try audio on hy_root first, fall back to rw or link_word so voices work wherever recordings exist
            vhtml = voice_btns(it["hy_root"], T)
            if not vhtml and rw and rw["a"] != it["hy_root"]:
                vhtml = voice_btns(rw["a"], T)
            if not vhtml:
                vhtml = voice_btns(link_word["a"], T)

            sn_vhtml = voice_btns(it["hy"], T)

            def _near_say(va):
                ar = audio_rel(va)
                if not ar:
                    return ""
                return f'<button class="say" type="button" data-src="../../{ar}" aria-label="{esc(BT["listen"])}">{spk_svg}</button>'

            near_li = "".join(
                f'<li><a href="../w/{wslug[va]}.html">'
                f'<span class="li-pic no" lang="hy" aria-hidden="true">{esc(va[:1])}</span>'
                f'<span class="hy" lang="hy">{esc(va)}</span>'
                f'<span class="t">{esc(inw[va][trk])}</span>'
                f'<span class="x">{esc(inw[va][tx])}</span></a>'
                f'{_near_say(va)}</li>'
                for va in near_words
            )

            is_uni = it["hy"].endswith("ունի") or sl.endswith("uni")
            sfx_note = T["sfx_uni"] if is_uni else T["sfx_yan"]
            west_disp = f'{it["west"]} ({it["hy"]})' if it["west"] else it["hy"]
            east_disp = f'{east}' + (f' · {disp}' if L == "ru" and disp.lower() != east.lower() else '')

            cat_pool = by_cat[it["cat"]]
            c_idx = cat_pool.index(it)
            rel_n = min(7, len(cat_pool) - 1)
            rel_items = [cat_pool[(c_idx + 1 + step * 3) % len(cat_pool)] for step in range(len(cat_pool) - 1)]
            # Deduplicate while preserving deterministic spread across the guild, ensuring 6..8 items
            seen_rel, rel_pick = {sl}, []
            for r_it in rel_items:
                if r_it["slug"] not in seen_rel:
                    seen_rel.add(r_it["slug"])
                    rel_pick.append(r_it)
                if len(rel_pick) >= rel_n:
                    break
            if len(rel_pick) < rel_n:
                for r_it in cat_pool[c_idx + 1:] + cat_pool[:c_idx]:
                    if r_it["slug"] not in seen_rel:
                        seen_rel.add(r_it["slug"])
                        rel_pick.append(r_it)
                    if len(rel_pick) >= rel_n:
                        break
            rel_li = "".join(
                f'<li><a href="{esc(r_it["slug"])}.html">'
                f'<span class="sn-rel-hy" lang="hy">{esc(r_it["hy"])}</span>'
                f'<span class="sn-rel-lat">{esc(ru_display_name(eastern_lat(r_it)) if L == "ru" else eastern_lat(r_it))}</span>'
                f'</a></li>'
                for r_it in rel_pick
            )
            rel_sec = (
                f'<section class="sn-related"><h2>{esc(T["rel_h"])}</h2>'
                f'<ul class="sn-rel">{rel_li}</ul></section>'
            ) if rel_pick else ""

            prev_it = rows[idx - 1] if idx > 0 else None
            next_it = rows[idx + 1] if idx + 1 < len(rows) else None
            pn = ('<p class="pn">'
                  + (f'<a href="{prev_it["slug"]}.html">← {esc(eastern_lat(prev_it))}</a>' if prev_it else '<span></span>')
                  + (f'<a href="{next_it["slug"]}.html">{esc(eastern_lat(next_it))} →</a>' if next_it else '')
                  + '</p>')

            title = T["title"].format(lat=disp, hy=it["hy"])
            desc = T["desc"].format(lat=disp, hy=it["hy"], root=it["hy_root"], rtr=it["rtr"])

            body = (
                f'<p class="crumbs"><a href="../">{esc(BT["dict"])}</a> › <a href="index.html">{esc(T["idx_h"])}</a></p>'
                f'<p class="eyebrow">{esc(T["cat_lbl"])}: {esc(cat_label)}</p>'
                f'<h1 class="pg">{esc(T["h1"].format(lat=disp, hy=it["hy"]))}</h1>'
                f'<div class="sn-hy" lang="hy">{esc(it["hy"])}</div>'
                f'<p class="sn-lead">{esc(meaning)}</p>'
                + (f'<div class="sn-voices">{sn_vhtml}</div>' if sn_vhtml else '')
                + f'<i class="orn" aria-hidden="true"></i>'
                f'<h2>{esc(T["anat_h"])}</h2>'
                f'<div class="sn-grid2">'
                f'<div class="sn-box"><p class="sn-k">{esc(T["east_lbl"])}</p><p class="sn-v">{esc(east_disp)}</p><p class="sn-v-hy" lang="hy">{esc(it["hy"])}</p></div>'
                f'<div class="sn-box"><p class="sn-k">{esc(T["west_lbl"])}</p><p class="sn-v">{esc(west_disp)}</p></div>'
                f'</div>'
                f'<div class="sn-sfx"><p class="sn-k">{esc(T["sfx_h"])}</p><p style="margin:4px 0 0">{esc(sfx_note)}</p></div>'
                f'<h2>{esc(T["root_h"])}</h2>'
                f'<div class="sn-root"><div class="sn-root-top"><div><span class="sn-root-hy" lang="hy">{esc(it["hy_root"])}</span>'
                f'<span class="sn-root-tr">[{esc(it["rtr"])}]</span></div></div>'
                f'<p class="sn-root-tx">{esc(root_meaning_tx)}</p>'
                + (f'<div class="sn-voices">{vhtml}</div>' if vhtml else '')
                + f'<p><a class="sn-wlink" href="{root_link_href}">{esc(root_link_text)}</a></p></div>'
                f'<h3>{esc(T["anc_words_h"])}</h3><ul class="ws">{near_li}</ul>'
                f'<h2>{esc(T["hist_h"])}</h2>'
                f'<div class="sn-hist"><p>{esc(meaning)}</p><p>{esc(T["hist_cat"].get(it["cat"], T["hist_cat"]["heritage"]))}</p></div>'
                f'<div class="sn-card-act"><button type="button" class="btn-card" data-act="surnameCard"'
                f' data-hy="{esc(it["hy"])}" data-lat="{esc(east)}" data-west="{esc(it["west"])}"'
                f' data-root="{esc(it["hy_root"])}" data-rtr="{esc(it["rtr"])}"'
                f' data-meaning="{esc(meaning)}" data-root-lbl="{esc(T["card_root"])}"'
                f' data-st-prep="{esc(T["card_prep"])}" data-st-dl="{esc(T["card_dl"])}" data-st-sh="{esc(T["card_sh"])}"'
                f' data-slug="{esc(sl)}">{esc(T["card_btn"])}</button>'
                f'<p class="sn-card-st" role="status" aria-live="polite"></p></div>'
                f'<section class="surname-gift-cta">'
                f'<h2>{esc(T["cta_h"].format(name=disp))}</h2>'
                f'<div class="sn-cta-acts">'
                f'<a class="sn-cta-radio" href="../../?lang={L}&amp;listen=1&amp;family={esc(sl)}&amp;root={esc(wslug[link_word["a"]])}&amp;ftrk=1">{esc(T["cta_radio"])}</a>'
                f'<a class="sn-cta-gift" href="../../?lang={L}&amp;paywall=gift&amp;family={esc(sl)}&amp;ftrk=1">{esc(T["cta_gift"].format(name=disp))}</a>'
                f'</div></section>'
                + rel_sec + pn + f'<p class="pn"><a href="index.html">{esc(T["all_sn"].format(total=len(rows)))}</a></p>'
            )

            ld = [
                {
                    "@context": "https://schema.org",
                    "@type": "DefinedTerm",
                    "name": it["hy"],
                    "alternateName": [east, it["west"]],
                    "termCode": it["rtr"],
                    "inLanguage": "hy",
                    "description": meaning,
                    "url": base + rel,
                    "inDefinedTermSet": {"@type": "DefinedTermSet", "name": f"Barik Roots — {T['idx_h']}", "url": f"{base}{L}/s/"},
                },
                {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": title,
                    "description": desc,
                    "inLanguage": L,
                    "url": base + rel,
                    "publisher": {"@type": "Organization", "name": "Barik", "url": base},
                },
                crumbs_ld_fn([("Barik", base), (T["idx_h"], f"{base}{L}/s/"), (disp, base + rel)]),
            ]
            p = os.path.join(site, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(page_fn(L, base, rel, title, desc, alts, body, ld, extra_js=("seo.js", "surnames.js")))
            files += 1
            sm.append((rel, alts))

            search_keys = "|".join(dict.fromkeys([
                slug_norm(sl), slug_norm(east), slug_norm(it["west"]), slug_norm(it["rtr"]),
                it["hy"].lower(), ru_display_name(east).lower(), slug_norm(ru_translit(ru_display_name(east))),
            ]))
            cards_html.append(
                f'<li data-cat="{esc(it["cat"])}" data-k="{esc(search_keys)}">'
                f'<a href="{sl}.html"><span class="sn-li-hy" lang="hy">{esc(it["hy"])}</span>'
                f'<span class="sn-li-lat">{esc(east)} / {esc(it["west"])}</span>'
                f'<span class="sn-li-m">{esc(meaning)}</span></a></li>'
            )

        # Index page /{L}/s/index.html
        guilds = (
            ("all", T["guilds"]["all"]),
            ("craft", T["guilds"]["craft"]),
            ("noble", T["guilds"]["noble"]),
            ("nature", T["guilds"]["nature"]),
            ("place", T["guilds"]["place"]),
            ("heritage,trait", T["guilds"]["heritage_trait"]),
        )
        cat_btns = "".join(
            f'<button type="button" class="sn-cat" data-cat="{c}" aria-pressed="{"true" if c == "all" else "false"}">{esc(lbl)}</button>'
            for c, lbl in guilds
        )
        idx_rel = f"{L}/s/index.html"
        ui_cfg = json.dumps({
            "k": T["dyn_k"], "h": T["dyn_h"], "pfx": T["pfx_map"], "sfx": T["sfx_map"],
            "rootLbl": T["dyn_root"], "openW": T["dyn_open_w"], "listen": T["dyn_listen"],
            "noRoot": T["dyn_no_root"].format(total=len(rows)), "cardBtn": T["card_btn"], "cardRoot": T["card_root"],
            "cardPrep": T["card_prep"], "cardDl": T["card_dl"], "cardSh": T["card_sh"],
            "ctaH": T["cta_h"], "ctaRadio": T["cta_radio"], "ctaGift": T["cta_gift"],
        }, ensure_ascii=False)
        idx_body = (
            f'<p class="crumbs"><a href="../">{esc(BT["dict"])}</a></p>'
            f'<p class="eyebrow" lang="hy">Արմատներ · Barik Roots</p>'
            f'<h1 class="pg">{esc(T["idx_h"])}</h1><i class="orn" aria-hidden="true"></i>'
            f'<p>{esc(T["idx_sub"].format(total=len(rows)))}</p>'
            f'<label class="sr" for="snSearch">{esc(T["search_lbl"])}</label>'
            f'<input id="snSearch" class="sn-search" type="search" autocomplete="off" placeholder="{esc(T["search_ph"])}" aria-label="{esc(T["search_lbl"])}">'
            f'<div class="sn-cats" role="group">{cat_btns}</div>'
            f'<section id="snDyn" class="sn-dyn" hidden></section>'
            f'<p id="snCount" class="sn-cnt" role="status" aria-live="polite" data-tpl="{esc(T["cnt_tpl"])}" data-empty="{esc(T["no_res"])}">{esc(T["cnt_tpl"].format(n=len(rows)))}</p>'
            f'<ul class="sn-list">{"".join(cards_html)}</ul>'
            f'<a class="cta" href="../../?lang={L}">{esc(BT["cta"])}</a>'
            f'<script>window.BARIK_SN_ROOTS=window.BARIK_SN_ROOTS||{{}};window.BARIK_SN_ROOTS.ui={ui_cfg};</script>'
        )
        idx_ld = crumbs_ld_fn([("Barik", base), (T["idx_h"], f"{base}{L}/s/")])
        p = os.path.join(site, idx_rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(
            page_fn(L, base, idx_rel, T["idx_t"], T["idx_d"].format(total=len(rows)), idx_alts, idx_body, idx_ld, extra_js=("seo.js", "surnames-roots.js", "surnames.js"))
        )
        files += 1
        sm.insert(0, (idx_rel, idx_alts))

    # Write shared surnames-roots.js cleanly (preserves .ui if inline script sets it later or earlier)
    roots_payload = json.dumps({"r": roots_map, "wf": wf_map}, ensure_ascii=False, separators=(",", ":"))
    open(os.path.join(site, "surnames-roots.js"), "w", encoding="utf-8").write(
        f"(function(){{var d={roots_payload};window.BARIK_SN_ROOTS=window.BARIK_SN_ROOTS||{{}};window.BARIK_SN_ROOTS.r=d.r;window.BARIK_SN_ROOTS.wf=d.wf;}})();\n"
    )

    # Sitemap with hreflang alternates for all 306 surname pages
    sm_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for rel, alts in sm:
        href_links = "".join(
            f'<xhtml:link rel="alternate" hreflang="{l}" href="{base}{p}"/>'
            for l, p in alts.items()
        ) + f'<xhtml:link rel="alternate" hreflang="x-default" href="{base}{alts.get("en", rel)}"/>'
        sm_xml.append(f"<url><loc>{base}{rel}</loc>{href_links}</url>")
    sm_xml.append("</urlset>")
    open(os.path.join(site, "sitemap-surnames.xml"), "w", encoding="utf-8").write("\n".join(sm_xml))
    print(f"фамилии (Barik Roots): {files} страниц ({len(LANGS)} языков × {len(rows) + 1})")
    return files
