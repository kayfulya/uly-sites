"""
Импорт истории очков уважения из 26 скринов (~14-24 мая 2026).
Запуск: ./venv/bin/python import_history.py
"""
import json
import os
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA_JSON = BASE / "data.json"
DATA_JS = BASE / "data.js"


def save_data(data):
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    DATA_JSON.write_text(raw, encoding="utf-8")
    DATA_JS.write_text(f"window.PAUK_DATA = {raw};", encoding="utf-8")


def upsert_member(data, m):
    for existing in data["members"]:
        if existing["id"] == m["id"]:
            existing.update(m)
            return
    data["members"].append(m)


def ensure_object(data, name, icon):
    for o in data["objects"]:
        if o["name"] == name:
            return o
    obj = {"name": name, "balance": 0, "icon": icon, "events": []}
    data["objects"].append(obj)
    return obj


def calc_balance(events):
    """null amount = аннуляция, обнуляет всё до этого момента."""
    bal = 0
    for e in events:
        if e.get("amount") is None:
            bal = 0
        else:
            bal += e["amount"]
    return bal


def main():
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))

    # --- 1) Новые участники + смена emoji Димы на 💀 ---
    new_members = [
        {"id": "vadim",         "name": "Вадим",        "alias": "Скоробогатько",  "role": "Москаль",                             "emoji": "🏙"},
        {"id": "annushka",      "name": "Аннушка",      "alias": "Anna Prokazova", "role": "Лид декора",                          "emoji": "🎨"},
        {"id": "mama_annushka", "name": "Мама Аннушки", "alias": None,             "role": "Просто мама Аннушки",                 "emoji": "💝"},
        {"id": "nikita",        "name": "Никита",       "alias": None,             "role": "Попрыгунчик",                         "emoji": "🦘"},
        {"id": "slava",         "name": "Слава",        "alias": "@svarkabilly",   "role": "Сварщик · варил бульономат и паука",  "emoji": "⚡"},
    ]
    for m in new_members:
        upsert_member(data, m)

    # Дима — 💀 (ушёл в минус, исключён из чата)
    for m in data["members"]:
        if m["id"] == "dima":
            m["emoji"] = "💀"

    # --- 2) Транзакции (люди) ---
    txs = [
        # === ФИНАНСЫ ===
        {"date": "2026-05-15", "to": ["vadim"], "amount": 1000, "reason": "Вадим первым скинул Дине 25 000 ₽ (Кэмп фи)", "by": "tanya", "chat": "Финансы"},
        {"date": "2026-05-15", "to": ["dina"],  "amount": 200,  "reason": "за быструю реакцию на финансы",                "by": "tanya", "chat": "Финансы"},
        {"date": "2026-05-16", "to": ["kravchenko"], "amount": 2000, "reason": "за второе место по скорости (скинул Дине 25 000 ₽)", "by": "tanya", "chat": "Финансы"},
        {"date": "2026-05-16", "to": ["jin"],        "amount": 2001, "reason": "он очень хотел скинуть вторым, но не успел",   "by": "tanya", "chat": "Финансы"},
        {"date": "2026-05-16", "to": ["kravchenko"], "amount": -50,  "reason": "за то что сразу за Алию не закинул",           "by": "ulya",  "chat": "Финансы"},

        # === БОЛТАЛКА ===
        {"date": "2026-05-14", "to": ["tanya"], "amount": 200, "reason": "за серьёзный подход к серьёзной теме (про сталь)", "by": "ulya", "chat": "Болталка"},
        {"date": "2026-05-14", "to": ["tanya"], "amount": 300, "reason": "за то, что Таня разбирается в людях и крутости",   "by": "ulya", "chat": "Болталка"},
        {"date": "2026-05-18", "to": ["vasya"], "amount": 500, "reason": "(просто так — Таня раздаёт)",                       "by": "tanya", "chat": "Болталка"},
        {"date": "2026-05-18", "to": ["slava"], "amount": 500, "reason": "Слава нам варил бульономат и паука",               "by": "tolya", "chat": "Болталка"},
        {"date": "2026-05-19", "to": ["ajsel"], "amount": 1000, "reason": "За то, что родилась! АЙ-СЕЛЬ! АЙ-СЕЛЬ! АЙ-СЕЛЬ!",  "by": "ulya", "chat": "Болталка"},
        {"date": "2026-05-19", "to": ["lesha"], "amount": 300, "reason": "за то что приготовил кашу и он меня сильно любит",  "by": "ulya", "chat": "Болталка"},
        {"date": "2026-05-19", "to": ["ulya"],  "amount": 300, "reason": "уле 300 ОУ за гитхаб )",                            "by": "vasya", "chat": "Болталка"},
        {"date": "2026-05-19", "to": ["tanya"], "amount": 10000, "amount_raw": 100000, "reason": "за то что она есть",        "by": "kravchenko", "chat": "Болталка", "capped": True},
        {"date": "2026-05-19", "to": ["annushka"], "amount": 500, "reason": "Аннушке за концепцию",                            "by": "ulya", "chat": "Болталка"},
        {"date": "2026-05-19", "to": ["ajsel", "aliya", "annushka"], "amount": 200, "reason": "за то, что собирались декор обсуждать", "by": "ulya", "chat": "Болталка"},

        # === ДЕКОР ===
        {"date": "2026-05-22", "to": ["mama_annushka"], "amount": 10000, "reason": "Маме Аннушки! Передай ей что это максимум очков!", "by": "ulya", "chat": "Декор"},

        # === ЛИДНОЕ ===
        {"date": "2026-05-18", "to": ["tanya"], "amount": 100, "reason": "Чтобы чувствовала себя лучше!", "by": "ulya", "chat": "Лидное"},

        # === КУХНЯ ===
        {"date": "2026-05-22", "to": ["dina"], "amount": 1000, "reason": "Дине! (за PDF оборудования кухни — сама прикинула на глаз)", "by": "ulya", "chat": "Кухня"},
        {"date": "2026-05-24", "to": ["dina"], "amount": 500,  "reason": "Дине за меню",                                                 "by": "ulya", "chat": "Кухня"},

        # === БОЛТАЛКА — давно не начисляла мужу ===
        {"date": "2026-05-25", "to": ["lesha"], "amount": 5000, "reason": "Мужу за то что давно не начисляла очки", "by": "ulya", "chat": "Болталка"},

        # === МОТОРЫ — вечер ~17.05 (после фото 16.05) ===
        {"date": "2026-05-17", "to": ["vasya"], "amount": 100, "reason": "за то, какой он счастливый",                               "by": "tanya", "chat": "Моторы"},
        {"date": "2026-05-17", "to": ["vasya"], "amount": 10000, "amount_raw": 1000000, "reason": "за коленку. Без него робот не пошёл (Толя дал 1м, согласован кап 10к)", "by": "tolya", "chat": "Моторы", "capped": True},
        {"date": "2026-05-17", "to": ["tolya"], "amount": 10000, "reason": "Урааа +10000 Толе!",                                      "by": "tanya", "chat": "Моторы"},
        {"date": "2026-05-17", "to": ["lesha"], "amount": 100,   "reason": "за то, что он муж Ули, и у него крутая фотка с бутербродом", "by": "tanya", "chat": "Моторы"},

        # === МОТОРЫ — блок питания и Толя ===
        {"date": "2026-05-18", "to": ["tolya"], "amount": 1000, "reason": "+1000 Толе! (за то что напомнил про правило 10к)", "by": "ulya", "chat": "Моторы"},

        # === МОТОРЫ — серый танк ===
        {"date": "2026-05-22", "to": ["tolya"], "amount": -10, "reason": "за то, что у него серый Танк, а не оранжевый",              "by": "tanya", "chat": "Моторы"},
        {"date": "2026-05-22", "to": ["tolya"], "amount": 11,  "reason": "за то, что он отвезёт меня на сером танке на огонёк",        "by": "tanya", "chat": "Моторы"},
        {"date": "2026-05-22", "to": ["tolya"], "amount": -20, "reason": "что Толя повезёт Таню на сером Танке",                       "by": "ulya",  "chat": "Моторы"},

        # === МОТОРЫ — отписавшиеся ===
        {"date": "2026-05-18", "to": ["demyan", "tanya", "kravchenko", "dina", "nikita"], "amount": -300, "reason": "за то что не отписались и не пришли (я вас всё равно очень-очень люблю)", "by": "ulya", "chat": "Моторы"},

        # === МОТОРЫ — Таня и ДР ===
        {"date": "2026-05-23", "to": ["tanya"], "amount": -50, "reason": "потому что мы её очень ждали, но она не приехала(", "by": "ulya", "chat": "Моторы"},
        {"date": "2026-05-24", "to": ["tanya"], "amount": 100, "reason": "за то, что планирует быть на ДР Ули",                "by": "ulya", "chat": "Моторы"},

        # === GENERAL — Дима в минус ===
        {"date": "2026-05-15", "to": ["dima"],  "amount": -10000, "reason": "ушёл в минус по очкам уважения — исключён из чата 💀", "by": "ulya", "chat": "General"},
    ]

    # Дописываем флаг capped: false где не указан
    for tx in txs:
        tx.setdefault("capped", False)

    data["transactions"].extend(txs)

    # --- 3) Каши — единичное начисление от Кравченко (не в allowlist) ---
    kashi = ensure_object(data, "Каши", "🍚")
    kashi["events"].append({"date": "2026-05-19", "amount": 100, "reason": "за то что её приготовили (заявлено Алексеем Кравченко)"})

    # --- 4) Алюминий — новые события (он был аннулирован, теперь возрождается) ---
    alum = ensure_object(data, "Алюминий", "⚙️")
    alum["events"].extend([
        {"date": "2026-05-15", "amount": 500,  "reason": "за красоту! (заявлено Улей)"},
        {"date": "2026-05-17", "amount": -100, "reason": "и без него справляемся (заявлено Таней)"},
        {"date": "2026-05-21", "amount": 100,  "reason": "за фрезеровку с первого раза и идеальное попадание в размер (Лёша попросил, Уля начислила)"},
    ])

    # --- 5) Сталь — заслужила 1500 (Таня) ---
    stal = ensure_object(data, "Сталь", "🔩")
    stal["events"].append({"date": "2026-05-14", "amount": 1500, "reason": "Сталь заслужила, как минимум, 1500 очков (заявлено Таней) — дешевле пластика и лучше алюминия"})

    # --- 6) Новые объекты ---
    pla = ensure_object(data, "Пластик (PLA)", "♻️")
    pla["events"].append({"date": "2026-05-17", "amount": 1000, "reason": "+1000 очков уважения пластику (заявлено Таней). А это кстати pla — Толя"})

    power = ensure_object(data, "Блок питания", "🔌")
    power["events"].append({"date": "2026-05-18", "amount": -100000000, "reason": "минус 100 000 000 очков блоку питания (Уля). «Он не готов к такой крутости» — Таня. Объекты могут уходить в любой минус"})

    # Паяльник — Уля сказала -500 000 (объектам кап не применяется)
    soldering = ensure_object(data, "Паяльник", "🔥")
    soldering["events"].append({"date": "2026-05-25", "amount": -500000, "reason": "−500 000 очков паяльнику (заявлено Улей)"})

    pa_cf = ensure_object(data, "PA CF", "🪶")
    pa_cf["events"].append({"date": "2026-05-22", "amount": -100, "reason": "пиара много, толку мало (Толя попросил, Уля начислила). Не выдержал 100 ньютонов"})

    newtons = ensure_object(data, "Ньютоны", "💪")
    newtons["events"].append({"date": "2026-05-22", "amount": 100, "reason": "100 очков ньютонам — у них 2:0 уже (заявлено Толей)"})

    bearing = ensure_object(data, "Верхний подшипник", "⭕")
    bearing["events"].append({"date": "2026-05-17", "amount": -100, "reason": "за то что не прикручен ко второму мотору (Уля)"})

    chlen = ensure_object(data, "Членопаук", "🍆")
    chlen["events"].append({"date": "2026-05-21", "amount": 100, "reason": "за то что существует! Новая фобия у арахнофобов (заявлено Улей)"})

    # --- 7) Пересчёт балансов всех объектов ---
    for o in data["objects"]:
        o["balance"] = calc_balance(o["events"])

    # --- 8) Сохранение ---
    save_data(data)

    print(f"✅ Готово.")
    print(f"   Транзакций добавлено: {len(txs)}")
    print(f"   Новых участников: {len(new_members)}")
    print(f"   Объектов в реестре: {len(data['objects'])}")
    print()
    print("Балансы объектов:")
    for o in data["objects"]:
        print(f"  {o['icon']} {o['name']}: {o['balance']}")


if __name__ == "__main__":
    main()
