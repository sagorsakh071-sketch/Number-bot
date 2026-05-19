import asyncio
import re
import os
import json
import logging
import urllib.request
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ─── Configuration ───
BOT_TOKEN   = "8609593081:AAGpOlcFHf51yhTMcroZHPy7u5Qrd6JwQvw"
OWNER_ID    = 7095358778
BAILEYS_URL = os.environ.get("BAILEYS_URL", "http://localhost:8080")
WA_USER_ID  = "wa_checker_admin"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# ─── Baileys ───
# ═══════════════════════════════════════

def baileys_request(method: str, path: str, body=None) -> dict:
    url     = f"{BAILEYS_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data    = json.dumps(body).encode() if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Baileys error [{path}]: {e}")
        return {}

async def get_wa_state() -> str:
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: baileys_request("GET", f"/status?userId={WA_USER_ID}")
    )
    return "authorized" if result.get("connected") else "notAuthorized"

async def get_pairing_code(phone: str) -> str:
    loop   = asyncio.get_event_loop()
    digits = re.sub(r"\D", "", phone)
    await loop.run_in_executor(
        None, lambda: baileys_request("POST", "/start", {"userId": WA_USER_ID})
    )
    await asyncio.sleep(3)
    result = await loop.run_in_executor(
        None, lambda: baileys_request("POST", "/pair", {"phone": digits, "userId": WA_USER_ID})
    )
    return result.get("code", "")

async def check_numbers_wa(numbers: list) -> dict:
    loop       = asyncio.get_event_loop()
    results    = {}
    batch_size = 50
    for i in range(0, len(numbers), batch_size):
        batch = numbers[i:i + batch_size]
        try:
            res = await loop.run_in_executor(
                None,
                lambda b=batch: baileys_request("POST", "/check", {"numbers": b, "userId": WA_USER_ID})
            )
            results.update(res.get("results", {}))
        except Exception as e:
            logger.error(f"Batch check error: {e}")
            for n in batch:
                results[n] = None
        await asyncio.sleep(1)
    return results

async def wa_disconnect_session():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, lambda: baileys_request("POST", "/disconnect", {"userId": WA_USER_ID})
    )


# ═══════════════════════════════════════
# ─── Handlers ───
# ═══════════════════════════════════════

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 WA Status",        callback_data="wa_status")],
        [InlineKeyboardButton("🔗 Connect WhatsApp",  callback_data="wa_connect")],
        [InlineKeyboardButton("🔌 Disconnect",        callback_data="wa_disconnect")],
    ])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ Access Denied")
    state  = await get_wa_state()
    status = "🟢 Connected" if state == "authorized" else "🔴 Disconnected"
    await update.message.reply_text(
        f"🔍 *WhatsApp Number Checker*\n\n"
        f"📱 *WA Status:* {status}\n\n"
        f"*কীভাবে use করবেন:*\n"
        f"1. WhatsApp connect করুন\n"
        f"2. `.txt`, `.xlsx` বা `.xls` file পাঠান\n"
        f"3. Bot দুইটা file দিবে:\n"
        f"   ✅ `registered.txt` — WA আছে\n"
        f"   ✨ `fresh.txt` — WA নেই",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

async def cb_wa_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    state  = await get_wa_state()
    status = "🟢 Connected" if state == "authorized" else "🔴 Disconnected"
    await query.edit_message_text(
        f"📱 *WhatsApp Status:* {status}",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

async def cb_wa_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["state"] = "waiting_phone"
    await query.edit_message_text(
        "📱 *WhatsApp Connect*\n\n"
        "আপনার WhatsApp নম্বর দিন (country code সহ):\n"
        "Example: `8801712345678`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]])
    )

async def cb_wa_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await wa_disconnect_session()
    await query.edit_message_text("🔌 *WhatsApp Disconnected!*",
        parse_mode="Markdown", reply_markup=main_menu())

async def cb_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Cancelled", reply_markup=main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if context.user_data.get("state") != "waiting_phone": return
    context.user_data.clear()

    phone   = re.sub(r"\D", "", update.message.text.strip())
    if len(phone) < 8:
        return await update.message.reply_text("❌ নম্বর ভুল!")

    loading = await update.message.reply_text("⏳ Connecting WhatsApp...")
    try:
        code = await get_pairing_code(phone)
        await loading.delete()
        if not code:
            return await update.message.reply_text(
                "❌ Pairing code পাওয়া যায়নি। আবার try করুন।",
                reply_markup=main_menu()
            )
        await update.message.reply_text(
            f"📱 *Pairing Code:*\n\n"
            f"`{code}`\n\n"
            f"WhatsApp → Linked Devices → Link a Device → Enter code\n\n"
            f"Connected হলে `/start` দিন।",
            parse_mode="Markdown"
        )
    except Exception as e:
        await loading.delete()
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return

    state = await get_wa_state()
    if state != "authorized":
        return await update.message.reply_text(
            "❌ WhatsApp connected নেই!\n/start দিয়ে connect করুন।"
        )

    doc = update.message.document
    if not doc:
        return await update.message.reply_text("❌ File পাঠান।")

    fname = doc.file_name.lower()
    if not (fname.endswith(".txt") or fname.endswith(".xlsx") or fname.endswith(".xls")):
        return await update.message.reply_text("❌ শুধু `.txt`, `.xlsx` বা `.xls` file পাঠান।")

    loading = await update.message.reply_text("⏳ File processing করছি...")

    try:
        file     = await context.bot.get_file(doc.file_id)
        tmp_path = f"/tmp/{doc.file_id}_{doc.file_name}"
        await file.download_to_drive(tmp_path)
    except Exception as e:
        await loading.delete()
        return await update.message.reply_text(f"❌ File download error: {e}")

    numbers = []
    try:
        if fname.endswith(".txt"):
            with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            numbers = re.findall(r'\d{7,15}', content)

        elif fname.endswith(".xlsx"):
            from openpyxl import load_workbook
            wb = load_workbook(tmp_path, read_only=True, data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    for cell in row:
                        if cell is not None:
                            digits = re.sub(r"\D", "", str(cell).strip())
                            if 7 <= len(digits) <= 15:
                                numbers.append(digits)

        elif fname.endswith(".xls"):
            import pandas as pd
            df = pd.read_excel(tmp_path, engine="xlrd", dtype=str, header=None)
            for col in df.columns:
                for val in df[col].dropna():
                    digits = re.sub(r"\D", "", str(val))
                    if 7 <= len(digits) <= 15:
                        numbers.append(digits)

        os.remove(tmp_path)
    except Exception as e:
        await loading.delete()
        return await update.message.reply_text(f"❌ File read error: {e}")

    numbers = list(dict.fromkeys(numbers))
    if not numbers:
        await loading.delete()
        return await update.message.reply_text("❌ কোনো নম্বর পাওয়া যায়নি।")

    await loading.edit_text(
        f"✅ *{len(numbers)}* নম্বর পাওয়া গেছে।\n"
        f"⏳ WhatsApp check করছি...",
        parse_mode="Markdown"
    )

    try:
        results = await check_numbers_wa(numbers)
    except Exception as e:
        await loading.delete()
        return await update.message.reply_text(f"❌ Check error: {e}")

    registered = [n for n in numbers if results.get(n) is True]
    fresh      = [n for n in numbers if results.get(n) is False]
    failed     = [n for n in numbers if results.get(n) is None]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    await loading.edit_text(
        f"✅ *Check Complete!*\n\n"
        f"📊 Total: *{len(numbers)}*\n"
        f"✅ WA Registered: *{len(registered)}*\n"
        f"✨ Fresh (no WA): *{len(fresh)}*\n"
        f"⚠️ Failed: *{len(failed)}*",
        parse_mode="Markdown"
    )

    if registered:
        await update.message.reply_document(
            document="\n".join(registered).encode("utf-8"),
            filename=f"registered_{timestamp}.txt",
            caption=f"✅ *WA Registered* — {len(registered)} numbers",
            parse_mode="Markdown"
        )

    if fresh:
        await update.message.reply_document(
            document="\n".join(fresh).encode("utf-8"),
            filename=f"fresh_{timestamp}.txt",
            caption=f"✨ *Fresh Numbers* — {len(fresh)} numbers",
            parse_mode="Markdown"
        )

    if failed:
        await update.message.reply_document(
            document="\n".join(failed).encode("utf-8"),
            filename=f"failed_{timestamp}.txt",
            caption=f"⚠️ *Failed* — {len(failed)} numbers",
            parse_mode="Markdown"
        )


# ═══════════════════════════════════════
# ─── Main ───
# ═══════════════════════════════════════

def main():
    logger.info("🔍 WhatsApp Checker Bot Starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(cb_wa_status,     pattern="^wa_status$"))
    app.add_handler(CallbackQueryHandler(cb_wa_connect,    pattern="^wa_connect$"))
    app.add_handler(CallbackQueryHandler(cb_wa_disconnect, pattern="^wa_disconnect$"))
    app.add_handler(CallbackQueryHandler(cb_cancel,        pattern="^cancel$"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
