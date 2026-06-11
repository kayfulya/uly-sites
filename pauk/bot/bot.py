"""
Бот Реестра Очков Уважения 🕷
Пишет начисления в ../data.json и ../data.js, которые читает index.html
"""
import json
import logging
import os
import re
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
DATA_JSON = ROOT_DIR / "data.json"
DATA_JS = ROOT_DIR / "data.js"
CONFIG = BASE_DIR / "config.json"
ALIASES = BASE_DIR / "aliases.json"
PENDING_FILE = BASE_DIR / "pending.json"
PENDING_ENTITIES_FILE = BASE_DIR / "pending_entities.json"


# ---------- IO ----------

def load_config():
    if not CONFIG.exists():
        raise SystemExit(
            f"\n❌ Нет файла {CONFIG}\n"
            f"Скопируй config.example.json в config.json и заполни токен + user_id.\n"
        )
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def load_data():
    return json.loads(DATA_JSON.read_text(encoding="utf-8"))


def save_data(data):
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    json_tmp = DATA_JSON.with_suffix(".json.tmp")
    json_tmp.write_text(raw, encoding="utf-8")
    os.replace(json_tmp, DATA_JSON)

    js_tmp = DATA_JS.with_suffix(".js.tmp")
    js_tmp.write_text(f"window.PAUK_DATA = {raw};", encoding="utf-8")
    os.replace(js_tmp, DATA_JS)

    # Авто-пуш на GitHub, чтобы сайт kayfulya.github.io/pauk-respect обновлялся
    _git_push()

def _git_push():
    """Коммитит data.js + data.json и пушит. Ошибки не роняет — логирует и идёт дальше."""
    try:
        subprocess.run(
            ["git", "-C", str(ROOT_DIR), "add", "data.json", "data.js"],
            check=True, capture_output=True, timeout=10
        )
        # --allow-empty: иногдa файлы не поменялись (напр. сохранили тот же json) — не падать
        r = subprocess.run(
            ["git", "-C", str(ROOT_DIR), "commit", "--allow-empty", "-m", "Бот: авто-пуш реестра"],
            capture_output=True, timeout=10
        )
        if r.returncode != 0:
            logging.warning(f"git commit не удался: {r.stderr.decode() if r.stderr else r}")
        subprocess.run(
            ["git", "-C", str(ROOT_DIR), "push"],
            check=True, capture_output=True, timeout=30
        )
        logging.info("Авто-пуш: реестр залит на GitHub")
    except subprocess.CalledProcessError as e:
        logging.warning(f"Авто-пуш не удался (git error): {e.stderr.decode() if e.stderr else e}")
    except Exception as e:
        logging.warning(f"Авто-пуш не удался: {e}")


def load_pending():
    if not PENDING_FILE.exists():
        return []
    return json.loads(PENDING_FILE.read_text(encoding="utf-8"))


def save_pending(p):
    tmp = PENDING_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, PENDING_FILE)


def load_pending_entities():
    if not PENDING_ENTITIES_FILE.exists():
        return []
    return json.loads(PENDING_ENTITIES_FILE.read_text(encoding="utf-8"))


def save_pending_entities(p):
    tmp = PENDING_ENTITIES_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, PENDING_ENTITIES_FILE)


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def make_slug(name):
    out = []
    for ch in name.lower():
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s or "x"


# ---------- Резолверы ----------

def build_aliases(data):
    aliases = {}
    for m in data["members"]:
        aliases[m["id"].lower()] = m["id"]
        aliases[m["name"].lower()] = m["id"]
        if m.get("alias"):
            aliases[m["alias"].lstrip("@").lower()] = m["id"]
    # Объекты доступны по имени с префиксом «obj:»
    for o in data.get("objects", []):
        aliases[o["name"].lower()] = f"obj:{o['name']}"
    if ALIASES.exists():
        for k, v in json.loads(ALIASES.read_text(encoding="utf-8")).items():
            aliases[k.lower()] = v
    return aliases


def calc_object_balance(events):
    """null amount = аннуляция, обнуляет всё до этого момента."""
    bal = 0
    for e in events:
        if e.get("amount") is None:
            bal = 0
        else:
            bal += e["amount"]
    return bal


def object_by_name(data, name):
    return next((o for o in data.get("objects", []) if o["name"] == name), None)


def write_object_event(obj_name, amount, reason):
    data = load_data()
    obj = object_by_name(data, obj_name)
    if obj is None:
        return None, None
    obj["events"].append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "amount": amount,
        "reason": reason,
    })
    obj["balance"] = calc_object_balance(obj["events"])
    save_data(data)
    return data, obj


def resolve_recipients(arg, aliases):
    parts = [p.strip().lower().lstrip("@") for p in arg.split(",") if p.strip()]
    resolved, unknown, ambiguous = [], [], []
    for p in parts:
        if p in aliases:
            mid = aliases[p]
            if isinstance(mid, str) and mid.startswith("ambig:"):
                ambiguous.append((p, mid[len("ambig:"):].split(",")))
            elif mid not in resolved:
                resolved.append(mid)
        else:
            unknown.append(p)
    return resolved, unknown, ambiguous


def recipient_from_reply(update, aliases, cfg):
    """Достаём получателя из сообщения, на которое ответили (включая форварды)."""
    msg = update.message
    if not msg or not msg.reply_to_message:
        return None
    reply = msg.reply_to_message

    candidates = []
    # 1) Форвард (если переслали чьё-то сообщение)
    fwd_user = getattr(reply, "forward_from", None)
    if fwd_user:
        candidates.append((fwd_user.username, fwd_user.first_name))
    # 2) Автор сообщения в этом чате
    if reply.from_user:
        candidates.append((reply.from_user.username, reply.from_user.first_name))

    for username, first_name in candidates:
        # сначала ищем по @username (через allowlist и aliases)
        if username:
            uname = username.lower()
            # через allowlist в config
            for member_key, val in cfg.get("allowed", {}).items():
                if isinstance(val, str) and val.lstrip("@").lower() == uname:
                    return member_key
            # через aliases (если у участника alias = @username)
            if uname in aliases:
                return aliases[uname]
        # потом по first_name (если в реестре есть)
        if first_name:
            fname = first_name.lower()
            if fname in aliases:
                return aliases[fname]
    return None


# ---------- Парсинг суммы ----------

_AMOUNT_SUFFIXES = [
    ("тысяч", 1000),
    ("тыс", 1000),
    ("млн", 1_000_000),
    ("млрд", 1_000_000_000),
    ("к", 1000),
    ("k", 1000),
    ("м", 1_000_000),
    ("m", 1_000_000),
]


def _normalize_amount_str(s):
    return s.replace("−", "-").replace("+", "").strip().lower().replace(" ", "")


def is_amount(s):
    s = _normalize_amount_str(s)
    if not s or s in ("-", "+"):
        return False
    for suffix, _ in _AMOUNT_SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
            break
    try:
        float(s)
        return True
    except ValueError:
        return False


def parse_amount(s):
    s = _normalize_amount_str(s)
    for suffix, mult in _AMOUNT_SUFFIXES:
        if s.endswith(suffix):
            num = s[: -len(suffix)].strip()
            return int(float(num) * mult)
    return int(s)


# ---------- Балансы / utilites ----------

def calc_balance(data, member_id):
    return sum(t["amount"] for t in data["transactions"] if member_id in t["to"])


def member_by_id(data, mid):
    return next(m for m in data["members"] if m["id"] == mid)


def author_id(cfg, user):
    """Принимает либо user_id (число), либо @username (строку)."""
    username = (user.username or "").lower()
    for member_key, val in cfg["allowed"].items():
        if isinstance(val, int) and val != 0 and val == user.id:
            return member_key
        if isinstance(val, str) and val.lstrip("@").lower() == username and username:
            return member_key
    return None


def apply_cap(amount_raw, cap):
    """Капим только плюсы. Минусы — без ограничения (можно убавлять сколько угодно)."""
    if amount_raw > cap:
        return cap, True
    return amount_raw, False


def format_recipients(data, recipients):
    """Имена и эмодзи для людей и объектов вперемешку."""
    names_parts = []
    emoji_parts = []
    for r in recipients:
        if r.startswith("obj:"):
            obj = object_by_name(data, r[4:])
            if obj:
                names_parts.append(obj["name"])
                emoji_parts.append(obj.get("icon", "🔧"))
            else:
                names_parts.append(r[4:])
                emoji_parts.append("🔧")
        else:
            m = member_by_id(data, r)
            names_parts.append(m["name"])
            emoji_parts.append(m["emoji"])
    return " + ".join(names_parts), "".join(emoji_parts)


# ---------- Применение транзакции ----------

def write_transaction(recipients, amount, amount_raw, capped, reason, by, chat):
    data = load_data()
    tx = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "to": recipients,
        "amount": amount,
        "reason": reason,
        "by": by,
        "chat": chat,
        "capped": capped,
    }
    if capped:
        tx["amount_raw"] = amount_raw
    data["transactions"].append(tx)
    save_data(data)
    return data


# ---------- Основная команда ----------

RU_TRIGGER = re.compile(
    r"^\s*/?(?:очки(?:\s+уважения)?|уважение|уважуха|respect)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)

# Шорткат: «+5 очков», «- 100 очков Тане за пропуск», «100к очков уважения»
# Разрешаем пробел между знаком и числом: «+ 5», «- 100»
SHORT_TRIGGER = re.compile(
    r"^\s*([+\-−]?\s*\d+(?:\s*(?:тыс|млн|к|k|м|m))?)\s+очк(?:а|ов|у|и|о)\b(?:\s+уважения)?(?:\s+(.+))?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _verb_for_amount(amount):
    """Возвращает (вопросная_форма, прошедшая_форма) с учётом знака."""
    if amount >= 0:
        return "Кому начислить", "Начислено"
    return "У кого убавить", "Убавлено"


async def _do_respect(update: Update, args):
    cfg = load_config()
    sender = update.effective_user
    by_user = author_id(cfg, sender)
    sender_label = f"@{sender.username}" if sender.username else (sender.first_name or "?")

    if not args:
        await update.message.reply_text(
            "Формат:\n"
            "  очки Вася 500 за лекцию  — начислить\n"
            "  очки Толя -50 пропустил  — убавить\n"
            "В ответ на сообщение имя не нужно:\n"
            "  очки 500 за лекцию  /  +5 очков  /  -100 очков\n"
            "Объектам: очки Алюминий +500 за красоту (без капа)\n"
            "Суффиксы: 100к, 1м, 100 тыс"
        )
        return

    data = load_data()
    aliases = build_aliases(data)

    first = args[0]
    recipients = []
    amount_arg = None
    reason = "(без причины)"

    if is_amount(first):
        # «очки <сумма> <причина>» — получатель из reply
        reply_target = recipient_from_reply(update, aliases, cfg)
        if reply_target is None:
            # Не-Совету уточнение не задаём: они должны указывать получателя сразу
            if by_user is None:
                await update.message.reply_text(
                    "🕷 Чтобы Совет проголосовал — укажи получателя в команде.\n"
                    "Пример: «очки Уля 150 за красоту» или «-100 очков Толе за опоздание»."
                )
                return
            try:
                amount_preview = parse_amount(first)
                verb_q, _ = _verb_for_amount(amount_preview)
                if amount_preview >= 0:
                    amount_text = f"+{amount_preview}"
                else:
                    amount_text = f"{abs(amount_preview)}"
            except (ValueError, TypeError):
                amount_text = first
                verb_q = "Кому начислить"
            reason_preview = " ".join(args[1:]).strip() if len(args) > 1 else ""
            reason_suffix = f' «{reason_preview}»' if reason_preview else ""
            asker = f"@{sender.username}" if sender.username else (sender.first_name or "ты")
            await update.message.reply_text(
                f"❓ {verb_q} {amount_text}{reason_suffix}?\n"
                f"{asker}, ответь именем (например: «Уля за красоту»)\n"
                f"или сделай reply на сообщение нужного человека."
            )
            return
        recipients = [reply_target]
        amount_arg = first
        reason = " ".join(args[1:]) if len(args) > 1 else "(без причины)"
    else:
        if len(args) < 2:
            await update.message.reply_text(
                "❓ Не хватает суммы. Пример: очки Вася 500 за лекцию"
            )
            return
        recipients, unknown, ambiguous = resolve_recipients(first, aliases)
        if ambiguous:
            await _ask_disambig(
                update,
                typed=ambiguous[0][0],
                candidate_ids=ambiguous[0][1],
                args=args,
                sender_label=sender_label,
            )
            return
        if unknown:
            await _ask_create_entity(
                update,
                unknown_name=unknown[0],
                args=args,
                by_user=by_user,
                sender_label=sender_label,
            )
            return
        if not recipients:
            await update.message.reply_text("❌ Получатели не распознаны.")
            return
        amount_arg = args[1]
        reason = " ".join(args[2:]) if len(args) > 2 else "(без причины)"

    try:
        amount_raw = parse_amount(amount_arg)
    except (ValueError, TypeError):
        await update.message.reply_text(
            f"❌ '{amount_arg}' не число. Пример: 500, +500, -100, 100к, 1м"
        )
        return

    # Разделение: люди и объекты
    object_recipients = [r[4:] for r in recipients if r.startswith("obj:")]
    member_recipients = [r for r in recipients if not r.startswith("obj:")]

    if object_recipients and member_recipients:
        await update.message.reply_text(
            "❌ В одной команде нельзя смешивать людей и объекты. Разнеси на две команды."
        )
        return

    chat_title = update.message.chat.title or "DM"

    # Ветка ОБЪЕКТА (плюсы под капом, минусы без)
    cap = cfg.get("cap", 10000)
    if object_recipients:
        if len(object_recipients) > 1:
            await update.message.reply_text(
                "❌ Объектам — по одному за раз."
            )
            return
        amount, capped = apply_cap(amount_raw, cap)
        # Не-Совет → заявка на голосование Совета (как и для людей)
        if by_user is None:
            await _create_pending(
                update,
                recipients=[f"obj:{object_recipients[0]}"],
                amount=amount,
                amount_raw=amount_raw,
                capped=capped,
                reason=reason,
                chat=chat_title,
                sender_label=sender_label,
            )
            return
        obj_name = object_recipients[0]
        data, obj = write_object_event(obj_name, amount, reason)
        _, verb_past = _verb_for_amount(amount)
        amount_abs = abs(amount)
        sign_shown = f"+{amount}" if amount >= 0 else f"-{amount_abs}"
        cap_note = (
            f"\n🕷 Округлено до потолка ({cap:,}). Заявлено: {amount_raw:,}."
            if capped
            else ""
        )
        await update.message.reply_text(
            f"✅ {verb_past} {sign_shown} → {obj['icon']} {obj['name']}\n"
            f"«{reason}»{cap_note}\n"
            f"💎 баланс объекта: {obj['balance']:,}".replace(",", " ")
        )
        return

    # Ветка ЛЮДЕЙ (с капом на плюсы)
    amount, capped = apply_cap(amount_raw, cap)

    # Если автор НЕ из Совета — заявка на голосование
    if by_user is None:
        await _create_pending(
            update,
            recipients=member_recipients,
            amount=amount,
            amount_raw=amount_raw,
            capped=capped,
            reason=reason,
            chat=chat_title,
            sender_label=sender_label,
        )
        return

    data = write_transaction(member_recipients, amount, amount_raw, capped, reason, by_user, chat_title)
    names, emojis = format_recipients(data, member_recipients)
    _, verb_past = _verb_for_amount(amount)
    amount_abs = abs(amount)
    sign_shown = f"+{amount}" if amount >= 0 else f"-{amount_abs}"
    arrow = "→" if amount >= 0 else "←"
    cap_note = (
        f"\n🕷 Округлено до потолка ({cap:,}). Заявлено: {amount_raw:,}."
        if capped
        else ""
    )
    reply = f"✅ {verb_past} {sign_shown} {arrow} {emojis} {names}\n«{reason}»{cap_note}"
    if len(member_recipients) == 1:
        bal = calc_balance(data, member_recipients[0])
        reply += f"\n💎 баланс: {bal}"
    await update.message.reply_text(reply)


# ---------- Голосование Совета (для не-членов) ----------

async def _create_pending(update, recipients, amount, amount_raw, capped, reason, chat, sender_label):
    pid = uuid.uuid4().hex[:8]
    pending = load_pending()
    pending.append({
        "id": pid,
        "by": sender_label,
        "to": recipients,
        "amount": amount,
        "amount_raw": amount_raw,
        "capped": capped,
        "reason": reason,
        "chat": chat,
        "asked_at": datetime.now().isoformat(),
    })
    save_pending(pending)

    data = load_data()
    names, emojis = format_recipients(data, recipients)
    _, verb_past = _verb_for_amount(amount)
    amount_abs = abs(amount)
    sign_shown = f"+{amount}" if amount >= 0 else f"-{amount_abs}"
    arrow = "→" if amount >= 0 else "←"
    cap_note = (
        f"\n🕷 Заявлено {amount_raw:,}, округлено до {amount:,}."
        if capped
        else ""
    )
    text = (
        f"🗳 Заявка от {sender_label}:\n\n"
        f"{verb_past} {sign_shown} {arrow} {emojis} {names}\n"
        f"«{reason}»{cap_note}\n\n"
        f"Нужен голос Совета (Уля, Таня, Толя)."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Согласен", callback_data=f"vote:approve:{pid}"),
        InlineKeyboardButton("❌ Против", callback_data=f"vote:reject:{pid}"),
    ]])
    await update.message.reply_text(text, reply_markup=kb)


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    cfg = load_config()
    voter = author_id(cfg, query.from_user)
    if voter is None:
        await query.answer("🕷 Голосовать может только Совет.", show_alert=True)
        return

    try:
        _, action, pid = query.data.split(":", 2)
    except ValueError:
        await query.answer("Битый формат.", show_alert=True)
        return

    pending = load_pending()
    p = next((x for x in pending if x["id"] == pid), None)
    if p is None:
        await query.answer("Заявка уже обработана.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    data = load_data()
    voter_m = member_by_id(data, voter)
    voter_label = f"{voter_m['emoji']} {voter_m['name']}"

    if action == "approve":
        reason = p["reason"] + f" (заявил {p['by']}, одобрил {voter_m['name']})"
        is_object = any(r.startswith("obj:") for r in p["to"])
        if is_object:
            obj_name = p["to"][0][4:]
            data, obj = write_object_event(obj_name, p["amount"], reason)
            bal_line = f"\n💎 баланс объекта: {obj['balance']:,}".replace(",", " ")
        else:
            data = write_transaction(
                p["to"], p["amount"], p["amount_raw"], p["capped"], reason, voter, p["chat"]
            )
            bal_line = ""
            if len(p["to"]) == 1:
                bal_line = f"\n💎 баланс: {calc_balance(data, p['to'][0])}"
        pending = [x for x in pending if x["id"] != pid]
        save_pending(pending)
        names, emojis = format_recipients(data, p["to"])
        _, verb_past = _verb_for_amount(p["amount"])
        amount_abs = abs(p["amount"])
        sign_shown = f"+{p['amount']}" if p["amount"] >= 0 else f"-{amount_abs}"
        arrow = "→" if p["amount"] >= 0 else "←"
        await query.edit_message_text(
            f"✅ {voter_label} одобрил(а).\n\n"
            f"{verb_past} {sign_shown} {arrow} {emojis} {names}\n"
            f"«{p['reason']}» (заявил {p['by']}){bal_line}"
        )
        await query.answer("Засчитано.")
        return

    if action == "reject":
        pending = [x for x in pending if x["id"] != pid]
        save_pending(pending)
        names, emojis = format_recipients(data, p["to"])
        await query.edit_message_text(
            f"❌ {voter_label} отклонил(а) заявку от {p['by']}\n"
            f"({p['amount']:+} → {emojis} {names} · «{p['reason']}»)"
        )
        await query.answer("Отклонено.")
        return

    await query.answer()


# ---------- Уточнение «какой именно» (disambig) ----------

async def _ask_disambig(update, typed, candidate_ids, args, sender_label):
    """Алиас указывает на нескольких — спрашиваем у автора, кого именно."""
    pid = uuid.uuid4().hex[:8]
    rec = {
        "id": pid,
        "typed": typed,
        "candidates": candidate_ids,
        "args": args,
        "by": sender_label,
        "asked_at": datetime.now().isoformat(),
    }
    pe = load_pending_entities()
    pe.append({**rec, "kind": "disambig"})
    save_pending_entities(pe)

    data = load_data()
    rows = []
    for cid in candidate_ids:
        m = next((x for x in data["members"] if x["id"] == cid), None)
        if not m:
            continue
        label = f"{m['emoji']} {m['name']}"
        if m.get("alias"):
            label += f" ({m['alias']})"
        rows.append([InlineKeyboardButton(label, callback_data=f"dis:{cid}:{pid}")])
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data=f"dis:cancel:{pid}")])
    await update.message.reply_text(
        f"❓ «{typed.capitalize()}» — кто из них?",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def disambig_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    try:
        _, choice, pid = query.data.split(":", 2)
    except ValueError:
        await query.answer("Битый формат.", show_alert=True)
        return

    pe = load_pending_entities()
    rec = next((x for x in pe if x.get("id") == pid and x.get("kind") == "disambig"), None)
    if rec is None:
        await query.answer("Заявка уже обработана.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # Только автор исходной команды может уточнить (чтобы чужие не путали)
    sender_label = rec.get("by", "")
    asker_username = (query.from_user.username or "").lower()
    if sender_label.startswith("@") and sender_label[1:].lower() != asker_username:
        await query.answer(f"Уточнить может только {sender_label}.", show_alert=True)
        return

    if choice == "cancel":
        pe = [x for x in pe if x.get("id") != pid]
        save_pending_entities(pe)
        await query.edit_message_text(f"❌ Уточнение отменено.")
        await query.answer()
        return

    data = load_data()
    m = next((x for x in data["members"] if x["id"] == choice), None)
    if not m:
        await query.answer("Такого нет.", show_alert=True)
        return

    pe = [x for x in pe if x.get("id") != pid]
    save_pending_entities(pe)

    # Подставляем выбранное имя в команду и просим повторить
    new_args = [m["name"]] + list(rec["args"][1:])
    cmd = " ".join(new_args)
    await query.edit_message_text(
        f"✅ Выбран {m['emoji']} {m['name']}.\n\n"
        f"{sender_label}, повтори команду:\n"
        f"`{cmd}`",
        parse_mode="Markdown",
    )
    await query.answer()


# ---------- Создание новой сущности на лету ----------

async def _ask_create_entity(update, unknown_name, args, by_user, sender_label):
    """Бот не нашёл получателя — предлагает Совету создать новый объект/человека."""
    if by_user is None:
        await update.message.reply_text(
            f"❌ Не знаю «{unknown_name}». Добавлять новых может только Совет (Уля, Таня, Толя)."
        )
        return
    pid = uuid.uuid4().hex[:8]
    record = {
        "id": pid,
        "name_typed": unknown_name,
        "args": args,
        "by": sender_label,
        "asked_at": datetime.now().isoformat(),
    }
    pe = load_pending_entities()
    pe.append(record)
    save_pending_entities(pe)

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ Объект", callback_data=f"ent:obj:{pid}"),
            InlineKeyboardButton("🎭 Человек", callback_data=f"ent:mem:{pid}"),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"ent:no:{pid}")],
    ])
    await update.message.reply_text(
        f"🆕 Не нашёл «{unknown_name}» в реестре.\n"
        f"Создать как:",
        reply_markup=kb,
    )


def _create_object(name):
    data = load_data()
    if any(o["name"].lower() == name.lower() for o in data.get("objects", [])):
        return data
    data.setdefault("objects", []).append({
        "name": name,
        "balance": 0,
        "icon": "🔧",
        "events": [],
    })
    save_data(data)
    return data


def _create_member(name):
    data = load_data()
    base_id = make_slug(name)
    mid = base_id
    n = 2
    existing = {m["id"] for m in data["members"]}
    while mid in existing:
        mid = f"{base_id}_{n}"
        n += 1
    data["members"].append({
        "id": mid,
        "name": name,
        "alias": None,
        "role": "Гость",
        "emoji": "🎭",
    })
    save_data(data)
    return data, mid


async def entity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    cfg = load_config()
    voter = author_id(cfg, query.from_user)
    if voter is None:
        await query.answer("Создавать может только Совет.", show_alert=True)
        return
    try:
        _, kind, pid = query.data.split(":", 2)
    except ValueError:
        await query.answer("Битый формат.", show_alert=True)
        return

    pe = load_pending_entities()
    rec = next((x for x in pe if x["id"] == pid), None)
    if rec is None:
        await query.answer("Заявка уже обработана.", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if kind == "no":
        pe = [x for x in pe if x["id"] != pid]
        save_pending_entities(pe)
        await query.edit_message_text(f"❌ Отменено. «{rec['name_typed']}» не добавлен.")
        await query.answer("Отменено.")
        return

    name = rec["name_typed"]
    pretty = name[:1].upper() + name[1:].lower()
    # сохраним и алиас в нижнем регистре, чтобы падеж сработал в след. раз
    alias_form = name.lower().lstrip("@")
    if kind == "obj":
        _create_object(pretty)
        # добавим алиас «гриффиндору» → «obj:Гриффиндор»
        _add_alias(alias_form, f"obj:{pretty}")
        kind_label = f"⚙️ Объект «{pretty}»"
    elif kind == "mem":
        _, mid = _create_member(pretty)
        _add_alias(alias_form, mid)
        kind_label = f"🎭 Человек «{pretty}»"
    else:
        await query.answer()
        return

    pe = [x for x in pe if x["id"] != pid]
    save_pending_entities(pe)

    # Подсказка: повторить команду, чтобы транзакция применилась
    original_cmd = " ".join(rec.get("args", []))
    by_label = rec.get("by", "")
    await query.edit_message_text(
        f"✅ Создан {kind_label}.\n\n"
        f"Теперь {by_label} может повторить команду:\n"
        f"`{original_cmd}`",
        parse_mode="Markdown",
    )
    await query.answer("Создано. Повтори команду.")


def _add_alias(alias_form, target):
    """Добавляет/обновляет запись в aliases.json."""
    data = json.loads(ALIASES.read_text(encoding="utf-8")) if ALIASES.exists() else {}
    data[alias_form] = target
    tmp = ALIASES.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ALIASES)


# ---------- Команды ----------

async def respect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _do_respect(update, context.args)


async def respect_ru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    m = RU_TRIGGER.match(update.message.text)
    if not m:
        return
    args = m.group(1).split()
    await _do_respect(update, args)


CLARIFY_QUESTION_RE = re.compile(
    r"(?:Кому\s+начислить|У\s+кого\s+убавить)\s+([+\-−]?\s*\d+(?:\s*(?:тыс|млн|к|k|м|m))?)\s*(?:«([^»]*)»)?",
    re.IGNORECASE,
)
CLARIFY_VERB_RE = re.compile(r"(начислить|убавить)", re.IGNORECASE)


class _ClarifyReplyFilter(filters.MessageFilter):
    def filter(self, message):
        if not message.reply_to_message:
            return False
        u = message.reply_to_message.from_user
        if not u or not u.is_bot:
            return False
        return bool(CLARIFY_QUESTION_RE.search(message.reply_to_message.text or ""))


CLARIFY_FILTER = _ClarifyReplyFilter()


async def respect_clarify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ловит ответ пользователя на вопрос бота «Кому начислить +N?»."""
    if not update.message or not update.message.text:
        return
    bot_question = update.message.reply_to_message.text or ""
    m = CLARIFY_QUESTION_RE.search(bot_question)
    if not m:
        return
    amount_str = m.group(1).replace(" ", "")
    fallback_reason = (m.group(2) or "").strip()

    # если вопрос был про «убавить» — сумма должна быть отрицательной
    verb_match = CLARIFY_VERB_RE.search(bot_question)
    if verb_match and verb_match.group(1).lower() == "убавить":
        clean = amount_str.lstrip("+-−")
        amount_str = "-" + clean

    user_text = update.message.text.strip()
    if not user_text:
        return
    # игнорируем если ответ — это снова команда (тогда обычные handlers разберут)
    if RU_TRIGGER.match(user_text) or SHORT_TRIGGER.match(user_text):
        return

    tokens = user_text.split()
    args = [tokens[0], amount_str] + tokens[1:]
    # если пользователь не указал причину в ответе — берём из вопроса
    if len(tokens) == 1 and fallback_reason:
        args = [tokens[0], amount_str] + fallback_reason.split()
    await _do_respect(update, args)


REASON_STARTERS = {
    "за", "потому", "потомучто", "после", "из-за", "изза",
    "для", "ибо", "потому-что", "т.к.", "тк",
}


async def respect_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шорткат вида «+5 очков ...» или «-100 очков Тане за пропуск»."""
    if not update.message or not update.message.text:
        return
    m = SHORT_TRIGGER.match(update.message.text)
    if not m:
        return
    amount_str = m.group(1).replace(" ", "")
    rest = (m.group(2) or "").strip()
    if not rest:
        args = [amount_str]
    else:
        tokens = rest.split()
        first = tokens[0].lower().lstrip("@").rstrip(",.!?")
        # Если первое слово начинает причину («за», «потому» и т.д.) — это причина
        # без получателя. Иначе считаем первый токен получателем (даже если он
        # неизвестен — пусть _do_respect ругнётся понятным сообщением).
        if first in REASON_STARTERS:
            args = [amount_str] + tokens
        else:
            args = [tokens[0], amount_str] + tokens[1:]
    await _do_respect(update, args)


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    aliases = build_aliases(data)
    if not context.args:
        await top(update, context)
        return
    recipients, unknown, _ambig = resolve_recipients(context.args[0], aliases)
    if unknown:
        await update.message.reply_text(f"❌ Не знаю: {', '.join(unknown)}")
        return
    lines = []
    for r in recipients:
        m = member_by_id(data, r)
        lines.append(f"{m['emoji']} {m['name']}: {calc_balance(data, r)}")
    await update.message.reply_text("\n".join(lines))


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    balances = [(m, calc_balance(data, m["id"])) for m in data["members"]]
    balances.sort(key=lambda x: -x[1])
    text = "🏆 Топ Совета:\n" + "\n".join(
        f"{i+1}. {m['emoji']} {m['name']}: {b:,}"
        for i, (m, b) in enumerate(balances[:10])
    )
    await update.message.reply_text(text)


async def ustav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cap = load_config().get("cap", 10000)
    await update.message.reply_text(
        f"🕷 Устав Совета Свидетелей Паука:\n\n"
        f"1. Начислять очки могут только Уля, Таня, Толя.\n"
        f"2. Максимум +{cap:,} очков за раз. Сверху округляется до потолка.\n"
        f"3. Убавлять можно сколько угодно — потолка на минусы нет.\n"
        f"4. Если очки крутит не Совет — нужен голос Совета (✅).\n"
        f"5. Получателя можно указать или ответить на его сообщение.\n"
        f"6. Реестр живёт в ~/Documents/Personal/Pauk-respect/"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕷 Бот Реестра Очков Уважения.\n\n"
        "НАЧИСЛИТЬ (плюс):\n"
        "  очки Вася 500 за лекцию\n"
        "  +5 очков (в ответ на сообщение)\n"
        "  очки 100к за находку (в ответ)\n"
        "  очки лёша,таня 300 за движ\n\n"
        "УБАВИТЬ (минус):\n"
        "  очки Толя -50 пропустил\n"
        "  -100 очков Тане за пропуск\n\n"
        "ОБЪЕКТЫ (без капа 10000):\n"
        "  очки Алюминий +500 за красоту\n"
        "  очки Паяльник -1м за тупость\n\n"
        "Команды:\n"
        "/balance <кого> — баланс\n"
        "/top — топ\n"
        "/ustav — правила\n\n"
        "Триггеры: очки, /очки, уважение, уважуха, /respect"
    )


def _build_app(cfg):
    app = Application.builder().token(cfg["bot_token"]).build()
    app.add_handler(CommandHandler("respect", respect))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("ustav", ustav))
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(RU_TRIGGER), respect_ru))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(SHORT_TRIGGER), respect_short))
    app.add_handler(MessageHandler(filters.TEXT & CLARIFY_FILTER, respect_clarify))
    app.add_handler(CallbackQueryHandler(vote, pattern=r"^vote:"))
    app.add_handler(CallbackQueryHandler(entity_callback, pattern=r"^ent:"))
    app.add_handler(CallbackQueryHandler(disambig_callback, pattern=r"^dis:"))
    return app


def main():
    logging.basicConfig(
        format="%(asctime)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    cfg = load_config()
    if cfg["bot_token"].startswith("ВСТАВЬ") or not cfg["bot_token"]:
        raise SystemExit("❌ В config.json не вставлен bot_token от @BotFather")

    backoff = 5
    while True:
        try:
            app = _build_app(cfg)
            print("🕷 Бот запущен. Ctrl+C чтобы остановить.")
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            print("🕷 Бот штатно завершился.")
            return
        except KeyboardInterrupt:
            print("🕷 Остановлен вручную.")
            return
        except (TimedOut, NetworkError) as e:
            logging.warning(f"Сетевая ошибка: {e!r}. Перезапуск через {backoff} сек.")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:
            logging.exception(f"Неожиданная ошибка: {e!r}. Перезапуск через {backoff} сек.")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    main()
