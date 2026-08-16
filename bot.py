"""
Earning Hub Number Bot - Python Version
All features: Numbers, WhatsApp Check, OTP, Earnings, Withdraw, 2FA, TempMail, Admin, Referral
"""

import os
import json
import re
import time
import asyncio
import logging
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

import pyotp
from aiohttp import web as aio_web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CopyTextButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

# ─── Logging ───
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Configuration ───
BOT_TOKEN = "7907217678:AAGWhPi2IwX714eL2-zmS3cGXJHvDoH5do8"
ADMIN_PASSWORD = "sadhin232134"

MAIN_CHANNEL     = "@earning_hub_official_channel"
MAIN_CHANNEL_URL = "https://t.me/earning_hub_official_channel"
MAIN_CHANNEL_ID  = -1003543718769
CHAT_GROUP       = "https://t.me/earning_hub_number_channel"
CHAT_GROUP_ID    = -1003875142184
OTP_GROUP        = "https://t.me/EarningHub_otp"
OTP_GROUP_ID     = -1003247504066

# ─── Baileys API (WhatsApp) ───
BAILEYS_URL = os.environ.get("BAILEYS_URL", "http://localhost:3000")

# ─── Data Directory ───
DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(os.path.abspath(__file__)))
logger.info(f"📁 Data Directory: {DATA_DIR}")

# ─── File Paths ───
NUMBERS_FILE        = os.path.join(DATA_DIR, "numbers.txt")
COUNTRIES_FILE      = os.path.join(DATA_DIR, "countries.json")
USERS_FILE          = os.path.join(DATA_DIR, "users.json")
SERVICES_FILE       = os.path.join(DATA_DIR, "services.json")
ACTIVE_NUMBERS_FILE = os.path.join(DATA_DIR, "active_numbers.json")
OTP_LOG_FILE        = os.path.join(DATA_DIR, "otp_log.json")
ADMINS_FILE         = os.path.join(DATA_DIR, "admins.json")
SETTINGS_FILE       = os.path.join(DATA_DIR, "settings.json")
TOTP_SECRETS_FILE   = os.path.join(DATA_DIR, "totp_secrets.json")
TEMP_MAILS_FILE     = os.path.join(DATA_DIR, "temp_mails.json")
EARNINGS_FILE       = os.path.join(DATA_DIR, "earnings.json")
WITHDRAW_FILE       = os.path.join(DATA_DIR, "withdrawals.json")
COUNTRY_PRICES_FILE = os.path.join(DATA_DIR, "country_prices.json")
WA_OWNER_FILE       = os.path.join(DATA_DIR, "wa_owner.json")
REFERRALS_FILE      = os.path.join(DATA_DIR, "referrals.json")

# ─── Default Settings ───
DEFAULT_SETTINGS = {
    "defaultNumberCount": 10,
    "cooldownSeconds": 5,
    "requireVerification": True,
    "minWithdraw": 50,
    "defaultOtpPrice": 0.25,
    "withdrawMethods": ["bKash", "Nagad"],
    "withdrawEnabled": True,
    "referralCommission": 10,
}

# ─── Load/Save Helpers ───
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {path}: {e}")
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {path}: {e}")

# ─── Load Data ───
settings       = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
if "referralCommission" not in settings:
    settings["referralCommission"] = 10

users          = load_json(USERS_FILE, {})
active_numbers = load_json(ACTIVE_NUMBERS_FILE, {})
otp_log        = load_json(OTP_LOG_FILE, [])
admins         = load_json(ADMINS_FILE, [])
totp_secrets   = load_json(TOTP_SECRETS_FILE, {})
temp_mails     = load_json(TEMP_MAILS_FILE, {})
earnings       = load_json(EARNINGS_FILE, {})
withdrawals    = load_json(WITHDRAW_FILE, [])
country_prices = load_json(COUNTRY_PRICES_FILE, {})
referrals      = load_json(REFERRALS_FILE, {})
wa_sessions    = {}

# ─── Global WhatsApp System ───
# admin একটা WA connect করলে সব user এর number check হবে
GLOBAL_WA_FILE    = os.path.join(DATA_DIR, "global_wa.json")
global_wa_data    = load_json(GLOBAL_WA_FILE, {
    "enabled":   False,   # Global WA check on/off
    "connected": False,   # Admin WA connected কিনা
    "phone":     "",      # Admin WA phone
    "uid":       "",      # Admin WA session uid
})

def save_global_wa():
    save_json(GLOBAL_WA_FILE, global_wa_data)
_tg_app        = None

countries = load_json(COUNTRIES_FILE, {
    "880": {"name": "Bangladesh",   "flag": "🇧🇩"},
    "91":  {"name": "India",        "flag": "🇮🇳"},
    "92":  {"name": "Pakistan",     "flag": "🇵🇰"},
    "977": {"name": "Nepal",        "flag": "🇳🇵"},
    "94":  {"name": "Sri Lanka",    "flag": "🇱🇰"},
    "95":  {"name": "Myanmar",      "flag": "🇲🇲"},
    "975": {"name": "Bhutan",       "flag": "🇧🇹"},
    "960": {"name": "Maldives",     "flag": "🇲🇻"},
    "66":  {"name": "Thailand",     "flag": "🇹🇭"},
    "84":  {"name": "Vietnam",      "flag": "🇻🇳"},
    "62":  {"name": "Indonesia",    "flag": "🇮🇩"},
    "60":  {"name": "Malaysia",     "flag": "🇲🇾"},
    "63":  {"name": "Philippines",  "flag": "🇵🇭"},
    "65":  {"name": "Singapore",    "flag": "🇸🇬"},
    "855": {"name": "Cambodia",     "flag": "🇰🇭"},
    "856": {"name": "Laos",         "flag": "🇱🇦"},
    "673": {"name": "Brunei",       "flag": "🇧🇳"},
    "670": {"name": "Timor-Leste",  "flag": "🇹🇱"},
    "86":  {"name": "China",        "flag": "🇨🇳"},
    "81":  {"name": "Japan",        "flag": "🇯🇵"},
    "82":  {"name": "South Korea",  "flag": "🇰🇷"},
    "886": {"name": "Taiwan",       "flag": "🇹🇼"},
    "852": {"name": "Hong Kong",    "flag": "🇭🇰"},
    "853": {"name": "Macau",        "flag": "🇲🇴"},
    "976": {"name": "Mongolia",     "flag": "🇲🇳"},
    "850": {"name": "North Korea",  "flag": "🇰🇵"},
    "7":   {"name": "Russia",       "flag": "🇷🇺"},
    "996": {"name": "Kyrgyzstan",   "flag": "🇰🇬"},
    "992": {"name": "Tajikistan",   "flag": "🇹🇯"},
    "993": {"name": "Turkmenistan", "flag": "🇹🇲"},
    "998": {"name": "Uzbekistan",   "flag": "🇺🇿"},
    "7778":{"name": "Kazakhstan",   "flag": "🇰🇿"},
    "93":  {"name": "Afghanistan",  "flag": "🇦🇫"},
    "98":  {"name": "Iran",         "flag": "🇮🇷"},
    "964": {"name": "Iraq",         "flag": "🇮🇶"},
    "963": {"name": "Syria",        "flag": "🇸🇾"},
    "961": {"name": "Lebanon",      "flag": "🇱🇧"},
    "962": {"name": "Jordan",       "flag": "🇯🇴"},
    "972": {"name": "Israel",       "flag": "🇮🇱"},
    "970": {"name": "Palestine",    "flag": "🇵🇸"},
    "966": {"name": "Saudi Arabia", "flag": "🇸🇦"},
    "971": {"name": "UAE",          "flag": "🇦🇪"},
    "974": {"name": "Qatar",        "flag": "🇶🇦"},
    "973": {"name": "Bahrain",      "flag": "🇧🇭"},
    "965": {"name": "Kuwait",       "flag": "🇰🇼"},
    "968": {"name": "Oman",         "flag": "🇴🇲"},
    "967": {"name": "Yemen",        "flag": "🇾🇪"},
    "994": {"name": "Azerbaijan",   "flag": "🇦🇿"},
    "374": {"name": "Armenia",      "flag": "🇦🇲"},
    "995": {"name": "Georgia",      "flag": "🇬🇪"},
    "44":  {"name": "UK",           "flag": "🇬🇧"},
    "49":  {"name": "Germany",      "flag": "🇩🇪"},
    "33":  {"name": "France",       "flag": "🇫🇷"},
    "39":  {"name": "Italy",        "flag": "🇮🇹"},
    "34":  {"name": "Spain",        "flag": "🇪🇸"},
    "31":  {"name": "Netherlands",  "flag": "🇳🇱"},
    "32":  {"name": "Belgium",      "flag": "🇧🇪"},
    "41":  {"name": "Switzerland",  "flag": "🇨🇭"},
    "43":  {"name": "Austria",      "flag": "🇦🇹"},
    "351": {"name": "Portugal",     "flag": "🇵🇹"},
    "353": {"name": "Ireland",      "flag": "🇮🇪"},
    "352": {"name": "Luxembourg",   "flag": "🇱🇺"},
    "356": {"name": "Malta",        "flag": "🇲🇹"},
    "357": {"name": "Cyprus",       "flag": "🇨🇾"},
    "45":  {"name": "Denmark",      "flag": "🇩🇰"},
    "46":  {"name": "Sweden",       "flag": "🇸🇪"},
    "47":  {"name": "Norway",       "flag": "🇳🇴"},
    "358": {"name": "Finland",      "flag": "🇫🇮"},
    "354": {"name": "Iceland",      "flag": "🇮🇸"},
    "370": {"name": "Lithuania",    "flag": "🇱🇹"},
    "371": {"name": "Latvia",       "flag": "🇱🇻"},
    "372": {"name": "Estonia",      "flag": "🇪🇪"},
    "30":  {"name": "Greece",       "flag": "🇬🇷"},
    "48":  {"name": "Poland",       "flag": "🇵🇱"},
    "420": {"name": "Czech Rep.",   "flag": "🇨🇿"},
    "421": {"name": "Slovakia",     "flag": "🇸🇰"},
    "36":  {"name": "Hungary",      "flag": "🇭🇺"},
    "40":  {"name": "Romania",      "flag": "🇷🇴"},
    "359": {"name": "Bulgaria",     "flag": "🇧🇬"},
    "385": {"name": "Croatia",      "flag": "🇭🇷"},
    "381": {"name": "Serbia",       "flag": "🇷🇸"},
    "387": {"name": "Bosnia",       "flag": "🇧🇦"},
    "386": {"name": "Slovenia",     "flag": "🇸🇮"},
    "382": {"name": "Montenegro",   "flag": "🇲🇪"},
    "389": {"name": "N. Macedonia", "flag": "🇲🇰"},
    "355": {"name": "Albania",      "flag": "🇦🇱"},
    "373": {"name": "Moldova",      "flag": "🇲🇩"},
    "380": {"name": "Ukraine",      "flag": "🇺🇦"},
    "375": {"name": "Belarus",      "flag": "🇧🇾"},
    "383": {"name": "Kosovo",       "flag": "🇽🇰"},
    "1":   {"name": "USA/Canada",   "flag": "🇺🇸"},
    "52":  {"name": "Mexico",       "flag": "🇲🇽"},
    "506": {"name": "Costa Rica",   "flag": "🇨🇷"},
    "502": {"name": "Guatemala",    "flag": "🇬🇹"},
    "504": {"name": "Honduras",     "flag": "🇭🇳"},
    "503": {"name": "El Salvador",  "flag": "🇸🇻"},
    "505": {"name": "Nicaragua",    "flag": "🇳🇮"},
    "507": {"name": "Panama",       "flag": "🇵🇦"},
    "53":  {"name": "Cuba",         "flag": "🇨🇺"},
    "509": {"name": "Haiti",        "flag": "🇭🇹"},
    "501": {"name": "Belize",       "flag": "🇧🇿"},
    "55":  {"name": "Brazil",       "flag": "🇧🇷"},
    "54":  {"name": "Argentina",    "flag": "🇦🇷"},
    "56":  {"name": "Chile",        "flag": "🇨🇱"},
    "57":  {"name": "Colombia",     "flag": "🇨🇴"},
    "51":  {"name": "Peru",         "flag": "🇵🇪"},
    "58":  {"name": "Venezuela",    "flag": "🇻🇪"},
    "593": {"name": "Ecuador",      "flag": "🇪🇨"},
    "591": {"name": "Bolivia",      "flag": "🇧🇴"},
    "595": {"name": "Paraguay",     "flag": "🇵🇾"},
    "598": {"name": "Uruguay",      "flag": "🇺🇾"},
    "592": {"name": "Guyana",       "flag": "🇬🇾"},
    "597": {"name": "Suriname",     "flag": "🇸🇷"},
    "20":  {"name": "Egypt",        "flag": "🇪🇬"},
    "213": {"name": "Algeria",      "flag": "🇩🇿"},
    "212": {"name": "Morocco",      "flag": "🇲🇦"},
    "216": {"name": "Tunisia",      "flag": "🇹🇳"},
    "218": {"name": "Libya",        "flag": "🇱🇾"},
    "249": {"name": "Sudan",        "flag": "🇸🇩"},
    "234": {"name": "Nigeria",      "flag": "🇳🇬"},
    "233": {"name": "Ghana",        "flag": "🇬🇭"},
    "221": {"name": "Senegal",      "flag": "🇸🇳"},
    "225": {"name": "Côte d'Ivoire","flag": "🇨🇮"},
    "222": {"name": "Mauritania",   "flag": "🇲🇷"},
    "223": {"name": "Mali",         "flag": "🇲🇱"},
    "226": {"name": "Burkina Faso", "flag": "🇧🇫"},
    "227": {"name": "Niger",        "flag": "🇳🇪"},
    "228": {"name": "Togo",         "flag": "🇹🇬"},
    "229": {"name": "Benin",        "flag": "🇧🇯"},
    "232": {"name": "Sierra Leone", "flag": "🇸🇱"},
    "231": {"name": "Liberia",      "flag": "🇱🇷"},
    "224": {"name": "Guinea",       "flag": "🇬🇳"},
    "245": {"name": "Guinea-Bissau","flag": "🇬🇼"},
    "238": {"name": "Cape Verde",   "flag": "🇨🇻"},
    "237": {"name": "Cameroon",     "flag": "🇨🇲"},
    "243": {"name": "DR Congo",     "flag": "🇨🇩"},
    "242": {"name": "Congo",        "flag": "🇨🇬"},
    "240": {"name": "Eq. Guinea",   "flag": "🇬🇶"},
    "241": {"name": "Gabon",        "flag": "🇬🇦"},
    "236": {"name": "CAR",          "flag": "🇨🇫"},
    "235": {"name": "Chad",         "flag": "🇹🇩"},
    "254": {"name": "Kenya",        "flag": "🇰🇪"},
    "255": {"name": "Tanzania",     "flag": "🇹🇿"},
    "256": {"name": "Uganda",       "flag": "🇺🇬"},
    "251": {"name": "Ethiopia",     "flag": "🇪🇹"},
    "252": {"name": "Somalia",      "flag": "🇸🇴"},
    "253": {"name": "Djibouti",     "flag": "🇩🇯"},
    "257": {"name": "Burundi",      "flag": "🇧🇮"},
    "250": {"name": "Rwanda",       "flag": "🇷🇼"},
    "291": {"name": "Eritrea",      "flag": "🇪🇷"},
    "27":  {"name": "South Africa", "flag": "🇿🇦"},
    "258": {"name": "Mozambique",   "flag": "🇲🇿"},
    "260": {"name": "Zambia",       "flag": "🇿🇲"},
    "263": {"name": "Zimbabwe",     "flag": "🇿🇼"},
    "267": {"name": "Botswana",     "flag": "🇧🇼"},
    "264": {"name": "Namibia",      "flag": "🇳🇦"},
    "266": {"name": "Lesotho",      "flag": "🇱🇸"},
    "268": {"name": "Eswatini",     "flag": "🇸🇿"},
    "244": {"name": "Angola",       "flag": "🇦🇴"},
    "261": {"name": "Madagascar",   "flag": "🇲🇬"},
    "230": {"name": "Mauritius",    "flag": "🇲🇺"},
    "248": {"name": "Seychelles",   "flag": "🇸🇨"},
    "61":  {"name": "Australia",    "flag": "🇦🇺"},
    "64":  {"name": "New Zealand",  "flag": "🇳🇿"},
    "679": {"name": "Fiji",         "flag": "🇫🇯"},
    "675": {"name": "Papua NG",     "flag": "🇵🇬"},
    "677": {"name": "Solomon Is.",  "flag": "🇸🇧"},
    "678": {"name": "Vanuatu",      "flag": "🇻🇺"},
    "676": {"name": "Tonga",        "flag": "🇹🇴"},
    "685": {"name": "Samoa",        "flag": "🇼🇸"},
    "686": {"name": "Kiribati",     "flag": "🇰🇮"},
    "688": {"name": "Tuvalu",       "flag": "🇹🇻"},
    "692": {"name": "Marshall Is.", "flag": "🇲🇭"},
    "691": {"name": "Micronesia",   "flag": "🇫🇲"},
    "680": {"name": "Palau",        "flag": "🇵🇼"},
})

services = load_json(SERVICES_FILE, {
    "whatsapp":    {"name": "WhatsApp",    "icon": "📱"},
    "telegram":    {"name": "Telegram",    "icon": "✈️"},
    "facebook":    {"name": "Facebook",    "icon": "📘"},
    "instagram":   {"name": "Instagram",   "icon": "📸"},
    "google":      {"name": "Google",      "icon": "🔍"},
    "verification":{"name": "Verification","icon": "✅"},
    "other":       {"name": "Other",       "icon": "🔧"},
})

numbers_by_cs = {}

def load_numbers():
    global numbers_by_cs
    numbers_by_cs = {}
    if not os.path.exists(NUMBERS_FILE):
        return
    try:
        with open(NUMBERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        num, cc, svc = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    elif len(parts) == 2:
                        num, cc, svc = parts[0].strip(), parts[1].strip(), "other"
                    else:
                        continue
                else:
                    num = line
                    cc  = get_country_code_from_number(num)
                    svc = "other"
                if not re.match(r"^\d{10,15}$", num):
                    continue
                if not cc:
                    continue
                numbers_by_cs.setdefault(cc, {}).setdefault(svc, [])
                if num not in numbers_by_cs[cc][svc]:
                    numbers_by_cs[cc][svc].append(num)
        total = sum(len(nums) for cc in numbers_by_cs.values() for nums in cc.values())
        logger.info(f"✅ Loaded {total} numbers")
    except Exception as e:
        logger.error(f"Error loading numbers: {e}")

def save_numbers():
    try:
        lines = []
        for cc, svcs in numbers_by_cs.items():
            for svc, nums in svcs.items():
                for num in nums:
                    lines.append(f"{num}|{cc}|{svc}")
        with open(NUMBERS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        logger.error(f"Error saving numbers: {e}")

load_numbers()

def save_settings():    save_json(SETTINGS_FILE, settings)
def save_referrals():   save_json(REFERRALS_FILE, referrals)

async def safe_edit(query, text, **kwargs):
    try:
        await query.edit_message_text(text, **kwargs)
    except Exception as e:
        if "not modified" in str(e).lower():
            pass
        else:
            raise

async def async_save_numbers():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_numbers)

async def async_save_users():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_users)

async def async_save_active():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_active)

async def async_save_otp_log():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_otp_log)

async def async_save_earnings():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_earnings)

async def async_save_withdrawals():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_withdrawals)

async def async_save_referrals():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_referrals)

def save_users():       save_json(USERS_FILE, users)
def save_active():
    save_json(ACTIVE_NUMBERS_FILE, active_numbers)
    rebuild_suffix_index()
def save_otp_log():     save_json(OTP_LOG_FILE, otp_log[-1000:])
def save_admins():      save_json(ADMINS_FILE, admins)
def save_totp():        save_json(TOTP_SECRETS_FILE, totp_secrets)
def save_temp_mails():  save_json(TEMP_MAILS_FILE, temp_mails)
def save_earnings():    save_json(EARNINGS_FILE, earnings)
def save_withdrawals(): save_json(WITHDRAW_FILE, withdrawals)
def save_cp():          save_json(COUNTRY_PRICES_FILE, country_prices)
def save_countries():   save_json(COUNTRIES_FILE, countries)
def save_services():    save_json(SERVICES_FILE, services)

if not os.path.exists(SETTINGS_FILE):
    save_settings()
if not os.path.exists(COUNTRIES_FILE):
    save_countries()
if not os.path.exists(SERVICES_FILE):
    save_services()

def is_admin(user_id: str) -> bool:
    return str(user_id) in admins

def get_country_code_from_number(num: str) -> str:
    s = str(num)
    for l in [3, 2, 1]:
        if s[:l] in countries:
            return s[:l]
    return ""

def get_otp_price(cc: str) -> float:
    return country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))

def get_user_earnings(uid: str) -> dict:
    uid = str(uid)
    if uid not in earnings:
        earnings[uid] = {
            "balance": 0,
            "totalEarned": 0,
            "otpCount": 0,
            "referralEarnings": 0,
        }
    if "referralEarnings" not in earnings[uid]:
        earnings[uid]["referralEarnings"] = 0
    return earnings[uid]

def get_referral_link(uid: str, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start=ref_{uid}"

async def add_earning(uid: str, cc: str) -> float:
    uid = str(uid)
    price = get_otp_price(cc)
    e = get_user_earnings(uid)
    e["balance"]     = round(e["balance"] + price, 2)
    e["totalEarned"] = round(e["totalEarned"] + price, 2)
    e["otpCount"]    = e.get("otpCount", 0) + 1

    referrer_id = users.get(uid, {}).get("referredBy")
    if referrer_id and str(referrer_id) != uid:
        commission_pct = settings.get("referralCommission", 10) / 100
        commission = round(price * commission_pct, 4)
        commission = round(commission, 2)
        if commission > 0:
            re_ = get_user_earnings(str(referrer_id))
            re_["balance"]          = round(re_["balance"] + commission, 2)
            re_["totalEarned"]      = round(re_["totalEarned"] + commission, 2)
            re_["referralEarnings"] = round(re_.get("referralEarnings", 0) + commission, 2)
            logger.info(f"💸 Referral commission {commission:.2f} taka → uid={referrer_id} (from uid={uid})")

    await async_save_earnings()
    return price

def get_time_ago(dt_str: str) -> str:
    try:
        if not dt_str:
            return "unknown"
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        secs = int((now - dt).total_seconds())
        if secs < 0:    return "just now"
        if secs < 60:   return f"{secs} seconds ago"
        if secs < 3600: return f"{secs // 60} minutes ago"
        if secs < 86400:return f"{secs // 3600} hours ago"
        return f"{secs // 86400} days ago"
    except Exception as e:
        logger.warning(f"get_time_ago error for '{dt_str}': {e}")
        return "unknown"

def get_available_countries_for_service(svc: str) -> list:
    return [cc for cc, svcs in numbers_by_cs.items()
            if svc in svcs and svcs[svc] and cc in countries]

async def get_multiple_numbers(cc: str, svc: str, uid: str, count: int) -> list:
    if cc not in numbers_by_cs or svc not in numbers_by_cs[cc]:
        return []
    pool = numbers_by_cs[cc][svc]
    if not pool:
        return []
    give = min(count, len(pool))
    nums = pool[:give]
    numbers_by_cs[cc][svc] = pool[give:]
    now = datetime.now(timezone.utc).isoformat()
    for n in nums:
        active_numbers[n] = {
            "userId": str(uid), "countryCode": cc, "service": svc,
            "assignedAt": now, "lastOTP": None, "otpCount": 0
        }
    await async_save_numbers()
    save_active()  # sync save — সাথে সাথে file এ লেখে
    await async_save_active()
    return nums

def extract_phone_from_text(text: str):
    m = re.search(r"\+?(\d{10,15})", text)
    return m.group(1) if m else None

# ─── Fast suffix index for active number matching ───
_suffix_index: dict = {}  # { last_8_digits: number }

def rebuild_suffix_index():
    global _suffix_index
    _suffix_index = {}
    for n in active_numbers:
        clean = n.lstrip("0")
        for l in [8, 7, 6]:
            if len(clean) >= l:
                key = clean[-l:]
                if key not in _suffix_index:
                    _suffix_index[key] = n

def find_active_number(panel_number: str):
    """Panel এর number দিয়ে active_numbers এ fast match করো"""
    clean = re.sub(r"\D", "", panel_number).lstrip("0")
    # Direct match
    if clean in active_numbers:
        return clean
    # Suffix match via index
    for l in [8, 7, 6]:
        if len(clean) >= l:
            key = clean[-l:]
            if key in _suffix_index:
                return _suffix_index[key]
    return None
    # ── Strategy 1: Full number direct match ──
    for num in list(active_numbers.keys()):
        if num in text:
            return num

    # ── Strategy 2: SPYX mask — "4917SPYX5576" (masdar OTP bot format) ──
    spyx_patterns = re.findall(r'(\d{3,})[A-Za-z]{2,8}(\d{2,})', text)
    for prefix, suffix in spyx_patterns:
        for num in list(active_numbers.keys()):
            if num.startswith(prefix) and num.endswith(suffix):
                return num

    # ── Strategy 3: *** mask — "7921***3002" ──
    masked_patterns = re.findall(r'(\d{3,})\*+(\d{2,})', text)
    for prefix, suffix in masked_patterns:
        for num in list(active_numbers.keys()):
            if num.startswith(prefix) and num.endswith(suffix):
                return num

    # ── Strategy 4: Number field prefix match ──
    num_field = re.search(r'[Nn]umber[:\s]+(\d{4,})', text)
    if num_field:
        prefix = num_field.group(1)
        for num in list(active_numbers.keys()):
            if num.startswith(prefix):
                return num

    # ── Strategy 5: Last 8/6 digits fallback ──
    for num in list(active_numbers.keys()):
        if num[-8:] in text:
            return num
    for num in list(active_numbers.keys()):
        if num[-6:] in text:
            return num

    # ── Strategy 6: Last 4 digits with any mask ──
    for num in list(active_numbers.keys()):
        suffix4 = num[-4:]
        if re.search(r'[A-Za-z\*]+' + re.escape(suffix4) + r'\b', text):
            return num

    return None

def extract_otp(text: str):
    cleaned = re.sub(r'\b(19|20)\d{2}[-/]\d{2}[-/]\d{2}(?:[T\s]\d{2}:\d{2}:\d{2})?\b', '', text)
    cleaned = re.sub(r'\b(19|20)\d{2}\b', '', cleaned)
    patterns = [
        r'OTP\s*Code[:\s]+(\d{4,8})',
        r'\b[A-Z]-(\d{4,8})\b',
        r'(?:otp|code|pin|verification|verify|token)[^\d]{0,10}(\d{4,8})',
        r'(?:is|has|:)\s*(\d{4,8})\b',
        r'\b(\d{6})\b',
        r'\b(\d{4})\b',
    ]
    for p in patterns:
        m = re.search(p, cleaned, re.IGNORECASE)
        if m and 4 <= len(m.group(1)) <= 8:
            return m.group(1)
    return None

# ─── HTTP OTP Server ───
HTTP_PORT = int(os.environ.get("HTTP_PORT", 8080))

async def http_otp_handler(request: aio_web.Request) -> aio_web.Response:
    global _tg_app
    try:
        data      = await request.json()
        number    = re.sub(r"\D", "", str(data.get("number", ""))).lstrip("0")
        otp_code  = str(data.get("otp", "")).strip().replace("-", "").replace(" ", "")
        service   = str(data.get("service", "other")).lower().strip()

        if not number:
            return aio_web.json_response({"ok": False, "error": "number required"}, status=400)

        # active_numbers এ match খোঁজো — leading zeros ছাড়া
        matched_number = None
        if number in active_numbers:
            matched_number = number
        else:
            # OTP bot ভিন্ন format এ পাঠাতে পারে, তাই suffix match করো
            for n in active_numbers:
                if n.endswith(number[-8:]) or number.endswith(n[-8:]):
                    matched_number = n
                    break

        if not matched_number:
            logger.warning(f"⚠️ HTTP /otp: number {number} not in active_numbers")
            return aio_web.json_response({"ok": False, "error": "number not active"}, status=404)

        an_data = active_numbers[matched_number]
        uid     = an_data["userId"]
        cc      = an_data.get("countryCode", "")

        otp_key = f"http_{otp_code}_{matched_number}"
        if an_data.get("lastOTP") == otp_key:
            return aio_web.json_response({"ok": True, "info": "duplicate"})
        an_data["lastOTP"]  = otp_key
        an_data["otpCount"] = an_data.get("otpCount", 0) + 1
        save_active()

        earned  = await add_earning(uid, cc)
        balance = get_user_earnings(uid)["balance"]
        svc     = services.get(service, {"icon": "📱", "name": service.capitalize()})
        country = countries.get(cc, {"flag": "🌍", "name": cc})

        notify = (
            f"📨 *OTP Received!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"📞 *Number:* `+{matched_number}`\n"
        )
        if otp_code:
            notify += f"\n🔑 *OTP Code:* `{otp_code}`\n"
        notify += f"\n💵 *+{earned:.2f} taka earned!*\n💰 *Balance: {balance:.2f} taka*"

        if _tg_app:
            try:
                await _tg_app.bot.send_message(int(uid), notify, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"HTTP OTP notify send error: {e}")

        otp_log.append({
            "phoneNumber": matched_number, "userId": uid, "countryCode": cc,
            "service": service, "otpCode": otp_code, "earned": earned,
            "messageId": None, "delivered": True,
            "source": "http_api",
            "timestamp": datetime.now().isoformat()
        })
        save_otp_log()

        logger.info(f"✅ HTTP /otp processed: +{matched_number} otp={otp_code} uid={uid}")
        return aio_web.json_response({"ok": True, "earned": earned, "balance": balance})

    except Exception as e:
        logger.error(f"HTTP /otp handler error: {e}")
        return aio_web.json_response({"ok": False, "error": str(e)}, status=500)

async def start_http_server():
    http_app = aio_web.Application()
    http_app.router.add_post("/otp", http_otp_handler)
    http_app.router.add_get("/health", lambda r: aio_web.json_response({"ok": True}))
    runner = aio_web.AppRunner(http_app)
    await runner.setup()
    site = aio_web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    logger.info(f"🌐 HTTP OTP server started → port {HTTP_PORT}")

def generate_totp(secret: str):
    try:
        clean = secret.replace(" ", "").replace("-", "").upper()
        missing_padding = (8 - len(clean) % 8) % 8
        if missing_padding:
            clean += "=" * missing_padding
        totp = pyotp.TOTP(clean)
        token = totp.now()
        remaining = 30 - (int(time.time()) % 30)
        return {"token": token, "timeRemaining": remaining}
    except Exception as e:
        logger.error(f"generate_totp error (secret_len={len(secret)}): {e}")
        return None

# ─── Baileys API (WhatsApp) Helpers ───
_green_state  = {"authorized": False}
_green_owner  = load_json(WA_OWNER_FILE, {"uid": None})
_wa_pair_lock = None

def save_green_owner():
    save_json(WA_OWNER_FILE, _green_owner)

def baileys_request(method: str, path: str, body=None) -> dict:
    url     = f"{BAILEYS_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data    = json.dumps(body).encode() if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Baileys API error [{path}]: {e}")
        return {}

async def green_get_state(uid: str = None) -> str:
    loop   = asyncio.get_event_loop()
    path   = f"/status?userId={uid}" if uid else "/status?userId=global"
    result = await loop.run_in_executor(None, lambda: baileys_request("GET", path))
    if result.get("connected"):
        return "authorized"
    return "notAuthorized"


async def green_api_monitor(app):
    logger.info("🟢 Baileys monitor started")
    fail_counts = {}

    while True:
        await asyncio.sleep(30)
        try:
            for uid in list(wa_sessions.keys()):
                if not wa_sessions.get(uid, {}).get("connected"):
                    continue
                try:
                    state = await green_get_state(uid)
                    if state != "authorized":
                        fail_counts[uid] = fail_counts.get(uid, 0) + 1
                        logger.warning(f"⚠️ Baileys: WA check fail #{fail_counts[uid]} uid={uid}")
                        if fail_counts[uid] >= 5:
                            fail_counts.pop(uid, None)
                            wa_sessions.pop(uid, None)
                            logger.warning(f"⚠️ Baileys: WhatsApp disconnected! uid={uid}")
                            try:
                                await app.bot.send_message(
                                    int(uid),
                                    "⚠️ *WhatsApp Disconnected!*\n\n"
                                    "তোমার WhatsApp থেকে bot disconnect হয়েছে।\n"
                                    "আবার connect করতে নিচের button চাপো।",
                                    parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", api_kwargs={"style": "primary"})
                                    ]])
                                )
                            except Exception as e:
                                logger.error(f"Disconnect notify error uid={uid}: {e}")
                    else:
                        fail_counts.pop(uid, None)
                except Exception as e:
                    logger.error(f"Baileys monitor error uid={uid}: {e}")
        except Exception as e:
            logger.error(f"Baileys monitor loop error: {e}")

async def send_otp_to_group(otp_code: str, group_msg: str, retries: int = 5):
    """Direct HTTP দিয়ে OTP group এ পাঠাও — PTB rate limit এড়াতে"""
    import aiohttp as _aiohttp
    url     = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    OTP_GROUP_ID,
        "text":       group_msg,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": str(otp_code), "copy_text": {"text": str(otp_code)}}],
                [
                    {"text": "☎️ Numbers", "url": "https://t.me/EARNING_HUB_NUMBER_BOT"},
                    {"text": "💬 Chats",   "url": "https://t.me/earning_hub_otp_group"},
                ]
            ]
        }
    }
    for attempt in range(1, retries + 1):
        try:
            async with _aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, timeout=15) as r:
                    if r.status == 200:
                        return True
                    elif r.status == 429:
                        data       = await r.json()
                        retry_after = data.get("parameters", {}).get("retry_after", 10)
                        logger.warning(f"⚠️ OTP Group Flood Wait {retry_after}s")
                        await asyncio.sleep(retry_after + 1)
                        continue
                    else:
                        logger.error(f"❌ OTP group send failed ({r.status})")
                        return False
        except Exception as e:
            logger.error(f"❌ OTP group send error: {e}")
            if attempt < retries:
                await asyncio.sleep(3)
    return False
    logger.info("🟢 Baileys monitor started")
    fail_counts = {}  # { uid: fail_count }

    while True:
        await asyncio.sleep(30)
        try:
            for uid in list(wa_sessions.keys()):
                if not wa_sessions.get(uid, {}).get("connected"):
                    continue
                try:
                    state = await green_get_state(uid)
                    if state != "authorized":
                        fail_counts[uid] = fail_counts.get(uid, 0) + 1
                        logger.warning(f"⚠️ Baileys: WA check fail #{fail_counts[uid]} uid={uid}")
                        # ৫ বার fail হলে disconnect বলবে
                        if fail_counts[uid] >= 5:
                            fail_counts.pop(uid, None)
                            wa_sessions.pop(uid, None)
                            logger.warning(f"⚠️ Baileys: WhatsApp disconnected! uid={uid}")
                            try:
                                await app.bot.send_message(
                                    int(uid),
                                    "⚠️ *WhatsApp Disconnected!*\n\n"
                                    "তোমার WhatsApp থেকে bot disconnect হয়েছে।\n"
                                    "আবার connect করতে নিচের button চাপো।",
                                    parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", api_kwargs={"style": "primary"})
                                    ]])
                                )
                            except Exception as e:
                                logger.error(f"Disconnect notify error uid={uid}: {e}")
                    else:
                        fail_counts.pop(uid, None)
                except Exception as e:
                    logger.error(f"Baileys monitor error uid={uid}: {e}")
        except Exception as e:
            logger.error(f"Baileys monitor loop error: {e}")

async def get_wa_pairing_code(phone: str, user_id: str) -> str:
    digits = re.sub(r"\D", "", phone)
    logger.info(f"📱 Baileys pairing for: +{digits} uid={user_id}")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: baileys_request("POST", "/start", {"userId": user_id})
    )
    await asyncio.sleep(3)
    result = await loop.run_in_executor(
        None,
        lambda: baileys_request("POST", "/pair", {"phone": digits, "userId": user_id})
    )
    logger.info(f"Baileys pairing result: {result}")
    if result.get("connected"):
        raise Exception("WhatsApp ইতিমধ্যে connected আছে।")
    if result.get("code"):
        code  = str(result["code"])
        clean = re.sub(r"[^A-Z0-9]", "", code.upper())
        if len(clean) >= 8:
            return f"{clean[:4]}-{clean[4:8]}"
        return code
    raise Exception(
        result.get("error") or
        "Pairing code পাওয়া যায়নি। Baileys server চালু আছে কিনা দেখো।"
    )

async def monitor_wa_connection(uid: str, context):
    logger.info(f"🔍 Waiting for WA auth: {uid}")
    for _ in range(60):
        await asyncio.sleep(5)
        try:
            state = await green_get_state(uid)
            if state == "authorized":
                wa_sessions[uid] = {"connected": True}
                logger.info(f"✅ WA connected: uid={uid}")
                try:
                    await context.bot.send_message(
                        int(uid),
                        "✅ *WhatsApp Connected!*\n\n"
                        "🟢 তোমার WhatsApp সফলভাবে connect হয়েছে।\n"
                        "এখন numbers assign হলে WA check দেখাবে।\n\n"
                        "Disconnect করতে নিচের বাটন চাপো:",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔴 Logout / Disconnect", callback_data="wa_disconnect", api_kwargs={"style": "success"})],
                            [InlineKeyboardButton("📊 Check Status", callback_data="wa_status", api_kwargs={"style": "danger"})],
                        ])
                    )
                except:
                    pass
                break
        except Exception as e:
            logger.warning(f"monitor_wa_connection error: {e}")

async def check_wa_number(phone: str, user_id: str):
    # ── Global WA enabled হলে admin WA দিয়ে check করো ──
    effective_uid = user_id
    if global_wa_data.get("enabled") and global_wa_data.get("connected"):
        effective_uid = global_wa_data.get("uid", user_id)

    if not wa_sessions.get(effective_uid, {}).get("connected"):
        state = await green_get_state(effective_uid)
        if state != "authorized":
            return None
        wa_sessions[effective_uid] = {"connected": True}
    digits = re.sub(r"\D", "", phone)
    loop   = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: baileys_request("POST", "/check", {"numbers": [digits], "userId": effective_uid})
        )
        logger.info(f"📱 WA check +{digits}: {result}")
        results = result.get("results", {})
        val = results.get(digits)
        if val is True:  return True
        if val is False: return False
        return None
    except Exception as e:
        logger.warning(f"check_wa_number error +{digits}: {e}")
        return None

# ─── Mail.tm API ───
def mailtm_request(method: str, path: str, body=None, token=None):
    url = f"https://api.mail.tm{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            return err
        except:
            return None
    except Exception as e:
        logger.error(f"Mail.tm error: {e}")
        return None

async def mailtm_request_async(method: str, path: str, body=None, token=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: mailtm_request(method, path, body, token)
    )

def random_str(n: int, chars="abcdefghijklmnopqrstuvwxyz0123456789") -> str:
    import random
    return "".join(random.choice(chars) for _ in range(n))

async def create_fresh_email():
    try:
        domains = await mailtm_request_async("GET", "/domains?page=1")
        domain_list = domains if isinstance(domains, list) else (domains or {}).get("hydra:member", [])
        if not domain_list:
            return None
        domain = domain_list[0]["domain"]
        username = random_str(12)
        password = random_str(16, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        address  = f"{username}@{domain}"
        account = None
        for _ in range(3):
            account = await mailtm_request_async("POST", "/accounts", {"address": address, "password": password})
            if account and account.get("id"):
                break
            await asyncio.sleep(3)
        if not account or not account.get("id"):
            return None
        token_res = await mailtm_request_async("POST", "/token", {"address": address, "password": password})
        if not token_res or not token_res.get("token"):
            return None
        return {
            "address":   address,
            "sidToken":  token_res["token"],
            "provider":  "mailtm",
            "createdAt": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"createFreshEmail error: {e}")
        return None

async def get_email_inbox(email_obj: dict):
    try:
        data = await mailtm_request_async("GET", "/messages?page=1", token=email_obj.get("sidToken"))
        msgs = data if isinstance(data, list) else (data or {}).get("hydra:member", [])
        return [{"id": m.get("id"), "from": (m.get("from") or {}).get("address", ""),
                 "subject": m.get("subject", ""), "date": m.get("createdAt", "")} for m in msgs]
    except:
        return []

async def get_email_message(msg_id: str, email_obj: dict) -> str:
    try:
        data = await mailtm_request_async("GET", f"/messages/{msg_id}", token=email_obj.get("sidToken"))
        if not data:
            return ""
        text = data.get("text", "")
        html = (data.get("html") or [""])[0]
        raw = text or re.sub(r"<[^>]*>", " ", html)
        return re.sub(r"\s+", " ", raw).strip()
    except:
        return ""

# ─── Membership Check ───
async def check_membership(user_id: int, app) -> dict:
    result = {"mainChannel": False, "chatGroup": False, "otpGroup": False, "allJoined": False}
    try:
        m = await app.bot.get_chat_member(MAIN_CHANNEL_ID, user_id)
        result["mainChannel"] = m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Main channel check: {e}")
    try:
        m = await app.bot.get_chat_member(CHAT_GROUP_ID, user_id)
        result["chatGroup"] = m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"Chat group check: {e}")
    try:
        m = await app.bot.get_chat_member(OTP_GROUP_ID, user_id)
        result["otpGroup"] = m.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.warning(f"OTP group check: {e}")
    result["allJoined"] = result["mainChannel"] and result["chatGroup"] and result["otpGroup"]
    return result

# ─── Keyboards ───
def main_keyboard():
    return ReplyKeyboardMarkup([
        ["☎️ Get Number", "📧 Get Tempmail"],
        ["🔐 2FA", "💰 Balances"],
        ["💸 Withdraw", "👥 Referral"],
        ["💬 Support"]
    ], resize_keyboard=True)

def verify_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ 📢 Main Channel", url=MAIN_CHANNEL_URL, api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("2️⃣ 💬 Number Channel", url=CHAT_GROUP, api_kwargs={"style": "success"})],
        [InlineKeyboardButton("3️⃣ 📨 OTP Group", url=OTP_GROUP, api_kwargs={"style": "danger"})],
        [InlineKeyboardButton("✅ VERIFY MEMBERSHIP", callback_data="verify_user", api_kwargs={"style": "primary"})],
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stock Report", callback_data="admin_stock", api_kwargs={"style": "primary"}),
         InlineKeyboardButton("👥 User Stats", callback_data="admin_users", api_kwargs={"style": "success"})],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast", api_kwargs={"style": "danger"}),
         InlineKeyboardButton("📋 OTP Log", callback_data="admin_otp_log", api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("➕ Add Numbers", callback_data="admin_add_numbers", api_kwargs={"style": "success"}),
         InlineKeyboardButton("📤 Upload File", callback_data="admin_upload", api_kwargs={"style": "danger"})],
        [InlineKeyboardButton("🗑️ Delete Numbers", callback_data="admin_delete", api_kwargs={"style": "primary"}),
         InlineKeyboardButton("🔧 Manage Services", callback_data="admin_manage_services", api_kwargs={"style": "success"})],
        [InlineKeyboardButton("🌍 Manage Countries", callback_data="admin_manage_countries", api_kwargs={"style": "danger"}),
         InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings", api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("💰 Country Prices", callback_data="admin_country_prices", api_kwargs={"style": "success"}),
         InlineKeyboardButton("💸 Withdrawals", callback_data="admin_withdrawals", api_kwargs={"style": "danger"})],
        [InlineKeyboardButton("👛 Balance Management", callback_data="admin_balance_manage", api_kwargs={"style": "primary"}),
         InlineKeyboardButton("👥 Referral Stats", callback_data="admin_referral_stats", api_kwargs={"style": "success"})],
        [InlineKeyboardButton("📡 OTP Panels", callback_data="admin_panels", api_kwargs={"style": "danger"}),
         InlineKeyboardButton("📱 Global WA", callback_data="admin_global_wa", api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("🚪 Logout", callback_data="admin_logout", api_kwargs={"style": "danger"})],
    ])

# ─── User Session State ───
user_sessions = {}

def get_session(uid) -> dict:
    uid = str(uid)
    if uid not in user_sessions:
        user_sessions[uid] = {
            "verified": False, "is_admin": False,
            "state": None, "data": None,
            "current_numbers": [], "current_service": None, "current_country": None,
            "last_number_time": 0, "last_verification_check": 0,
        }
    return user_sessions[uid]

# ─── Verification Middleware ───
async def ensure_verified(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    uid  = str(user.id)
    sess = get_session(uid)

    # Admin সবসময় pass
    if sess["is_admin"] or is_admin(uid):
        sess["is_admin"] = True
        return True

    # Verification বন্ধ থাকলে pass
    if not settings.get("requireVerification", True):
        return True

    # Local flag চেক — chat_member handler real-time এ update করে
    if sess.get("verified") or users.get(uid, {}).get("verified", False):
        return True

    # Verified না — rejoin করতে বলো, block না
    msg = (
        "⚠️ *Bot ব্যবহার করতে সকল গ্রুপে join করতে হবে!*\n\n"
        "নিচের সবগুলোতে join করুন, তারপর VERIFY চাপুন:"
    )
    if update.callback_query:
        await update.callback_query.answer("⛔ সব group এ join করো!", show_alert=True)
        try:
            await update.callback_query.edit_message_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
        except:
            await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
    else:
        await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())
    return False

# ─── /start ───
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        uid  = str(user.id)

        if uid not in users:
            users[uid] = {
                "id": uid, "username": user.username or "no_username",
                "first_name": user.first_name or "User",
                "last_name": user.last_name or "",
                "joined": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "verified": False,
                "referredBy": None,
                "referralCount": 0,
            }

        if context.args and context.args[0].startswith("ref_"):
            referrer_id = context.args[0][4:]
            # শুধু referredBy সেট করো — verify সফল হওয়ার আগে count হবে না
            if (referrer_id != uid
                    and not users[uid].get("referredBy")
                    and referrer_id in users):
                users[uid]["referredBy"] = referrer_id
                users[uid]["referralVerified"] = False
                logger.info(f"🔗 Referral pending verify: uid={uid} referred by uid={referrer_id}")

        await async_save_users()

        sess = get_session(uid)
        sess["state"] = None
        sess["data"]  = None

        welcome = (
            f"👋 *Welcome to Earning Hub Number Bot!*\n\n"
            f"📱 Get virtual numbers for OTP verification\n"
            f"💵 Earn money from each OTP received"
        )

        if sess.get("verified") or (uid in users and users[uid].get("verified")):
            await update.message.reply_text(
                welcome + "\n\n✅ Choose an option:",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
        else:
            await update.message.reply_text(
                welcome + "\n\nFirst, join all required groups to use the bot:",
                parse_mode="Markdown", reply_markup=verify_keyboard()
            )
    except Exception as e:
        logger.error(f"cmd_start error: {e}")
        try:
            await update.message.reply_text("⚠️ Error occurred. Please try again.")
        except:
            pass

# ─── Verify ───
async def cb_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Checking...")

    user = update.effective_user
    uid  = str(user.id)
    membership = await check_membership(user.id, context.application)

    if membership["allJoined"]:
        sess = get_session(uid)
        sess["verified"] = True
        sess["last_verification_check"] = time.time()
        if is_admin(uid):
            sess["is_admin"] = True
        if uid in users:
            users[uid]["verified"] = True

            # ── Referral: শুধু প্রথমবার verify হলে count করো ──
            if not users[uid].get("referralVerified", False):
                referrer_id = users[uid].get("referredBy")
                if referrer_id and referrer_id in users:
                    users[uid]["referralVerified"] = True
                    users[referrer_id]["referralCount"] = users[referrer_id].get("referralCount", 0) + 1
                    referrals.setdefault(referrer_id, [])
                    if uid not in referrals[referrer_id]:
                        referrals[referrer_id].append(uid)
                    await async_save_referrals()
                    logger.info(f"✅ Referral confirmed: uid={uid} → referrer={referrer_id}")
                    try:
                        await context.bot.send_message(
                            int(referrer_id),
                            f"🎉 *New Referral Confirmed!*\n\n"
                            f"👤 *{user.first_name}* সব group join করে verified হয়েছে!\n"
                            f"💸 তারা OTP থেকে earn করলে তুমি *{settings.get('referralCommission', 10)}%* commission পাবে।",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            await async_save_users()

        await query.edit_message_text("✅ *VERIFICATION SUCCESSFUL!*\n\nYou can now use all features.", parse_mode="Markdown")
        await context.bot.send_message(
            user.id, "🎉 Welcome! Choose an option:",
            reply_markup=main_keyboard()
        )
    else:
        msg = "❌ *VERIFICATION FAILED*\n\n"
        if not membership["mainChannel"]: msg += "❌ 1️⃣ Main Channel\n"
        if not membership["chatGroup"]:   msg += "❌ 2️⃣ Number Channel\n"
        if not membership["otpGroup"]:    msg += "❌ 3️⃣ OTP Group\n"
        msg += "\nPlease join ALL groups and click VERIFY again."
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=verify_keyboard())

# ─── Admin Login ───
async def cmd_adminlogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 2:
        return await update.message.reply_text("❌ Usage: /adminlogin [password]")
    if parts[1] == ADMIN_PASSWORD:
        uid = str(update.effective_user.id)
        sess = get_session(uid)
        sess["is_admin"] = True
        sess["state"]    = None
        sess["data"]     = None
        if uid not in admins:
            admins.append(uid)
            save_admins()
        await update.message.reply_text("✅ *Admin Login Successful!*\nUse /admin to access panel.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Wrong password.")

# ─── Admin Panel ───
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    sess = get_session(uid)
    if not sess["is_admin"] and not is_admin(uid):
        return await update.message.reply_text("❌ Use /adminlogin [password] first.")
    sess["state"] = None
    sess["data"]  = None
    await update.message.reply_text("🛠 *Admin Dashboard*\n\nSelect an option:", parse_mode="Markdown", reply_markup=admin_keyboard())

# ─── GET NUMBERS ───
async def handle_get_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context):
        return
    sess = get_session(str(update.effective_user.id))
    sess["state"] = None

    avail = []
    for svc_id, svc in services.items():
        ccs = get_available_countries_for_service(svc_id)
        if ccs:
            total = sum(len(numbers_by_cs.get(cc, {}).get(svc_id, [])) for cc in ccs)
            avail.append((svc_id, svc, total))

    if not avail:
        return await update.message.reply_text("📭 *No Numbers Available*\n\nPlease try again later.", parse_mode="Markdown")

    # ── 3-color cycle for service buttons ──
    _svc_colors = ["primary", "success", "danger"]
    buttons = []
    for i in range(0, len(avail), 2):
        row = []
        row.append(InlineKeyboardButton(
            f"{avail[i][1]['icon']} {avail[i][1]['name']} ({avail[i][2]})",
            callback_data=f"svc:{avail[i][0]}", api_kwargs={"style": _svc_colors[i % 3]}
        ))
        if i+1 < len(avail):
            row.append(InlineKeyboardButton(
                f"{avail[i+1][1]['icon']} {avail[i+1][1]['name']} ({avail[i+1][2]})",
                callback_data=f"svc:{avail[i+1][0]}", api_kwargs={"style": _svc_colors[(i+1) % 3]}
            ))
        buttons.append(row)

    await update.message.reply_text(
        "🎯 *Select a Service*\n\n_(number in brackets = available count)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── cb_select_service — 3-COLOR FIX ───
async def cb_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await ensure_verified(update, context):
        return
    await query.answer()
    svc_id = query.data.split(":", 1)[1]
    svc    = services.get(svc_id, {"name": svc_id, "icon": "📞"})
    ccs    = sorted(get_available_countries_for_service(svc_id), key=lambda cc: get_otp_price(cc))

    if not ccs:
        return await query.answer("❌ No numbers available", show_alert=True)

    # ── 3-color cycle: primary=blue, success=green, danger=red ──
    _cc_colors = ["primary", "success", "danger"]
    buttons = []
    for i in range(0, len(ccs), 2):
        row = []
        cc1 = ccs[i]; c1 = countries[cc1]; p1 = get_otp_price(cc1)
        row.append(InlineKeyboardButton(
            f"{c1['flag']} {c1['name']} ({p1:.2f}TK)",
            callback_data=f"cc:{svc_id}:{cc1}",
            api_kwargs={"style": _cc_colors[i % 3]}
        ))
        if i+1 < len(ccs):
            cc2 = ccs[i+1]; c2 = countries[cc2]; p2 = get_otp_price(cc2)
            row.append(InlineKeyboardButton(
                f"{c2['flag']} {c2['name']} ({p2:.2f}TK)",
                callback_data=f"cc:{svc_id}:{cc2}",
                api_kwargs={"style": _cc_colors[(i+1) % 3]}
            ))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="back_services", api_kwargs={"style": "danger"})])

    await query.edit_message_text(
        f"{svc['icon']} *{svc['name']}* — Select Country\n\n_(taka = earnings per OTP)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def cb_select_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await ensure_verified(update, context):
        return
    await query.answer()
    _, svc_id, cc = query.data.split(":")
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    count = settings.get("defaultNumberCount", 10)
    now   = time.time()

    cooldown = settings.get("cooldownSeconds", 5)
    if (now - sess["last_number_time"]) < cooldown and sess["current_numbers"]:
        remaining = int(cooldown - (now - sess["last_number_time"]))
        return await query.answer(f"⏳ {remaining} সেকেন্ড অপেক্ষা করো।", show_alert=True)

    nums = await get_multiple_numbers(cc, svc_id, uid, count)
    if not nums:
        return await query.answer("❌ Not enough numbers available.", show_alert=True)

    for old in sess["current_numbers"]:
        active_numbers.pop(old, None)
    await async_save_active()

    sess["current_numbers"] = nums
    sess["current_service"] = svc_id
    sess["current_country"] = cc
    sess["last_number_time"] = now

    country = countries.get(cc, {"flag": "🌍", "name": cc})
    svc     = services.get(svc_id, {"icon": "📞", "name": svc_id})
    price   = get_otp_price(cc)
    wa_connected = wa_sessions.get(uid, {}).get("connected", False) or (global_wa_data.get("enabled") and global_wa_data.get("connected"))

    def make_msg():
        return (
            f"✅ *{len(nums)} Number(s) Assigned!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"💵 *Earnings per OTP:* {price:.2f} taka\n\n"
            f"📌 OTP automatically আসবে।"
        )

    # ── Copy buttons — ২টা করে এক row ──
    from telegram import CopyTextButton

    def make_copy_buttons(wa_result=None):
        rows = []
        for n in nums:
            if wa_result:
                icon = "📱" if wa_result.get(n) is True else ("❌" if wa_result.get(n) is False else "⬜")
            else:
                icon = "⏳" if wa_connected else "📋"
            rows.append([InlineKeyboardButton(
                text=f"{icon} +{n}",
                copy_text=CopyTextButton(text=f"+{n}")
            )])
        return rows

    bottom_buttons = [
        [InlineKeyboardButton("📨 Open OTP Group", url=OTP_GROUP, api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("🔄 Get New Numbers", callback_data=f"newnum:{svc_id}:{cc}", api_kwargs={"style": "success"})],
        [InlineKeyboardButton("🔙 Service List", callback_data="back_services", api_kwargs={"style": "danger"})],
    ]
    if not wa_connected:
        bottom_buttons.append([InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", api_kwargs={"style": "primary"})])

    buttons = make_copy_buttons() + bottom_buttons
    await query.edit_message_text(make_msg(), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    if wa_connected:
        chat_id = query.message.chat_id
        msg_id  = query.message.message_id
        async def do_wa_check():
            results = await asyncio.gather(
                *[check_wa_number(n, uid) for n in nums],
                return_exceptions=True
            )
            res = {n: (r if not isinstance(r, Exception) else None)
                   for n, r in zip(nums, results)}
            try:
                await context.bot.edit_message_text(
                    make_msg(), chat_id=chat_id, message_id=msg_id,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(make_copy_buttons(res) + bottom_buttons)
                )
            except: pass
        asyncio.create_task(do_wa_check())
        asyncio.create_task(do_wa_check())

async def cb_new_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await ensure_verified(update, context):
        return
    await query.answer()
    _, svc_id, cc = query.data.split(":")
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    now  = time.time()
    cooldown = settings.get("cooldownSeconds", 5)

    if (now - sess["last_number_time"]) < cooldown:
        remaining = int(cooldown - (now - sess["last_number_time"]))
        return await query.answer(f"⏳ {remaining} সেকেন্ড অপেক্ষা করো।", show_alert=True)

    count = settings.get("defaultNumberCount", 10)
    nums  = await get_multiple_numbers(cc, svc_id, uid, count)
    if not nums:
        return await query.answer("❌ No numbers available.", show_alert=True)

    for old in sess["current_numbers"]:
        active_numbers.pop(old, None)
    await async_save_active()

    sess["current_numbers"] = nums
    sess["last_number_time"] = now

    country = countries.get(cc, {"flag": "🌍", "name": cc})
    svc     = services.get(svc_id, {"icon": "📞", "name": svc_id})
    price   = get_otp_price(cc)
    wa_connected = wa_sessions.get(uid, {}).get("connected", False) or (global_wa_data.get("enabled") and global_wa_data.get("connected"))

    def make_msg_new():
        return (
            f"🔄 *{len(nums)} New Number(s)!*\n\n"
            f"{svc['icon']} *Service:* {svc['name']}\n"
            f"{country['flag']} *Country:* {country['name']}\n"
            f"💵 *Earnings per OTP:* {price:.2f} taka\n\n"
            f"📌 OTP automatically আসবে।"
        )

    from telegram import CopyTextButton

    def make_copy_buttons_new(wa_result=None):
        rows = []
        for n in nums:
            if wa_result:
                icon = "📱" if wa_result.get(n) is True else ("❌" if wa_result.get(n) is False else "⬜")
            else:
                icon = "⏳" if wa_connected else "📋"
            rows.append([InlineKeyboardButton(
                text=f"{icon} +{n}",
                copy_text=CopyTextButton(text=f"+{n}")
            )])
        return rows

    bottom_buttons_new = [
        [InlineKeyboardButton("📨 Open OTP Group", url=OTP_GROUP, api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("🔄 Get New Numbers", callback_data=f"newnum:{svc_id}:{cc}", api_kwargs={"style": "success"})],
        [InlineKeyboardButton("🔙 Service List", callback_data="back_services", api_kwargs={"style": "danger"})],
    ]
    if not wa_connected:
        bottom_buttons_new.append([InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", api_kwargs={"style": "primary"})])

    buttons = make_copy_buttons_new() + bottom_buttons_new
    await query.edit_message_text(make_msg_new(), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    if wa_connected:
        chat_id = query.message.chat_id
        msg_id  = query.message.message_id
        async def do_wa_check_new():
            results = await asyncio.gather(
                *[check_wa_number(n, uid) for n in nums],
                return_exceptions=True
            )
            res = {n: (r if not isinstance(r, Exception) else None)
                   for n, r in zip(nums, results)}
            try:
                await context.bot.edit_message_text(
                    make_msg_new(), chat_id=chat_id, message_id=msg_id,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(make_copy_buttons_new(res) + bottom_buttons_new)
                )
            except: pass
        asyncio.create_task(do_wa_check_new())

async def cb_back_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    avail = []
    for svc_id, svc in services.items():
        ccs = get_available_countries_for_service(svc_id)
        if ccs:
            total = sum(len(numbers_by_cs.get(cc, {}).get(svc_id, [])) for cc in ccs)
            avail.append((svc_id, svc, total))

    # ── 3-color cycle ──
    _svc_colors = ["primary", "success", "danger"]
    buttons = []
    for i in range(0, len(avail), 2):
        row = []
        row.append(InlineKeyboardButton(
            f"{avail[i][1]['icon']} {avail[i][1]['name']} ({avail[i][2]})",
            callback_data=f"svc:{avail[i][0]}", api_kwargs={"style": _svc_colors[i % 3]}
        ))
        if i+1 < len(avail):
            row.append(InlineKeyboardButton(
                f"{avail[i+1][1]['icon']} {avail[i+1][1]['name']} ({avail[i+1][2]})",
                callback_data=f"svc:{avail[i+1][0]}", api_kwargs={"style": _svc_colors[(i+1) % 3]}
            ))
        buttons.append(row)

    await query.edit_message_text(
        "🎯 *Select a Service*\n\n_(number in brackets = available count)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─── BALANCE ───
async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    e   = get_user_earnings(uid)
    pending = [w for w in withdrawals if w["userId"] == uid and w["status"] == "pending"]
    withdrawn = sum(w["amount"] for w in withdrawals if w["userId"] == uid and w["status"] == "approved")
    ref_count = users.get(uid, {}).get("referralCount", 0)
    ref_earn  = e.get("referralEarnings", 0)

    await update.message.reply_text(
        f"💰 *Your Earnings*\n\n"
        f"💵 *Current Balance:* {e['balance']:.2f} taka\n"
        f"📈 *Total Earned:* {e['totalEarned']:.2f} taka\n"
        f"📨 *Total OTPs:* {e.get('otpCount', 0)}\n"
        f"💸 *Total Withdrawn:* {withdrawn:.2f} taka\n"
        f"⏳ *Pending Withdrawals:* {len(pending)}\n\n"
        f"👥 *Referrals:* {ref_count} জন\n"
        f"🎁 *Referral Earnings:* {ref_earn:.2f} taka\n\n"
        f"📌 *Minimum Withdraw:* {settings['minWithdraw']} taka",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 Withdraw", callback_data="start_withdraw", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("📋 Withdraw History", callback_data="withdraw_history", api_kwargs={"style": "primary"})],
        ])
    )

# ─── REFERRAL ───
async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    bot_username = context.bot.username
    ref_link = get_referral_link(uid, bot_username)
    commission = settings.get("referralCommission", 10)
    ref_count = users.get(uid, {}).get("referralCount", 0)
    ref_earn  = get_user_earnings(uid).get("referralEarnings", 0)

    referred_list = referrals.get(uid, [])
    referred_text = ""
    if referred_list:
        for r_uid in referred_list[-5:][::-1]:
            r_user = users.get(r_uid, {})
            r_name = r_user.get("first_name", "User")
            r_name = r_name.replace("*", "").replace("_", "")
            r_earn  = get_user_earnings(r_uid)
            my_cut  = round(r_earn.get("totalEarned", 0) * commission / 100, 2)
            referred_text += f"  👤 {r_name} — তোমার cut: *{my_cut:.2f} taka*\n"

    msg = (
        f"👥 *Referral Program*\n\n"
        f"🔗 তোমার referral link:\n`{ref_link}`\n\n"
        f"💸 *Commission:* প্রতি OTP এর *{commission}%*\n\n"
        f"📊 *তোমার Stats:*\n"
        f"  👥 Total Referrals: *{ref_count}*\n"
        f"  💰 Total Commission Earned: *{ref_earn:.2f} taka*\n"
    )
    if referred_text:
        msg += f"\n📋 *Recent Referrals:*\n{referred_text}"

    msg += (
        f"\n📌 *How it works:*\n"
        f"  1. উপরের link share করো\n"
        f"  2. কেউ join করলে তারা OTP earn করবে\n"
        f"  3. তুমি তাদের প্রতিটা OTP income এর *{commission}%* পাবে আজীবন!\n"
    )

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Share Referral Link", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}&text={urllib.parse.quote(f'আমার referral link দিয়ে join করো এবং OTP থেকে আয় করো!')}", api_kwargs={"style": "success"})],
            [InlineKeyboardButton("📊 Referral Stats", callback_data="ref_stats", api_kwargs={"style": "danger"})],
        ])
    )

async def cb_ref_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    commission = settings.get("referralCommission", 10)
    ref_count = users.get(uid, {}).get("referralCount", 0)
    ref_earn  = get_user_earnings(uid).get("referralEarnings", 0)
    referred_list = referrals.get(uid, [])

    msg = (
        f"📊 *Referral Statistics*\n\n"
        f"👥 *Total Referred:* {ref_count}\n"
        f"💰 *Total Commission:* {ref_earn:.2f} taka\n"
        f"📌 *Commission Rate:* {commission}%\n\n"
    )

    if referred_list:
        msg += "👤 *All Referred Users:*\n"
        for r_uid in referred_list[-20:]:
            r_user = users.get(r_uid, {})
            r_name = r_user.get("first_name", "User").replace("*", "").replace("_", "")
            r_earn = get_user_earnings(r_uid)
            otps   = r_earn.get("otpCount", 0)
            my_cut = round(r_earn.get("totalEarned", 0) * commission / 100, 2)
            msg += f"  • {r_name} | OTPs: {otps} | তোমার: {my_cut:.2f}৳\n"
    else:
        msg += "এখনো কোনো referral নেই।\n"

    if len(msg) > 4000:
        msg = msg[:3950] + "\n..._truncated_"

    bot_username = context.bot.username
    ref_link = get_referral_link(uid, bot_username)

    await query.edit_message_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Share Link", url=f"https://t.me/share/url?url={urllib.parse.quote(ref_link)}", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton("🔙 Back", callback_data="goto_main", api_kwargs={"style": "success"})],
        ])
    )

# ─── WITHDRAW ───
async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid = str(update.effective_user.id)
    e   = get_user_earnings(uid)
    sess = get_session(uid)
    sess["state"] = None

    if not settings.get("withdrawEnabled", True):
        return await update.message.reply_text("⏸️ *Withdrawals are currently disabled.*", parse_mode="Markdown")

    if e["balance"] < settings["minWithdraw"]:
        return await update.message.reply_text(
            f"❌ *Insufficient balance.*\n\n"
            f"💵 Balance: {e['balance']:.2f} taka\n"
            f"📌 Minimum: {settings['minWithdraw']} taka",
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        f"💸 *Withdraw*\n\n💵 Balance: *{e['balance']:.2f} taka*\n\nChoose method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟣 bKash", callback_data="wm:bKash", api_kwargs={"style": "danger"}),
             InlineKeyboardButton("🟠 Nagad", callback_data="wm:Nagad", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", api_kwargs={"style": "success"})],
        ])
    )

async def cb_withdraw_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split(":", 1)[1]
    uid    = str(update.effective_user.id)
    sess   = get_session(uid)
    e      = get_user_earnings(uid)

    sess["state"] = "w_amount"
    sess["data"]  = {"method": method}

    amounts = []
    for a in [settings["minWithdraw"], 100, 200, 500]:
        if e["balance"] >= a and a not in amounts:
            amounts.append(a)

    rows = []
    for i in range(0, len(amounts), 2):
        row = [InlineKeyboardButton(f"{amounts[i]} taka", callback_data=f"wa:{method}:{amounts[i]}", api_kwargs={"style": "primary"})]
        if i+1 < len(amounts):
            row.append(InlineKeyboardButton(f"{amounts[i+1]} taka", callback_data=f"wa:{method}:{amounts[i+1]}", api_kwargs={"style": "success"}))
        rows.append(row)
    rows.append([InlineKeyboardButton(f"💰 All ({e['balance']:.2f} taka)", callback_data=f"wa:{method}:{e['balance']:.2f}", api_kwargs={"style": "danger"})])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", api_kwargs={"style": "primary"})])

    icon = "🟣" if method == "bKash" else "🟠"
    await query.edit_message_text(
        f"{icon} *{method} Withdrawal*\n\n💵 Balance: *{e['balance']:.2f} taka*\n\nSelect amount or type in chat:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def cb_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, method, amt_str = query.data.split(":")
    amount = float(amt_str)
    uid    = str(update.effective_user.id)
    sess   = get_session(uid)
    e      = get_user_earnings(uid)

    if amount < settings["minWithdraw"]:
        return await query.answer(f"❌ Minimum {settings['minWithdraw']} taka", show_alert=True)
    if amount > e["balance"]:
        return await query.answer("❌ Insufficient balance!", show_alert=True)

    sess["state"] = "w_account"
    sess["data"]  = {"method": method, "amount": amount}
    icon = "🟣" if method == "bKash" else "🟠"

    await query.edit_message_text(
        f"{icon} *{method} — {amount:.2f} taka*\n\n📱 Your *{method} number:*\nExample: `01712345678`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", api_kwargs={"style": "success"})]])
    )

async def cb_withdraw_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None
    await query.edit_message_text("❌ *Cancelled.*", parse_mode="Markdown")

async def cb_withdraw_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid   = str(update.effective_user.id)
    uwith = [w for w in withdrawals if w["userId"] == uid][-10:][::-1]

    text = "📋 *Withdraw History*\n\n"
    if not uwith:
        text += "No withdrawal requests yet."
    else:
        for w in uwith:
            icon = "✅" if w["status"] == "approved" else "❌" if w["status"] == "rejected" else "⏳"
            date = w["requestedAt"][:10]
            text += f"{icon} *{w['amount']:.2f} taka* - {w['method']}\n"
            text += f"📱 `{w['account']}` | {date}\n\n"

    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="goto_main", api_kwargs={"style": "danger"})]]))

async def cb_start_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    e    = get_user_earnings(uid)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None

    if not settings.get("withdrawEnabled", True):
        return await query.edit_message_text("⏸️ *Withdrawals are currently disabled.*", parse_mode="Markdown")
    if e["balance"] < settings["minWithdraw"]:
        return await query.edit_message_text(
            f"❌ *Insufficient balance.*\n💵 Balance: {e['balance']:.2f} taka\n📌 Minimum: {settings['minWithdraw']} taka",
            parse_mode="Markdown"
        )

    await query.edit_message_text(
        f"💸 *Withdraw*\n\n💵 Balance: *{e['balance']:.2f} taka*\n\nChoose method:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟣 bKash", callback_data="wm:bKash", api_kwargs={"style": "primary"}),
             InlineKeyboardButton("🟠 Nagad", callback_data="wm:Nagad", api_kwargs={"style": "success"})],
            [InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", api_kwargs={"style": "danger"})],
        ])
    )

# ─── WhatsApp Connect ───
async def cb_wa_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)

    if wa_sessions.get(uid, {}).get("connected"):
        await query.edit_message_text(
            "✅ *WhatsApp Already Connected!*\n\n"
            "🟢 WhatsApp এখন active আছে।\n"
            "Disconnect করতে নিচের বাটন চাপো:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔴 Logout / Disconnect", callback_data="wa_disconnect", api_kwargs={"style": "primary"})],
                [InlineKeyboardButton("📊 Check Status", callback_data="wa_status", api_kwargs={"style": "success"})],
            ])
        )
        return

    sess = get_session(uid)
    sess["state"] = "wa_waiting_number"
    await context.bot.send_message(
        update.effective_user.id,
        "📱 WhatsApp Connect\n\nতোমার WhatsApp নম্বর দাও (country code সহ):\nExample: 8801712345678"
    )

async def cb_wa_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Checking...")
    uid   = str(update.effective_user.id)

    try:
        state = await green_get_state(uid)
    except:
        state = "notAuthorized"

    conn = (state == "authorized")
    if conn:
        wa_sessions[uid] = {"connected": True}
    else:
        wa_sessions.pop(uid, None)

    STATE_MAP = {
        "authorized":    "✅ *WhatsApp Connected!*\n\nNumber assign হলে 📱/❌ দেখাবে।",
        "notAuthorized": "🔴 *WhatsApp connected নেই।*\n\nCode enter করলে আবার Check Status চাপো।",
    }
    text = STATE_MAP.get(state, f"❓ Unknown state: {state}")
    btns = [[InlineKeyboardButton("🔴 Disconnect", callback_data="wa_disconnect", api_kwargs={"style": "danger"})]] if conn else \
           [[InlineKeyboardButton("📱 Connect", callback_data="wa_connect", api_kwargs={"style": "primary"})]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def cb_wa_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Disconnecting...")
    uid = str(update.effective_user.id)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: baileys_request("POST", "/disconnect", {"userId": uid}))
        logger.info(f"✅ Baileys logout called for uid={uid}")
    except Exception as e:
        logger.error(f"Baileys logout error: {e}")

    wa_sessions.pop(uid, None)

    await query.edit_message_text(
        "🔴 *WhatsApp Disconnected!*\n\n"
        "তোমার WhatsApp সফলভাবে logout হয়েছে।\n"
        "আবার connect করতে নিচের বাটন চাপো:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Connect WhatsApp", callback_data="wa_connect", api_kwargs={"style": "success"})],
        ])
    )

# ─── Temp Mail ───
async def handle_tempmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    existing = temp_mails.get(uid)

    if existing:
        await update.message.reply_text(
            f"📧 *Temporary Email*\n\n📌 Your email:\n`{existing['address']}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📬 Check Inbox", callback_data="tm_inbox", api_kwargs={"style": "danger"})],
                [InlineKeyboardButton("📋 Show Email", callback_data="tm_show", api_kwargs={"style": "primary"})],
                [InlineKeyboardButton("🔄 Get New Email", callback_data="tm_create", api_kwargs={"style": "success"})],
                [InlineKeyboardButton("🗑️ Delete Email", callback_data="tm_delete", api_kwargs={"style": "danger"})],
            ])
        )
    else:
        await update.message.reply_text(
            "📧 *Temporary Email*\n\n✅ Create a new disposable email address.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🆕 Create New Email", callback_data="tm_create", api_kwargs={"style": "primary"})]])
        )

async def cb_tm_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Creating...")
    uid   = str(update.effective_user.id)
    loading = await context.bot.send_message(uid, "⏳ *Creating your email...*", parse_mode="Markdown")

    async def _create_task():
        try:
            new_email = await create_fresh_email()
            if not new_email:
                await context.bot.edit_message_text(
                    "❌ *Email creation failed.* Please try again.",
                    chat_id=uid, message_id=loading.message_id,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="tm_create", api_kwargs={"style": "success"})]])
                )
                return
            temp_mails[uid] = new_email
            save_temp_mails()
            await context.bot.edit_message_text(
                f"✅ *New Email Created!*\n\n📧 `{new_email['address']}`\n\n📌 Use this on any website.",
                chat_id=uid, message_id=loading.message_id,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📬 Check Inbox", callback_data="tm_inbox", api_kwargs={"style": "danger"})],
                    [InlineKeyboardButton("🔄 Get New Email", callback_data="tm_create", api_kwargs={"style": "primary"})],
                    [InlineKeyboardButton("🗑️ Delete", callback_data="tm_delete", api_kwargs={"style": "success"})],
                ])
            )
        except Exception as e:
            logger.error(f"cb_tm_create task error uid={uid}: {e}")
            try:
                await context.bot.edit_message_text(
                    "❌ *Error occurred.* Please try again.",
                    chat_id=uid, message_id=loading.message_id,
                    parse_mode="Markdown"
                )
            except:
                pass

    asyncio.create_task(_create_task())

async def cb_tm_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📬 Loading...")
    uid = str(update.effective_user.id)

    if uid not in temp_mails:
        return await query.edit_message_text(
            "❌ No email found.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🆕 Create", callback_data="tm_create", api_kwargs={"style": "danger"})]])
        )

    email_obj = temp_mails[uid]

    async def _inbox_task():
        try:
            messages  = await get_email_inbox(email_obj)
            now_str   = datetime.now().strftime("%I:%M:%S %p")
            text      = f"📬 *Inbox:* `{email_obj['address']}`\n🕐 _{now_str}_\n\n"

            if not messages:
                text += "📭 *No emails yet.*"
            else:
                for msg in messages[:5]:
                    text += f"━━━━━━━━━━\n📩 *From:* {msg['from']}\n📌 *Subject:* {msg['subject']}\n"
                    body = await get_email_message(msg["id"], email_obj)
                    if body:
                        otp_m = re.findall(r"\b\d{4,8}\b", body)
                        if otp_m:
                            text += f"\n🔑 *OTP:* `{otp_m[0]}`\n"
                        text += f"\n📝 _{body[:250]}..._\n" if len(body) > 250 else f"\n📝 _{body}_\n"
                    text += "\n"

            try:
                await query.edit_message_text(text[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="tm_inbox", api_kwargs={"style": "primary"})],
                    [InlineKeyboardButton("🔄 New Email", callback_data="tm_create", api_kwargs={"style": "success"})],
                    [InlineKeyboardButton("🗑️ Delete", callback_data="tm_delete", api_kwargs={"style": "danger"})],
                ]))
            except:
                pass
        except Exception as e:
            logger.error(f"cb_tm_inbox task error uid={uid}: {e}")

    asyncio.create_task(_inbox_task())

async def cb_tm_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    if uid not in temp_mails:
        return await query.answer("❌ No email found", show_alert=True)
    addr = temp_mails[uid]["address"]
    await query.edit_message_text(
        f"📧 *Your Temp Email:*\n\n`{addr}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📬 Check Inbox", callback_data="tm_inbox", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton("🔄 New Email", callback_data="tm_create", api_kwargs={"style": "success"})],
        ])
    )

async def cb_tm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    temp_mails.pop(uid, None)
    save_temp_mails()
    await query.edit_message_text("✅ *Email deleted.*", parse_mode="Markdown")

# ─── 2FA/TOTP ───
async def handle_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context): return
    sess = get_session(str(update.effective_user.id))
    sess["state"] = None
    await update.message.reply_text(
        "🔐 *2-Step Verification Code Generator*\n\nSelect a service:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📘 Facebook 2FA", callback_data="totp:facebook", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("📸 Instagram 2FA", callback_data="totp:instagram", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton("🔍 Google 2FA", callback_data="totp:google", api_kwargs={"style": "success"})],
            [InlineKeyboardButton("⚙️ Other 2FA", callback_data="totp:other", api_kwargs={"style": "danger"})],
        ])
    )

async def cb_totp_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    svc  = query.data.split(":", 1)[1]
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = "totp_waiting_secret"
    sess["data"]  = {"service": svc}

    if uid in users:
        users[uid]["pending_totp_svc"] = svc
        await async_save_users()

    icons = {"facebook": "📘", "instagram": "📸", "google": "🔍", "other": "⚙️"}
    names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "Other"}
    icon  = icons.get(svc, "🔐")
    name  = names.get(svc, svc)

    await query.edit_message_text(
        f"{icon} *{name} Secret Key*\n\n"
        f"Send your Authenticator Secret Key.\n\n"
        f"🔑 It looks like: `JBSWY3DPEHPK3PXP`\n\n"
        f"Type /cancel to cancel",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="totp_back", api_kwargs={"style": "primary"})]])
    )

async def cb_totp_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔐 *2FA Code Generator*\n\nSelect a service:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📘 Facebook 2FA", callback_data="totp:facebook", api_kwargs={"style": "success"})],
            [InlineKeyboardButton("📸 Instagram 2FA", callback_data="totp:instagram", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("🔍 Google 2FA", callback_data="totp:google", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton("⚙️ Other 2FA", callback_data="totp:other", api_kwargs={"style": "success"})],
        ])
    )

async def cb_totp_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Refreshing...")
    _, svc, secret_enc = query.data.split(":", 2)

    if secret_enc == "TOOLONG":
        await query.edit_message_text(
            "⚠️ Secret key টি অনেক বড়। Refresh করতে আবার 🔐 2FA বাটন চাপুন।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="totp_back", api_kwargs={"style": "danger"})]]))
        return

    secret = urllib.parse.unquote(secret_enc)
    result = generate_totp(secret)

    icons = {"facebook": "📘", "instagram": "📸", "google": "🔍", "other": "⚙️"}
    names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "2FA"}
    icon  = icons.get(svc, "🔐")
    name  = names.get(svc, svc)

    if not result:
        return await query.edit_message_text("❌ Invalid secret key.", parse_mode="Markdown")

    cb_data = f"totp_r:{svc}:{secret_enc}"

    try:
        await query.edit_message_text(
            f"{icon} *{name} 2FA Code*\n\n"
            f"🔑 *Code:* `{result['token']}`\n\n"
            f"⏰ *{result['timeRemaining']} seconds remaining*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh Code", callback_data=cb_data, api_kwargs={"style": "primary"})],
                [InlineKeyboardButton("🔙 Back", callback_data="totp_back", api_kwargs={"style": "success"})],
            ])
        )
    except:
        pass

# ─── Support ───
async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💬 *Support*\n\nContact admin:\n📌 @Asif_store_bot",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact", url="https://t.me/Asif_store_bot", api_kwargs={"style": "danger"})]])
    )

# ─── Admin Callbacks ───
async def cb_admin_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    report = "📊 *Stock Report*\n\n"
    total_all = 0
    for cc, svcs in numbers_by_cs.items():
        country = countries.get(cc, {"flag": "🏴", "name": cc})
        report += f"\n{country['flag']} {country['name']} (+{cc}):\n"
        ct = 0
        for svc_id, nums in svcs.items():
            svc = services.get(svc_id, {"icon": "📞", "name": svc_id})
            if nums:
                report += f"  {svc['icon']} {svc['name']}: *{len(nums)}*\n"
                ct += len(nums)
        report += f"  *Total:* {ct}\n"
        total_all += ct

    report += f"\n📈 *Grand Total:* {total_all}\n"
    report += f"👥 *Active:* {len(active_numbers)}\n"
    report += f"📨 *OTPs:* {len(otp_log)}"

    if len(report) > 4000:
        report = report[:3950] + "\n..._truncated_"

    await safe_edit(query, report, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stock", api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "success"})],
    ]))

async def cb_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    try:
        total = len(users)
        total_referrals = sum(u.get("referralCount", 0) for u in users.values())
        msg   = (
            f"👥 *User Statistics*\n\n"
            f"• Total Users: {total}\n"
            f"• Active Numbers: {len(active_numbers)}\n"
            f"• OTPs Processed: {len(otp_log)}\n"
            f"• Total Referrals Made: {total_referrals}\n\n"
        )

        recent = sorted(users.values(), key=lambda u: u.get("last_active",""), reverse=True)[:10]
        for u in recent:
            uid_str  = u.get('id', '?')
            fname    = u.get('first_name', '').replace('*','').replace('_','').replace('`','')
            uname    = u.get('username', 'no_username').replace('_','\\_')
            msg += f"👤 *{fname}*\n🆔 `{uid_str}` | @{uname}\n"
            msg += f"🕐 {get_time_ago(u.get('last_active', ''))}\n\n"

        if len(msg) > 4000:
            msg = msg[:3950] + "..._truncated_"

        await safe_edit(query, msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_users", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
        ]))
    except Exception as e:
        logger.error(f"cb_admin_users error: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                f"❌ *Error loading user stats*\n\n`{str(e)[:200]}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "success"})]])
            )
        except:
            pass

async def cb_admin_otp_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    msg = "📋 *Recent OTP Logs*\n\n"
    if not otp_log:
        msg += "No OTPs yet."
    else:
        for log in otp_log[-10:][::-1]:
            msg += f"📞 `{log['phoneNumber']}` → 👤 `{log['userId']}`\n"
            msg += f"🕐 {get_time_ago(log.get('timestamp',''))}\n\n"

    await safe_edit(query, msg[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_otp_log", api_kwargs={"style": "danger"})],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
    ]))

async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_broadcast"
    await query.edit_message_text(
        "📢 *Broadcast Message*\n\nSend the message to broadcast to all users:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "success"})]])
    )

async def cb_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    commission = settings.get("referralCommission", 10)
    await query.edit_message_text(
        f"⚙️ *Bot Settings*\n\n"
        f"📞 Number Count: *{settings['defaultNumberCount']}*\n"
        f"⏱ Cooldown: *{settings['cooldownSeconds']} seconds*\n"
        f"🔐 Verification: *{'Enabled ✅' if settings['requireVerification'] else 'Disabled ❌'}*\n"
        f"💵 OTP Price: *{settings.get('defaultOtpPrice', 0.25):.2f} taka*\n"
        f"💸 Min Withdraw: *{settings['minWithdraw']} taka*\n"
        f"🏧 Withdraw: *{'Enabled ✅' if settings['withdrawEnabled'] else 'Disabled ❌'}*\n"
        f"👥 Referral Commission: *{commission}%*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 Number Count", callback_data="as_count", api_kwargs={"style": "danger"}),
             InlineKeyboardButton("⏱ Cooldown", callback_data="as_cooldown", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton(f"🔐 Verification {'Disable' if settings['requireVerification'] else 'Enable'}", callback_data="as_toggle_verify", api_kwargs={"style": "success"})],
            [InlineKeyboardButton("💵 OTP Price", callback_data="as_price", api_kwargs={"style": "danger"}),
             InlineKeyboardButton("💸 Min Withdraw", callback_data="as_minw", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton(f"🏧 Withdraw {'🔴 Disable' if settings['withdrawEnabled'] else '🟢 Enable'}", callback_data="as_toggle_withdraw", api_kwargs={"style": "success"})],
            [InlineKeyboardButton(f"👥 Referral Commission ({commission}%)", callback_data="as_referral_commission", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
        ])
    )

async def cb_admin_toggle_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    settings["requireVerification"] = not settings["requireVerification"]
    save_settings()
    await query.answer(f"✅ Verification {'Enabled' if settings['requireVerification'] else 'Disabled'}")
    await cb_admin_settings(update, context)

async def cb_admin_toggle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    settings["withdrawEnabled"] = not settings["withdrawEnabled"]
    save_settings()
    await query.answer(f"✅ Withdraw {'Enabled' if settings['withdrawEnabled'] else 'Disabled'}")
    await cb_admin_settings(update, context)

async def cb_as_referral_commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_referral_commission"
    current = settings.get("referralCommission", 10)
    await query.edit_message_text(
        f"👥 *Set Referral Commission*\n\n"
        f"Current: *{current}%*\n\n"
        f"Send new commission percentage (0-50):\n"
        f"Example: `10` means 10%",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "success"})]])
    )

async def cb_admin_referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    commission = settings.get("referralCommission", 10)
    total_referrals = sum(u.get("referralCount", 0) for u in users.values())
    total_ref_earn  = sum(e.get("referralEarnings", 0) for e in earnings.values())

    msg = (
        f"👥 *Referral System Stats*\n\n"
        f"📌 Commission Rate: *{commission}%*\n"
        f"👥 Total Referrals: *{total_referrals}*\n"
        f"💰 Total Commission Paid: *{total_ref_earn:.2f} taka*\n\n"
        f"🏆 *Top Referrers:*\n"
    )

    top_ref = sorted(
        [(uid_k, u.get("referralCount", 0)) for uid_k, u in users.items()],
        key=lambda x: x[1], reverse=True
    )[:10]

    for r_uid, r_count in top_ref:
        if r_count == 0:
            continue
        r_user = users.get(r_uid, {})
        r_name = r_user.get("first_name", "User").replace("*", "").replace("_", "")
        r_earn = earnings.get(r_uid, {}).get("referralEarnings", 0)
        msg += f"  👤 {r_name} | {r_count} referrals | {r_earn:.2f} taka\n"

    if len(msg) > 4000:
        msg = msg[:3950] + "\n..._truncated_"

    await query.edit_message_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚙️ Set Commission ({commission}%)", callback_data="as_referral_commission", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
        ])
    )

async def cb_as_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_count"
    await query.edit_message_text(
        f"📞 *Set Number Count*\n\nCurrent: *{settings['defaultNumberCount']}*\n\nSend new count (1-100):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "success"})]])
    )

async def cb_as_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_cooldown"
    await query.edit_message_text(
        f"⏱ *Set Cooldown*\n\nCurrent: *{settings['cooldownSeconds']} seconds*\n\nSend new cooldown (1-3600):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "danger"})]])
    )

async def cb_as_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_price"
    await query.edit_message_text(
        f"💵 *Set Default OTP Price*\n\nCurrent: *{settings.get('defaultOtpPrice', 0.25):.2f} taka*\n\nSend new price:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "primary"})]])
    )

async def cb_as_minw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_minw"
    await query.edit_message_text(
        f"💸 *Set Min Withdraw*\n\nCurrent: *{settings['minWithdraw']} taka*\n\nSend new minimum:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "success"})]])
    )

async def cb_admin_add_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_add_numbers"
    await query.edit_message_text(
        "➕ *Add Numbers*\n\nFormat:\n`[number]|[country code]|[service]`\n\nExample:\n`8801712345678|880|whatsapp`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "danger"})]])
    )

async def cb_admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    pending = [w for w in withdrawals if w["status"] == "pending"]
    msg = f"💸 *Pending Withdrawals:* {len(pending)}\n\n"

    for w in pending[:10]:
        msg += f"🆔 `{w['id'][-8:]}`\n"
        msg += f"👤 {w.get('userName','')} | 💵 {w['amount']:.2f} taka\n"
        msg += f"📱 {w['method']}: `{w['account']}`\n\n"

    buttons = []
    for w in pending[:5]:
        buttons.append([
            InlineKeyboardButton(f"✅ {w['id'][-6:]}", callback_data=f"wadm_approve:{w['id']}", api_kwargs={"style": "primary"}),
            InlineKeyboardButton(f"❌ {w['id'][-6:]}", callback_data=f"wadm_reject:{w['id']}", api_kwargs={"style": "success"}),
        ])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "danger"})])

    await query.edit_message_text(msg[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_withdraw_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    wid = query.data.split(":", 1)[1]
    for w in withdrawals:
        if w["id"] == wid:
            w["status"] = "approved"
            w["processedAt"] = datetime.now().isoformat()
            await async_save_withdrawals()
            await query.answer("✅ Approved!")
            try:
                await context.bot.send_message(w["userId"],
                    f"✅ *Withdrawal Approved!*\n\n💵 {w['amount']:.2f} taka → {w['method']}: `{w['account']}`",
                    parse_mode="Markdown")
            except:
                pass
            break
    await cb_admin_withdrawals(update, context)

async def cb_withdraw_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    wid = query.data.split(":", 1)[1]
    for w in withdrawals:
        if w["id"] == wid:
            w["status"] = "rejected"
            w["processedAt"] = datetime.now().isoformat()
            e = get_user_earnings(w["userId"])
            e["balance"] = round(e["balance"] + w["amount"], 2)
            await async_save_earnings()
            await async_save_withdrawals()
            await query.answer("❌ Rejected!")
            try:
                await context.bot.send_message(w["userId"],
                    f"❌ *Withdrawal Rejected.*\n\n💵 {w['amount']:.2f} taka refunded.",
                    parse_mode="Markdown")
            except:
                pass
            break
    await cb_admin_withdrawals(update, context)

async def cb_admin_balance_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    await query.edit_message_text(
        "👛 *Balance Management*\n\nSelect action:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Balance", callback_data="bal_add", api_kwargs={"style": "primary"}),
             InlineKeyboardButton("➖ Deduct Balance", callback_data="bal_deduct", api_kwargs={"style": "success"})],
            [InlineKeyboardButton("🔄 Reset Balance", callback_data="bal_reset", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
        ])
    )

async def cb_bal_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_add_balance"
    await query.edit_message_text(
        "➕ *Add Balance*\n\nFormat: `[userId] [amount]`\nExample: `123456789 50`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "success"})]])
    )

async def cb_bal_deduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_deduct_balance"
    await query.edit_message_text(
        "➖ *Deduct Balance*\n\nFormat: `[userId] [amount]`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "danger"})]])
    )

async def cb_bal_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_reset_balance"
    await query.edit_message_text(
        "🔄 *Reset Balance*\n\nSend the userId:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "primary"})]])
    )

async def cb_admin_country_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    get_session(uid)["state"] = "admin_set_country_price"
    text = "💰 *Country Prices*\n\nCurrent prices:\n"
    for cc, c in countries.items():
        p = country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))
        text += f"{c['flag']} +{cc}: *{p:.2f} TK*\n"
    text += "\nSend new prices (format: `880 0.50`):"

    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "success"})]]))

async def cb_admin_manage_countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    await query.edit_message_text(
        f"🌍 *Manage Countries*\n\nTotal: *{len(countries)}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Country", callback_data="country_add", api_kwargs={"style": "danger"}),
             InlineKeyboardButton("📋 List Countries", callback_data="country_list", api_kwargs={"style": "primary"})],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "success"})],
        ])
    )

async def cb_country_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "🌍 *Country List*\n\n"
    for cc, c in countries.items():
        p = country_prices.get(cc, settings.get("defaultOtpPrice", 0.25))
        text += f"{c['flag']} *{c['name']}* (+{cc}) — {p:.2f} TK/OTP\n"
    await query.edit_message_text(text[:4000], parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_manage_countries", api_kwargs={"style": "danger"})]]))

async def cb_country_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "admin_add_country"
    await query.edit_message_text(
        "🌍 *Add Country*\n\nFormat: `[code] [name] [flag]`\nExample: `880 Bangladesh 🇧🇩`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "primary"})]])
    )

async def cb_admin_manage_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    await query.edit_message_text(
        "🔧 *Manage Services*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 List Services", callback_data="svc_list", api_kwargs={"style": "success"}),
             InlineKeyboardButton("➕ Add Service", callback_data="svc_add", api_kwargs={"style": "danger"})],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
        ])
    )

async def cb_svc_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📋 *Services List*\n\n"
    for svc_id, svc in services.items():
        text += f"• {svc['icon']} *{svc['name']}* (ID: `{svc_id}`)\n"
    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_manage_services", api_kwargs={"style": "success"})]]))

async def cb_svc_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "admin_add_service"
    await query.edit_message_text(
        "🔧 *Add Service*\n\nFormat: `[id] [name] [icon]`\nExample: `facebook Facebook 📘`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "danger"})]])
    )

async def cb_admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    sess = get_session(uid)
    sess["state"] = "admin_upload_select_service"

    buttons = [[InlineKeyboardButton(f"{svc['icon']} {svc['name']}", callback_data=f"upload_svc:{svc_id}", api_kwargs={"style": "primary"})]
               for svc_id, svc in services.items()]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "success"})])
    await query.edit_message_text("📤 *Upload Numbers*\n\nSelect service:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def cb_upload_svc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    svc_id = query.data.split(":", 1)[1]
    svc    = services.get(svc_id, {"name": svc_id})
    sess   = get_session(uid)
    sess["state"] = "admin_upload_file"
    sess["data"]  = {"serviceId": svc_id}
    await query.edit_message_text(
        f"📤 *Upload Numbers for {svc['name']}*\n\nSend a .txt file with numbers (one per line).",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel", api_kwargs={"style": "danger"})]])
    )

async def cb_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = None
    get_session(uid)["data"]  = None
    await query.edit_message_text("🛠 *Admin Dashboard*\n\nSelect an option:", parse_mode="Markdown", reply_markup=admin_keyboard())

async def cb_admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = None
    get_session(uid)["data"]  = None
    await query.edit_message_text("❌ *Cancelled.*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛠 Back to Admin", callback_data="admin_back", api_kwargs={"style": "primary"})]]))

async def cb_admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    await query.answer()
    sess = get_session(uid)
    sess["is_admin"] = False
    sess["state"]    = None
    await query.edit_message_text("🚪 *Admin Logged Out.*", parse_mode="Markdown")

async def cb_admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    buttons = []
    for cc, svcs in numbers_by_cs.items():
        for svc_id, nums in svcs.items():
            if nums:
                buttons.append([InlineKeyboardButton(
                    f"🗑️ +{cc}/{svc_id} ({len(nums)})",
                    callback_data=f"del_confirm:{cc}:{svc_id}", api_kwargs={"style": "primary"}
                )])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_back", api_kwargs={"style": "success"})])
    await query.edit_message_text("🗑️ *Delete Numbers*\n\nSelect to delete:", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def cb_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    _, cc, svc_id = query.data.split(":")
    count = len(numbers_by_cs.get(cc, {}).get(svc_id, []))
    await query.edit_message_text(
        f"⚠️ *Confirm Deletion*\n\nDelete {count} numbers from +{cc}/{svc_id}?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes", callback_data=f"del_exec:{cc}:{svc_id}", api_kwargs={"style": "danger"}),
             InlineKeyboardButton("❌ No", callback_data="admin_back", api_kwargs={"style": "primary"})],
        ])
    )

async def cb_del_exec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    _, cc, svc_id = query.data.split(":")
    count = len(numbers_by_cs.get(cc, {}).get(svc_id, []))
    if cc in numbers_by_cs and svc_id in numbers_by_cs[cc]:
        del numbers_by_cs[cc][svc_id]
        if not numbers_by_cs[cc]:
            del numbers_by_cs[cc]
    await async_save_numbers()
    await query.edit_message_text(f"✅ *Deleted {count} numbers.*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "success"})]]))

async def cb_goto_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Done.", parse_mode="Markdown")

# ─── Document Handler ───
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    sess = get_session(uid)

    if sess.get("state") != "admin_upload_file":
        return

    doc   = update.message.document
    fname = (doc.file_name or "").lower()

    if not (fname.endswith(".txt") or fname.endswith(".xlsx") or fname.endswith(".xls")):
        return await update.message.reply_text("❌ Only .txt or .xlsx files are supported.")

    svc_id = (sess.get("data") or {}).get("serviceId", "other")
    added  = 0
    file   = await context.bot.get_file(doc.file_id)

    if fname.endswith(".xlsx") or fname.endswith(".xls"):
        try:
            import openpyxl, io
            raw = await file.download_as_bytearray()
            wb  = openpyxl.load_workbook(io.BytesIO(bytes(raw)), read_only=True, data_only=True)
            ws  = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                for cell in row:
                    if cell is None:
                        continue
                    num = re.sub(r"\D", "", str(cell))
                    if not re.match(r"^\d{10,15}$", num):
                        continue
                    cc = get_country_code_from_number(num)
                    if not cc:
                        continue
                    numbers_by_cs.setdefault(cc, {}).setdefault(svc_id, [])
                    if num not in numbers_by_cs[cc][svc_id]:
                        numbers_by_cs[cc][svc_id].append(num)
                        added += 1
                    break
        except Exception as e:
            logger.error(f"XLSX parse error: {e}")
            return await update.message.reply_text(f"❌ Excel file read error: {e}")
    else:
        raw_content = await file.download_as_bytearray()
        lines = raw_content.decode("utf-8", errors="ignore").split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                parts = line.split("|")
                num = parts[0].strip()
                cc  = parts[1].strip() if len(parts) > 1 else get_country_code_from_number(num)
                svc = parts[2].strip() if len(parts) > 2 else svc_id
            else:
                num = re.sub(r"\D", "", line)
                cc  = get_country_code_from_number(num)
                svc = svc_id
            if not re.match(r"^\d{10,15}$", num) or not cc:
                continue
            numbers_by_cs.setdefault(cc, {}).setdefault(svc, [])
            if num not in numbers_by_cs[cc][svc]:
                numbers_by_cs[cc][svc].append(num)
                added += 1

    await async_save_numbers()
    sess["state"] = None
    sess["data"]  = None
    await update.message.reply_text(f"✅ *{added} numbers uploaded successfully!*", parse_mode="Markdown")

# ─── Main Text Handler ───
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    uid  = str(user.id)
    text = update.message.text.strip()

    if uid not in users:
        users[uid] = {
            "id": uid, "username": user.username or "no_username",
            "first_name": user.first_name or "User", "last_name": user.last_name or "",
            "joined": datetime.now().isoformat(), "last_active": datetime.now().isoformat(),
            "verified": False, "referredBy": None, "referralCount": 0,
        }
    users[uid]["last_active"] = datetime.now().isoformat()
    await async_save_users()

    sess = get_session(uid)
    if not sess.get("is_admin") and is_admin(uid):
        sess["is_admin"] = True
    state = sess.get("state")

    if state == "wa_waiting_number":
        sess["state"] = None
        phone = re.sub(r"\D", "", text)
        if len(phone) < 10 or len(phone) > 15:
            return await update.message.reply_text("❌ Invalid number. Example: `8801712345678`", parse_mode="Markdown")

        loading = await update.message.reply_text(
            "⏳ *Pairing code নিচ্ছে...*\n\n⌛ কয়েক সেকেন্ড অপেক্ষা করো।",
            parse_mode="Markdown"
        )

        async def wa_task():
            try:
                # আগে check করো connected কিনা
                current_state = await green_get_state(uid)
                if current_state == "authorized":
                    wa_sessions[uid] = {"connected": True}
                    try: await loading.delete()
                    except: pass
                    await context.bot.send_message(
                        uid,
                        "✅ *WhatsApp Already Connected!*\n\n"
                        "🟢 তোমার WhatsApp ইতিমধ্যে connected আছে।",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔴 Logout / Disconnect", callback_data="wa_disconnect", api_kwargs={"style": "danger"})],
                            [InlineKeyboardButton("📊 Check Status", callback_data="wa_status", api_kwargs={"style": "primary"})],
                        ])
                    )
                    return

                code = await get_wa_pairing_code(phone, uid)
                clean_code = re.sub(r"[^A-Z0-9]", "", code.upper())
                formatted = (clean_code[:4] + "-" + clean_code[4:8]) if len(clean_code) >= 8 else code
                try: await loading.delete()
                except: pass
                await context.bot.send_message(
                    uid,
                    f"🔑 *Pairing Code*\n\n"
                    f"`{formatted}`\n\n"
                    f"📋 *Steps:*\n"
                    f"1. WhatsApp খোলো\n"
                    f"2. Settings → Linked Devices\n"
                    f"3. Link a Device → *Link with phone number*\n"
                    f"4. উপরের code enter করো\n\n"
                    f"✅ Code enter করার পর *Check Status* চাপো।",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Check Status", callback_data="wa_status", api_kwargs={"style": "danger"})],
                        [InlineKeyboardButton("🔄 New Code", callback_data="wa_connect", api_kwargs={"style": "primary"})],
                    ])
                )
                asyncio.create_task(monitor_wa_connection(uid, context))
            except Exception as e:
                try: await loading.delete()
                except: pass
                logger.error(f"WA error: {e}", exc_info=True)
                await context.bot.send_message(
                    uid,
                    f"❌ *Connection failed:* {str(e)[:150]}\n\nকিছুক্ষণ পর আবার try করো।",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Try Again", callback_data="wa_connect", api_kwargs={"style": "success"})]])
                )

        asyncio.create_task(wa_task())
        return

    pending_totp_svc = users.get(uid, {}).get("pending_totp_svc")
    if state == "totp_waiting_secret" or pending_totp_svc:
        sess["state"] = None
        svc = (sess.get("data") or {}).get("service") or pending_totp_svc or "other"

        if uid in users and "pending_totp_svc" in users[uid]:
            del users[uid]["pending_totp_svc"]
            await async_save_users()

        try:
            result = generate_totp(text)
        except Exception as e:
            logger.error(f"TOTP exception uid={uid}: {e}")
            result = None

        if not result:
            await update.message.reply_text(
                "❌ *Invalid secret key!*\n\n"
                "Key টি সঠিক নয়। Authenticator app থেকে exact secret key copy করো।\n"
                "Example format: `JBSWY3DPEHPK3PXP`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data=f"totp:{svc}", api_kwargs={"style": "danger"})],
                    [InlineKeyboardButton("🔙 Back", callback_data="totp_back", api_kwargs={"style": "primary"})],
                ])
            )
            return

        icons = {"facebook": "📘", "instagram": "📸", "google": "🔍", "other": "⚙️"}
        names = {"facebook": "Facebook", "instagram": "Instagram", "google": "Google", "other": "2FA"}
        icon  = icons.get(svc, "🔐")
        name  = names.get(svc, svc)

        secret_quoted = urllib.parse.quote(text)
        cb_data = f"totp_r:{svc}:{secret_quoted}"
        if len(cb_data.encode()) > 62:
            cb_data = f"totp_r:{svc}:TOOLONG"

        try:
            await update.message.reply_text(
                f"{icon} *{name} 2FA Code*\n\n"
                f"🔑 *Code:* `{result['token']}`\n\n"
                f"⏰ *{result['timeRemaining']} seconds remaining*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh Code", callback_data=cb_data, api_kwargs={"style": "success"})],
                    [InlineKeyboardButton("🔙 Back", callback_data="totp_back", api_kwargs={"style": "danger"})],
                ])
            )
        except Exception as e:
            logger.error(f"TOTP reply error uid={uid}: {e}")
            await update.message.reply_text(f"✅ 2FA Code: {result['token']} (⏰ {result['timeRemaining']}s)")
        return

    if state == "w_account":
        sess["state"] = None
        data   = sess.get("data", {})
        method = data.get("method", "bKash")
        amount = data.get("amount", 0)
        e      = get_user_earnings(uid)

        if amount > e["balance"]:
            return await update.message.reply_text("❌ Insufficient balance!")

        icon = "🟣" if method == "bKash" else "🟠"
        sess["state"] = "w_confirm"
        sess["data"]  = {"method": method, "amount": amount, "account": text}

        await update.message.reply_text(
            f"{icon} *Confirm Withdrawal*\n\n"
            f"💳 Method: {method}\n"
            f"📱 Account: `{text}`\n"
            f"💵 Amount: *{amount:.2f} taka*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="w_confirm", api_kwargs={"style": "primary"}),
                 InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", api_kwargs={"style": "success"})],
            ])
        )
        return

    if state == "admin_set_referral_commission" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if 0 <= val <= 50:
                settings["referralCommission"] = val
                save_settings()
                await update.message.reply_text(
                    f"✅ *Referral commission set to {val:.1f}%*\n\n"
                    f"এখন থেকে প্রতি OTP এর {val:.1f}% commission referrer পাবে।",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ 0 থেকে 50 এর মধ্যে দাও।")
        except:
            await update.message.reply_text("❌ Invalid number. Example: `10`", parse_mode="Markdown")
        return

    if state == "global_wa_phone" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        phone = re.sub(r"\D", "", text.strip())
        if len(phone) < 8:
            return await update.message.reply_text("❌ নম্বর ভুল!")
        loading = await update.message.reply_text("⏳ Connecting Global WhatsApp...")
        try:
            code = await get_wa_pairing_code(phone, f"global_{uid}")
            if not code:
                await loading.delete()
                return await update.message.reply_text("❌ Pairing code পাওয়া যায়নি।")
            global_wa_data["phone"]     = phone
            global_wa_data["uid"]       = f"global_{uid}"
            global_wa_data["connected"] = False
            save_global_wa()
            await loading.delete()
            await update.message.reply_text(
                f"📱 *Global WhatsApp Pairing Code:*\n\n"
                f"`{code}`\n\n"
                f"WhatsApp → Linked Devices → Link a Device → Enter code",
                parse_mode="Markdown"
            )
            # verify loop
            async def verify_global_wa():
                for _ in range(20):
                    await asyncio.sleep(15)
                    state_check = await green_get_state(f"global_{uid}")
                    if state_check == "authorized":
                        wa_sessions[f"global_{uid}"] = {"connected": True}
                        global_wa_data["connected"] = True
                        global_wa_data["enabled"]   = True
                        save_global_wa()
                        try:
                            await context.bot.send_message(
                                int(uid),
                                "✅ *Global WhatsApp Connected!*\n\n"
                                "এখন সব user এর number এই WA দিয়ে check হবে।",
                                parse_mode="Markdown"
                            )
                        except: pass
                        return
            asyncio.create_task(verify_global_wa())
        except Exception as e:
            await loading.delete()
            await update.message.reply_text(f"❌ Error: {e}")
        return

    if state == "admin_add_panel" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.strip().split()
        if len(parts) != 3:
            return await update.message.reply_text("❌ Format ভুল!\n`URL username password`", parse_mode="Markdown")
        url, username, password = parts
        ptype  = sess.pop("panel_type", "masdar_client")
        panels = load_panels()
        panels.append({"url": url, "username": username, "password": password, "type": ptype})
        save_panels(panels)
        idx = len(panels) - 1
        otp_panel_tasks[idx] = asyncio.create_task(run_panel(panels[idx], idx, context.application))
        label = PANEL_TYPE_LABEL.get(ptype, ptype)
        await update.message.reply_text(
            f"✅ *Panel Added & Started!*\n\n🔗 `{url}`\n👤 `{username}`\n🏷️ {label}",
            parse_mode="Markdown"
        )
        return

    if state == "admin_broadcast" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        sent = 0
        for target_uid in list(users.keys()):
            try:
                await context.bot.send_message(target_uid, text, parse_mode="Markdown")
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
        await update.message.reply_text(f"✅ *Broadcast sent to {sent} users.*", parse_mode="Markdown")
        return

    if state == "admin_add_numbers" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        added = 0
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                num, cc, svc = parts[0].strip(), parts[1].strip(), parts[2].strip()
            elif len(parts) == 2:
                num, cc, svc = parts[0].strip(), parts[1].strip(), "other"
            else:
                num = line
                cc  = get_country_code_from_number(num)
                svc = "other"
            if re.match(r"^\d{10,15}$", num) and cc:
                numbers_by_cs.setdefault(cc, {}).setdefault(svc, [])
                if num not in numbers_by_cs[cc][svc]:
                    numbers_by_cs[cc][svc].append(num)
                    added += 1
        await async_save_numbers()
        await update.message.reply_text(f"✅ *{added} numbers added!*", parse_mode="Markdown")
        return

    if state == "admin_set_count" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = int(text)
            if 1 <= val <= 100:
                settings["defaultNumberCount"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Number count set to {val}.*", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Enter 1-100.")
        except:
            await update.message.reply_text("❌ Invalid number.")
        return

    if state == "admin_set_cooldown" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = int(text)
            if 1 <= val <= 3600:
                settings["cooldownSeconds"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Cooldown set to {val} seconds.*", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Enter 1-3600.")
        except:
            await update.message.reply_text("❌ Invalid number.")
        return

    if state == "admin_set_price" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val >= 0:
                settings["defaultOtpPrice"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Default OTP price set to {val:.2f} taka.*", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Invalid price.")
        return

    if state == "admin_set_minw" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        try:
            val = float(text)
            if val > 0:
                settings["minWithdraw"] = val
                save_settings()
                await update.message.reply_text(f"✅ *Min withdraw set to {val:.2f} taka.*", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Invalid amount.")
        return

    if state == "admin_add_balance" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 2:
            try:
                target_id = parts[0]
                amount    = float(parts[1])
                e         = get_user_earnings(target_id)
                e["balance"] = round(e["balance"] + amount, 2)
                await async_save_earnings()
                await update.message.reply_text(f"✅ *{amount:.2f} taka added to {target_id}.*", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Error.")
        else:
            await update.message.reply_text("❌ Format: `[userId] [amount]`", parse_mode="Markdown")
        return

    if state == "admin_deduct_balance" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 2:
            try:
                target_id = parts[0]
                amount    = float(parts[1])
                e         = get_user_earnings(target_id)
                e["balance"] = max(0, round(e["balance"] - amount, 2))
                await async_save_earnings()
                await update.message.reply_text(f"✅ *{amount:.2f} taka deducted from {target_id}.*", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Error.")
        return

    if state == "admin_reset_balance" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        target_id = text.strip()
        e = get_user_earnings(target_id)
        e["balance"] = 0
        await async_save_earnings()
        await update.message.reply_text(f"✅ *{target_id}'s balance reset to 0.*", parse_mode="Markdown")
        return

    if state == "admin_set_country_price" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        updated = 0
        for line in text.split("\n"):
            parts = re.split(r"[:\s]+", line.strip())
            if len(parts) >= 2:
                cc    = re.sub(r"\D", "", parts[0])
                try:
                    price = float(parts[1])
                    if cc and price >= 0:
                        country_prices[cc] = price
                        updated += 1
                except:
                    pass
        save_cp()
        await update.message.reply_text(f"✅ *{updated} prices updated!*", parse_mode="Markdown")
        return

    if state == "admin_add_country" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 3:
            cc   = re.sub(r"\D", "", parts[0])
            name = " ".join(parts[1:-1])
            flag = parts[-1]
            countries[cc] = {"name": name, "flag": flag}
            save_countries()
            await update.message.reply_text(f"✅ *Country added!*\n+{cc}: {flag} {name}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Format: `[code] [name] [flag]`", parse_mode="Markdown")
        return

    if state == "admin_add_service" and (sess["is_admin"] or is_admin(uid)):
        sess["state"] = None
        parts = text.split()
        if len(parts) >= 3:
            svc_id   = parts[0].lower()
            svc_name = " ".join(parts[1:-1])
            icon     = parts[-1]
            services[svc_id] = {"name": svc_name, "icon": icon}
            save_services()
            await update.message.reply_text(f"✅ *Service added!*\n`{svc_id}`: {icon} {svc_name}", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Format: `[id] [name] [icon]`", parse_mode="Markdown")
        return

    if state == "w_amount":
        try:
            amount = float(text)
            e      = get_user_earnings(uid)
            method = (sess.get("data") or {}).get("method", "bKash")

            if amount < settings["minWithdraw"]:
                return await update.message.reply_text(f"❌ Minimum {settings['minWithdraw']} taka")
            if amount > e["balance"]:
                return await update.message.reply_text("❌ Insufficient balance!")

            sess["state"] = "w_account"
            sess["data"]  = {"method": method, "amount": amount}
            icon = "🟣" if method == "bKash" else "🟠"
            await update.message.reply_text(
                f"{icon} *{method} — {amount:.2f} taka*\n\n📱 Your {method} number:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="w_cancel", api_kwargs={"style": "danger"})]])
            )
        except:
            pass
        return

# ─── Withdraw Confirm ───
async def cb_withdraw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    if sess.get("state") != "w_confirm":
        return

    data    = sess.get("data", {})
    method  = data.get("method")
    account = data.get("account")
    amount  = data.get("amount")
    e       = get_user_earnings(uid)

    if amount > e["balance"]:
        sess["state"] = None
        return await query.edit_message_text("❌ Balance changed. Please try again.", parse_mode="Markdown")

    e["balance"] = round(e["balance"] - amount, 2)
    await async_save_earnings()

    wid = str(int(time.time() * 1000))
    withdrawals.append({
        "id": wid, "userId": uid,
        "userName": update.effective_user.first_name or "User",
        "userUsername": update.effective_user.username or "",
        "amount": amount, "method": method, "account": account,
        "status": "pending", "requestedAt": datetime.now().isoformat(), "processedAt": None
    })
    await async_save_withdrawals()
    sess["state"] = None
    sess["data"]  = None

    await query.edit_message_text(
        f"✅ *Withdrawal Request Submitted!*\n\n"
        f"💳 {method}\n📱 `{account}`\n💵 {amount:.2f} taka\n\n"
        f"⏳ Admin approval pending.",
        parse_mode="Markdown"
    )

# ─── OTP Group Message Handler ───
async def handle_otp_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    if str(chat_id) != str(OTP_GROUP_ID) and chat_id != OTP_GROUP_ID:
        return

    msg_text = update.message.text or update.message.caption or ""
    msg_id   = update.message.message_id
    if not msg_text:
        return

    logger.info(f"📨 OTP Group [{msg_id}]: {msg_text[:120]}")
    logger.info(f"🔍 Active numbers count: {len(active_numbers)}")
    matched = find_matching_active_number(msg_text)
    if not matched:
        logger.warning(f"⚠️ No active number matched for msg: {msg_text[:200]}")
        return

    data = active_numbers[matched]
    uid  = data["userId"]
    cc   = data.get("countryCode", "")

    if data.get("lastOTP") == msg_id:
        return
    data["lastOTP"] = msg_id
    data["otpCount"] = data.get("otpCount", 0) + 1
    await async_save_active()

    otp_code = extract_otp(msg_text)
    earned   = await add_earning(uid, cc)
    balance  = get_user_earnings(uid)["balance"]
    svc      = services.get(data.get("service",""), {"icon": "📱", "name": "Service"})
    country  = countries.get(cc, {"flag": "🌍", "name": cc})

    notify = (
        f"📨 *OTP Received!*\n\n"
        f"{svc['icon']} *Service:* {svc['name']}\n"
        f"{country['flag']} *Country:* {country['name']}\n"
        f"📞 *Number:* `+{matched}`\n"
    )
    if otp_code:
        notify += f"\n🔑 *OTP Code:* `{otp_code}`\n"
    notify += f"\n💵 *+{earned:.2f} taka earned!*\n💰 *Balance: {balance:.2f} taka*"

    try:
        await context.bot.send_message(uid, notify, parse_mode="Markdown")
        await context.bot.forward_message(uid, OTP_GROUP_ID, msg_id)
    except Exception as e:
        logger.error(f"OTP notify error: {e}")

    otp_log.append({
        "phoneNumber": matched, "userId": uid, "countryCode": cc,
        "service": data.get("service"), "otpCode": otp_code, "earned": earned,
        "messageId": msg_id, "delivered": True,
        "timestamp": datetime.now().isoformat()
    })
    await async_save_otp_log()

# ─── Real-time Group Member Change Handler ───
REQUIRED_GROUP_IDS = {MAIN_CHANNEL_ID, CHAT_GROUP_ID, OTP_GROUP_ID}

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কেউ group ছাড়লে বা join করলে real-time এ handle করো"""
    try:
        cm = update.chat_member
        if not cm:
            return

        chat_id = cm.chat.id
        if chat_id not in REQUIRED_GROUP_IDS:
            return

        user    = cm.new_chat_member.user
        uid     = str(user.id)
        old_status = cm.old_chat_member.status  # আগের status
        new_status = cm.new_chat_member.status  # নতুন status

        LEFT_STATUSES   = {"left", "kicked", "banned"}
        JOINED_STATUSES = {"member", "administrator", "creator"}

        # ── কেউ group ছেড়ে গেলে ──
        if old_status in JOINED_STATUSES and new_status in LEFT_STATUSES:
            logger.info(f"👋 User {uid} left chat {chat_id}")

            if uid not in users:
                return

            # verified=False করো — referral ছাড়া user হলেও
            users[uid]["verified"] = False
            sess = get_session(uid)
            sess["verified"] = False

            # referral ছিল এবং confirmed ছিল → count কমাও
            if users[uid].get("referralVerified", False):
                users[uid]["referralVerified"] = False
                referrer_id = users[uid].get("referredBy")
                if referrer_id and referrer_id in users:
                    users[referrer_id]["referralCount"] = max(0, users[referrer_id].get("referralCount", 0) - 1)
                    if referrer_id in referrals and uid in referrals[referrer_id]:
                        referrals[referrer_id].remove(uid)
                    await async_save_referrals()
                    logger.info(f"📉 Referral removed: uid={uid} left → referrer={referrer_id} count={users[referrer_id]['referralCount']}")
                    try:
                        await context.bot.send_message(
                            int(referrer_id),
                            f"⚠️ *Referral Lost!*\n\n"
                            f"তোমার একজন referred user group ছেড়ে গেছে।\n"
                            f"👥 Current Referrals: *{users[referrer_id]['referralCount']}*",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

            await async_save_users()
            logger.info(f"🔒 Access revoked for uid={uid} (left chat {chat_id})")

        # ── কেউ আবার group এ join করলে — শুধু log করো, verify এ count হবে ──
        elif old_status in LEFT_STATUSES and new_status in JOINED_STATUSES:
            logger.info(f"✅ User {uid} joined chat {chat_id}")

    except Exception as e:
        logger.error(f"handle_chat_member_update error: {e}")

# ─── /cancel command ───
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    sess = get_session(uid)
    sess["state"] = None
    sess["data"]  = None
    if is_admin(uid):
        sess["is_admin"] = True
    await update.message.reply_text("✅ Cancelled.", reply_markup=main_keyboard())

# ─── Periodic scheduled check ───
async def scheduled_membership_check(app):
    while True:
        await asyncio.sleep(30 * 60)  # ৩০ মিনিট পর পর background check
        if not settings.get("requireVerification", True):
            continue
        logger.info(f"🔄 [Scheduled] Checking {len(users)} users...")
        blocked = 0
        for uid, user in list(users.items()):
            try:
                membership = await check_membership(int(uid), app)
                if not membership["allJoined"]:
                    users[uid]["verified"] = False
                    blocked += 1
                    sess = get_session(uid)
                    sess["verified"] = False

                    # ── রেফার কাউন্ট কমাও যদি আগে verified ছিল ──
                    if users[uid].get("referralVerified", False):
                        users[uid]["referralVerified"] = False
                        referrer_id = users[uid].get("referredBy")
                        if referrer_id and referrer_id in users:
                            current_count = users[referrer_id].get("referralCount", 0)
                            users[referrer_id]["referralCount"] = max(0, current_count - 1)
                            # referrals list থেকেও সরাও
                            if referrer_id in referrals and uid in referrals[referrer_id]:
                                referrals[referrer_id].remove(uid)
                            await async_save_referrals()
                            logger.info(f"📉 Referral removed: uid={uid} left group → referrer={referrer_id} count={users[referrer_id]['referralCount']}")
                            try:
                                await app.bot.send_message(
                                    int(referrer_id),
                                    f"⚠️ *Referral Lost!*\n\n"
                                    f"তোমার একজন referred user group ছেড়ে গেছে।\n"
                                    f"👥 Current Referrals: *{users[referrer_id]['referralCount']}*",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass

                    try:
                        pass  # message পাঠানো বন্ধ
                    except:
                        pass
                else:
                    users[uid]["verified"] = True
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Scheduled check error for {uid}: {e}")
        await async_save_users()
        logger.info(f"✅ [Scheduled] {blocked} users blocked.")

# ═══════════════════════════════════════════════
# ─── OTP Panel Scraping System ───
# ═══════════════════════════════════════════════

PANELS_FILE     = os.path.join(DATA_DIR, "panels.json")
otp_panel_tasks   = {}   # { index: asyncio.Task }
otp_panel_status  = {}   # { index: "running" | "stopped" | "error" }
otp_seen_ids      = set()

def load_panels() -> list:
    return load_json(PANELS_FILE, [])

def save_panels(panels: list):
    save_json(PANELS_FILE, panels)

def scraper_extract_otp(message: str):
    if not message: return None
    cleaned = re.sub(r'\b(19|20)\d{2}[-/]\d{2}[-/]\d{2}\b', '', message)
    cleaned = re.sub(r'\b(19|20)\d{2}\b', '', cleaned)
    for p in [
        r'FB-(\d{5})', r'[Gg]-(\d{6})',
        r'(?:otp|code|pin|verification|كود|رمز|কোড)[^\d]{0,15}(\d{4,8})',
        r'(?:is|has|:)\s*(\d{4,8})\b',
        r'(\d{3}[- ]\d{3})', r'\b(\d{6})\b', r'\b(\d{4,8})\b',
    ]:
        m = re.search(p, cleaned, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(' ', '').replace('-', '')
            if 4 <= len(raw) <= 8:
                return raw
    return None

def scraper_detect_service(message: str, range_name: str = "") -> str:
    combined = (message + " " + range_name).lower()
    for svc, pat in {
        'whatsapp': r'whatsapp|واتساب', 'telegram': r'telegram',
        'facebook': r'facebook|fb\.com', 'instagram': r'instagram',
        'google':   r'google|gmail',     'microsoft': r'microsoft|outlook',
        'twitter':  r'twitter|x\.com',   'tiktok':    r'tiktok',
        'snapchat': r'snapchat',
    }.items():
        if re.search(pat, combined, re.IGNORECASE):
            return svc
    return "other"

async def panel_login(session, url: str, username: str, password: str) -> bool:
    """Auto-detect panel type and login"""
    # ── Masdar panel (ints/login) ──
    if await _masdar_login(session, url, username, password):
        return True
    # ── IMS panel (login) ──
    if await _ims_login(session, url, username, password):
        return True
    return False

async def _masdar_login(session, url: str, username: str, password: str) -> bool:
    try:
        from bs4 import BeautifulSoup as _BS
        async with session.get(f"{url}/ints/login", ssl=False, timeout=15) as r:
            if r.status != 200: return False
            soup = _BS(await r.text(), "html.parser")
            capt = "5"
            inp  = soup.find("input", {"name": "capt"})
            if inp:
                nums = re.findall(r'\d+', (inp.find_parent("div") or inp).get_text())
                if len(nums) >= 2:
                    capt = str(int(nums[0]) + int(nums[1]))

        async with session.post(
            f"{url}/ints/signin",
            data={"username": username, "password": password, "capt": capt},
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": f"{url}/ints/login", "Origin": url},
            allow_redirects=True, ssl=False, timeout=15
        ) as r:
            if "login" not in str(r.url).lower():
                logger.info(f"✅ Masdar login OK: {url}")
                return True
            return False
    except Exception as e:
        logger.debug(f"Masdar login failed {url}: {e}")
        return False

async def _ims_login(session, url: str, username: str, password: str) -> bool:
    try:
        from bs4 import BeautifulSoup as _BS
        login_url = f"{url}/login"
        async with session.get(login_url, ssl=False, timeout=15) as r:
            if r.status != 200: return False
            text = await r.text()
            soup = _BS(text, "html.parser")
            # captcha
            capt = "5"
            math = re.search(r'(\d+)\s*([\+\-])\s*(\d+)', text)
            if math:
                a, op, b = int(math.group(1)), math.group(2), int(math.group(3))
                capt = str(a + b) if op == '+' else str(a - b)
            # etkk token
            etkk_input = soup.find("input", {"name": "etkk"})
            etkk_val   = etkk_input.get("value", "") if etkk_input else ""

        async with session.post(
            f"{url}/signin",
            data={"etkk": etkk_val, "username": username, "password": password, "capt": capt},
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": login_url},
            allow_redirects=True, ssl=False, timeout=15
        ) as r:
            text = await r.text()
            if username in text or "CDR" in text or "dashboard" in str(r.url).lower():
                logger.info(f"✅ IMS login OK: {url}")
                return True
            return False
    except Exception as e:
        logger.debug(f"IMS login failed {url}: {e}")
        return False

async def panel_fetch_sms(session, url: str, panel_type: str = "masdar_client") -> list:
    TYPE_MAP = {
        "masdar_client": {"path": "/ints/client/res/data_smscdr.php",
                          "ref":  "/ints/client/SMSCDRStats", "cols": 7, "idx": 4},
        "masdar_agent":  {"path": "/ints/agent/res/data_smscdr.php",
                          "ref":  "/ints/agent/SMSCDRStats",  "cols": 7, "idx": 4},
        "ims_client":    {"path": "/client/res/data_smscdr.php",
                          "ref":  "/client/SMSCDRStats",      "cols": 9, "idx": 5},
        "ims_agent":     {"path": "/agent/res/data_smscdr.php",
                          "ref":  "/agent/SMSCDRReports",     "cols": 9, "idx": 5},
    }
    cfg   = TYPE_MAP.get(panel_type, TYPE_MAP["masdar_client"])
    today = datetime.now().strftime('%Y-%m-%d')
    ts    = int(time.time() * 1000)
    params = {
        "fdate1": today + " 00:00:00",
        "fdate2": today + " 23:59:59",
        "frange": "", "fnum": "", "fcli": "", "fg": "0",
        "sEcho": "1", "iColumns": str(cfg["cols"]),
        "iDisplayStart": "0", "iDisplayLength": "100",
        "sSearch": "", "bRegex": "false",
        "iSortCol_0": "0", "sSortDir_0": "desc", "iSortingCols": "1",
        "_": ts,
    }
    for i in range(cfg["cols"]):
        params[f"mDataProp_{i}"] = str(i)
    try:
        async with session.get(
            url + cfg["path"], params=params, ssl=False, timeout=15,
            headers={"X-Requested-With": "XMLHttpRequest",
                     "Referer": url + cfg["ref"]}
        ) as r:
            if r.status != 200: return []
            data   = json.loads(await r.text())
            result = []
            for item in data.get("aaData", []):
                if not isinstance(item, list) or len(item) <= cfg["idx"]: continue
                if isinstance(item[0], str) and item[0].startswith('0,0,0,0'): continue
                otp = scraper_extract_otp(str(item[cfg["idx"]]))
                if otp:
                    result.append({
                        "timestamp": str(item[0]),
                        "number":    re.sub(r"\D", "", str(item[2])) if len(item) > 2 else "",
                        "range":     str(item[1]) if len(item) > 1 else "",
                        "message":   str(item[cfg["idx"]]),
                        "otp":       otp,
                    })
            return result
    except Exception as e:
        logger.error(f"❌ fetch_sms error {url}: {e}")
        return []

async def _masdar_fetch(session, url: str):
    try:
        now  = datetime.now()
        s_dt = now.strftime('%Y-%m-%d') + '%2000:00:00'
        e_dt = now.strftime('%Y-%m-%d') + '%2023:59:59'
        ts   = int(time.time() * 1000)
        api  = (
            f"{url}/ints/client/res/data_smscdr.php?"
            f"fdate1={s_dt}&fdate2={e_dt}&frange=&fnum=&fcli=&fg=0&"
            f"sEcho=1&iColumns=7&sColumns=%2C%2C%2C%2C%2C%2C&"
            f"iDisplayStart=0&iDisplayLength=100&"
            f"mDataProp_0=0&mDataProp_1=1&mDataProp_2=2&"
            f"mDataProp_3=3&mDataProp_4=4&mDataProp_5=5&mDataProp_6=6&"
            f"sSearch=&bRegex=false&iSortCol_0=0&sSortDir_0=desc&iSortingCols=1&_={ts}"
        )
        async with session.get(api, ssl=False, timeout=15,
            headers={"X-Requested-With": "XMLHttpRequest",
                     "Referer": f"{url}/ints/client/SMSCDRStats"}) as r:
            if r.status != 200: return None
            data = json.loads(await r.text())
            result = []
            for item in data.get("aaData", []):
                if not isinstance(item, list) or len(item) < 5: continue
                if isinstance(item[0], str) and item[0].startswith('0,0,0,0'): continue
                otp = scraper_extract_otp(str(item[4]))
                if otp:
                    result.append({
                        "timestamp": str(item[0]),
                        "number":    re.sub(r"\D", "", str(item[2])),
                        "range":     str(item[1]),
                        "message":   str(item[4]),
                        "otp":       otp,
                    })
            return result
    except:
        return None

async def _ims_fetch(session, url: str):
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        ts    = int(time.time() * 1000)
        params = {
            "fdate1": f"{today} 00:00:00",
            "fdate2": f"{today} 23:59:59",
            "frange": "", "fnum": "", "fcli": "", "fg": "0",
            "sEcho": "1", "iColumns": "9",
            "iDisplayStart": "0", "iDisplayLength": "100",
            "mDataProp_0": "0", "mDataProp_1": "1", "mDataProp_2": "2",
            "mDataProp_3": "3", "mDataProp_4": "4", "mDataProp_5": "5",
            "mDataProp_6": "6", "mDataProp_7": "7", "mDataProp_8": "8",
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "desc", "iSortingCols": "1",
            "_": ts
        }
        api = f"{url}/agent/res/data_smscdr.php"
        async with session.get(api, params=params, ssl=False, timeout=15,
            headers={"X-Requested-With": "XMLHttpRequest",
                     "Referer": f"{url}/agent/SMSCDRReports"}) as r:
            if r.status != 200: return None
            data = json.loads(await r.text())
            result = []
            for item in data.get("aaData", []):
                if not isinstance(item, list) or len(item) < 6: continue
                otp = scraper_extract_otp(str(item[5]))
                if otp:
                    result.append({
                        "timestamp": str(item[0]),
                        "number":    re.sub(r"\D", "", str(item[2])),
                        "range":     str(item[1]),
                        "message":   str(item[5]),
                        "otp":       otp,
                    })
            return result
    except:
        return None

async def run_panel(panel: dict, idx: int, app):
    import aiohttp as _aio
    url      = panel["url"].rstrip("/")
    username = panel["username"]
    password = panel["password"]
    logger.info(f"🚀 Panel #{idx+1} started: {url}")
    otp_panel_status[idx] = "running"

    async with _aio.ClientSession(
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
        cookie_jar=_aio.CookieJar(unsafe=True)
    ) as session:
        last_login    = 0
        fail_count    = 0
        previous_otps = set()  # এই run এ যা পাঠিয়েছি
        while True:
            try:
                # ── Login / Re-login ──
                if time.time() - last_login > 540:
                    ok = await panel_login(session, url, username, password)
                    if not ok:
                        fail_count += 1
                        if fail_count >= 3:
                            otp_panel_status[idx] = "error"
                            logger.error(f"❌ Panel #{idx+1} login failed 3 times, stopping.")
                            return
                        await asyncio.sleep(60)
                        continue
                    last_login = time.time()
                    fail_count = 0
                    otp_panel_status[idx] = "running"

                # ── SMS Fetch ──
                sms_list = await panel_fetch_sms(session, url, panel.get("type", "masdar_client"))

                for sms in sms_list:
                    otp_id = f"{sms['number']}_{sms['otp']}_{sms['timestamp']}"
                    if otp_id in previous_otps:
                        continue
                    previous_otps.add(otp_id)
                    # memory limit
                    if len(previous_otps) > 50000:
                        previous_otps = set(list(previous_otps)[-20000:])

                    # ── active_numbers fresh reload ──
                    fresh_active = load_json(ACTIVE_NUMBERS_FILE, {})
                    if fresh_active and set(fresh_active.keys()) != set(active_numbers.keys()):
                        active_numbers.clear()
                        active_numbers.update(fresh_active)
                        rebuild_suffix_index()

                    number  = sms["number"].lstrip("0")
                    matched = find_active_number(number)

                    if not matched:
                        continue
                    an   = active_numbers[matched]
                    uid  = an["userId"]
                    cc   = an.get("countryCode", "")
                    svc_id = scraper_detect_service(sms["message"], sms["range"])

                    earned  = await add_earning(uid, cc)
                    balance = get_user_earnings(uid)["balance"]
                    svc     = services.get(svc_id, {"icon": "📱", "name": svc_id.capitalize()})
                    country = countries.get(cc, {"flag": "🌍", "name": cc})

                    notify = (
                        f"📨 *OTP Received!*\n\n"
                        f"{svc['icon']} *Service:* {svc['name']}\n"
                        f"{country['flag']} *Country:* {country['name']}\n"
                        f"📞 *Number:* `+{matched}`\n"
                        f"\n🔑 *OTP Code:* `{sms['otp']}`\n"
                        f"\n💵 *+{earned:.2f} taka earned!*\n"
                        f"💰 *Balance: {balance:.2f} taka*"
                    )

                    try:
                        await app.bot.send_message(int(uid), notify, parse_mode="Markdown")
                        logger.info(f"✅ OTP sent to user: +{matched} → uid={uid} otp={sms['otp']}")
                    except Exception as e:
                        logger.error(f"❌ notify error uid={uid}: {e}")

                    otp_log.append({
                        "phoneNumber": matched, "userId": uid, "countryCode": cc,
                        "service": svc_id, "otpCode": sms["otp"], "earned": earned,
                        "messageId": None, "delivered": True,
                        "source": f"panel_{url}",
                        "timestamp": datetime.now().isoformat()
                    })
                    await async_save_otp_log()
                    await asyncio.sleep(0.3)  # Telegram rate limit এর জন্য ছোট delay

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                otp_panel_status[idx] = "stopped"
                logger.info(f"⏹️ Panel #{idx+1} stopped")
                return
            except Exception as e:
                otp_panel_status[idx] = "error"
                logger.error(f"❌ Panel #{idx+1} error: {e}")
                await asyncio.sleep(30)

def start_all_panels(app):
    rebuild_suffix_index()  # startup এ index তৈরি করো
    panels = load_panels()
    for i, p in enumerate(panels):
        if i not in otp_panel_tasks or otp_panel_tasks[i].done():
            otp_panel_tasks[i] = asyncio.create_task(run_panel(p, i, app))
    logger.info(f"📡 {len(panels)} panel(s) started")

# ── Admin Panel Callbacks ──
PANEL_TYPE_LABEL = {
    "masdar_client": "Masdar Client",
    "masdar_agent":  "Masdar Agent",
    "ims_client":    "IMS Client",
    "ims_agent":     "IMS Agent",
}

async def cb_admin_panels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    panels = load_panels()
    msg = f"📡 *OTP Panels*\n\nTotal: *{len(panels)}*\n\n"
    for i, p in enumerate(panels):
        status = otp_panel_status.get(i, "stopped")
        if status == "running":   icon = "🟢 Running"
        elif status == "error":   icon = "🔴 Login Failed"
        else:                     icon = "⚫ Stopped"
        label = PANEL_TYPE_LABEL.get(p.get('type', ''), p.get('type', ''))
        msg += f"*{i+1}.* `{p['url']}`\n👤 `{p['username']}` | 🏷️ {label} | {icon}\n\n"
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Panel", callback_data="panel_add:auto", api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("🗑️ Delete Panel", callback_data="panel_del", api_kwargs={"style": "danger"}),
         InlineKeyboardButton("🔄 Restart All",  callback_data="panel_restart", api_kwargs={"style": "success"})],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
    ]))

async def cb_admin_global_wa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()

    connected = global_wa_data.get("connected", False)
    enabled   = global_wa_data.get("enabled", False)
    phone     = global_wa_data.get("phone", "N/A")

    status_icon = "🟢" if connected else "🔴"
    toggle_icon = "✅ ON" if enabled else "❌ OFF"

    msg = (
        f"📱 *Global WhatsApp System*\n\n"
        f"*Status:* {status_icon} {'Connected' if connected else 'Disconnected'}\n"
        f"*Phone:* `{phone}`\n"
        f"*WA Check:* {toggle_icon}\n\n"
        f"একটা WhatsApp connect করলে সব user এর number check হবে।"
    )

    buttons = []
    if connected:
        buttons.append([
            InlineKeyboardButton(
                f"{'🔴 Disable' if enabled else '🟢 Enable'} WA Check",
                callback_data="global_wa_toggle",
                api_kwargs={"style": "success" if not enabled else "danger"}
            ),
            InlineKeyboardButton("🔌 Disconnect", callback_data="global_wa_disconnect", api_kwargs={"style": "danger"})
        ])
    else:
        buttons.append([InlineKeyboardButton("📱 Connect WhatsApp", callback_data="global_wa_connect", api_kwargs={"style": "primary"})])

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})])
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_global_wa_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    await query.answer()
    get_session(uid)["state"] = "global_wa_phone"
    await query.edit_message_text(
        "📱 *Global WhatsApp Connect*\n\n"
        "WhatsApp নম্বর দাও (country code সহ):\n"
        "Example: `8801712345678`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="admin_global_wa", api_kwargs={"style": "danger"})
        ]])
    )

async def cb_global_wa_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    global_wa_data["enabled"] = not global_wa_data.get("enabled", False)
    save_global_wa()
    status = "✅ চালু" if global_wa_data["enabled"] else "❌ বন্ধ"
    await query.answer(f"Global WA Check {status}", show_alert=True)
    await cb_admin_global_wa(update, context)

async def cb_global_wa_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    wa_uid = global_wa_data.get("uid", "")
    if wa_uid and wa_uid in wa_sessions:
        wa_sessions.pop(wa_uid, None)
    global_wa_data["connected"] = False
    global_wa_data["phone"]     = ""
    global_wa_data["enabled"]   = False
    save_global_wa()
    await query.answer("🔌 Global WA Disconnected", show_alert=True)
    await cb_admin_global_wa(update, context)

# ─── Global WA handle_text ───
# (handle_text এ state "global_wa_phone" handle করা হবে)
    query = update.callback_query
    uid   = str(update.effective_user.id)
    if not get_session(uid)["is_admin"] and not is_admin(uid):
        return await query.answer("❌ Admin only")
    await query.answer()
    panels = load_panels()
    msg = f"📡 *OTP Panels*\n\nTotal: *{len(panels)}*\n\n"
    for i, p in enumerate(panels):
        status = otp_panel_status.get(i, "stopped")
        if status == "running":
            icon = "🟢 Running"
        elif status == "error":
            icon = "🔴 Login Failed"
        else:
            icon = "⚫ Stopped"
        label = PANEL_TYPE_LABEL.get(p.get('type', ''), p.get('type', ''))
        msg += f"*{i+1}.* `{p['url']}`\n👤 `{p['username']}` | 🏷️ {label} | {icon}\n\n"

    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Panel", callback_data="panel_add:auto", api_kwargs={"style": "primary"})],
        [InlineKeyboardButton("🗑️ Delete Panel", callback_data="panel_del", api_kwargs={"style": "danger"}),
         InlineKeyboardButton("🔄 Restart All",  callback_data="panel_restart", api_kwargs={"style": "success"})],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back", api_kwargs={"style": "primary"})],
    ]))

async def cb_panel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid   = str(update.effective_user.id)
    await query.answer()
    ptype = query.data.split(":")[1] if ":" in query.data else "masdar_client"
    get_session(uid)["state"]      = "admin_add_panel"
    get_session(uid)["panel_type"] = ptype
    label = PANEL_TYPE_LABEL.get(ptype, ptype)
    await query.edit_message_text(
        f"➕ *Add {label} Panel*\n\n"
        f"Format: `URL username password`\n\n"
        f"Example:\n`http://139.99.69.196 admin admin123`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="admin_panels", api_kwargs={"style": "danger"})
        ]])
    )

async def cb_panel_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    panels = load_panels()
    if not panels:
        return await query.edit_message_text("❌ কোনো panel নেই।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panels")]]))
    buttons = [[InlineKeyboardButton(f"🗑️ {i+1}. {p['url']}", callback_data=f"panel_del_confirm:{i}")]
               for i, p in enumerate(panels)]
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panels", api_kwargs={"style": "primary"})])
    await query.edit_message_text("🗑️ *কোন panel delete করবে?*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def cb_panel_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx    = int(query.data.split(":")[1])
    panels = load_panels()
    if 0 <= idx < len(panels):
        removed = panels.pop(idx)
        save_panels(panels)
        if idx in otp_panel_tasks and not otp_panel_tasks[idx].done():
            otp_panel_tasks[idx].cancel()
            otp_panel_tasks.pop(idx, None)
        await query.edit_message_text(f"✅ *Deleted:* `{removed['url']}`", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panels")]]))

async def cb_panel_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Restarting...")
    for task in otp_panel_tasks.values():
        if not task.done():
            task.cancel()
    otp_panel_tasks.clear()
    start_all_panels(context.application)
    await query.edit_message_text("✅ *All panels restarted!*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panels")]]))

# ─── Main ───
def main():
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("adminlogin", cmd_adminlogin))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    app.add_handler(MessageHandler(filters.Regex("^(☎️ Get Number|📞 Get Numbers)$"), handle_get_numbers))
    app.add_handler(MessageHandler(filters.Regex("^📧"), handle_tempmail))
    app.add_handler(MessageHandler(filters.Regex("^🔐"), handle_2fa))
    app.add_handler(MessageHandler(filters.Regex("^💰 Balances$"), handle_balance))
    app.add_handler(MessageHandler(filters.Regex("^💸 Withdraw$"), handle_withdraw))
    app.add_handler(MessageHandler(filters.Regex("^👥 Referral$"), handle_referral))
    app.add_handler(MessageHandler(filters.Regex("^💬 Support$"), handle_support))

    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_document))

    app.add_handler(CallbackQueryHandler(cb_verify, pattern="^verify_user$"))
    app.add_handler(CallbackQueryHandler(cb_select_service, pattern="^svc:"))
    app.add_handler(CallbackQueryHandler(cb_select_country, pattern="^cc:"))
    app.add_handler(CallbackQueryHandler(cb_new_numbers, pattern="^newnum:"))
    app.add_handler(CallbackQueryHandler(cb_back_services, pattern="^back_services$"))

    app.add_handler(CallbackQueryHandler(cb_start_withdraw, pattern="^start_withdraw$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_method, pattern="^wm:"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_amount, pattern="^wa:"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_cancel, pattern="^w_cancel$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_confirm, pattern="^w_confirm$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_history, pattern="^withdraw_history$"))
    app.add_handler(CallbackQueryHandler(cb_goto_main, pattern="^goto_main$"))

    app.add_handler(CallbackQueryHandler(cb_wa_connect, pattern="^wa_connect$"))
    app.add_handler(CallbackQueryHandler(cb_wa_status, pattern="^wa_status$"))
    app.add_handler(CallbackQueryHandler(cb_wa_disconnect, pattern="^wa_disconnect$"))

    app.add_handler(CallbackQueryHandler(cb_tm_create, pattern="^tm_create$"))
    app.add_handler(CallbackQueryHandler(cb_tm_inbox, pattern="^tm_inbox$"))
    app.add_handler(CallbackQueryHandler(cb_tm_show, pattern="^tm_show$"))
    app.add_handler(CallbackQueryHandler(cb_tm_delete, pattern="^tm_delete$"))

    app.add_handler(CallbackQueryHandler(cb_totp_service, pattern="^totp:"))
    app.add_handler(CallbackQueryHandler(cb_totp_back, pattern="^totp_back$"))
    app.add_handler(CallbackQueryHandler(cb_totp_refresh, pattern="^totp_r:"))

    app.add_handler(CallbackQueryHandler(cb_ref_stats, pattern="^ref_stats$"))

    app.add_handler(CallbackQueryHandler(cb_admin_stock, pattern="^admin_stock$"))
    app.add_handler(CallbackQueryHandler(cb_admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(cb_admin_otp_log, pattern="^admin_otp_log$"))
    app.add_handler(CallbackQueryHandler(cb_admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(cb_admin_settings, pattern="^admin_settings$"))
    app.add_handler(CallbackQueryHandler(cb_admin_toggle_verify, pattern="^as_toggle_verify$"))
    app.add_handler(CallbackQueryHandler(cb_admin_toggle_withdraw, pattern="^as_toggle_withdraw$"))
    app.add_handler(CallbackQueryHandler(cb_as_count, pattern="^as_count$"))
    app.add_handler(CallbackQueryHandler(cb_as_cooldown, pattern="^as_cooldown$"))
    app.add_handler(CallbackQueryHandler(cb_as_price, pattern="^as_price$"))
    app.add_handler(CallbackQueryHandler(cb_as_minw, pattern="^as_minw$"))
    app.add_handler(CallbackQueryHandler(cb_as_referral_commission, pattern="^as_referral_commission$"))
    app.add_handler(CallbackQueryHandler(cb_admin_referral_stats, pattern="^admin_referral_stats$"))
    app.add_handler(CallbackQueryHandler(cb_admin_add_numbers, pattern="^admin_add_numbers$"))
    app.add_handler(CallbackQueryHandler(cb_admin_withdrawals, pattern="^admin_withdrawals$"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_approve, pattern="^wadm_approve:"))
    app.add_handler(CallbackQueryHandler(cb_withdraw_reject, pattern="^wadm_reject:"))
    app.add_handler(CallbackQueryHandler(cb_admin_balance_manage, pattern="^admin_balance_manage$"))
    app.add_handler(CallbackQueryHandler(cb_bal_add, pattern="^bal_add$"))
    app.add_handler(CallbackQueryHandler(cb_bal_deduct, pattern="^bal_deduct$"))
    app.add_handler(CallbackQueryHandler(cb_bal_reset, pattern="^bal_reset$"))
    app.add_handler(CallbackQueryHandler(cb_admin_country_prices, pattern="^admin_country_prices$"))
    app.add_handler(CallbackQueryHandler(cb_admin_manage_countries, pattern="^admin_manage_countries$"))
    app.add_handler(CallbackQueryHandler(cb_country_list, pattern="^country_list$"))
    app.add_handler(CallbackQueryHandler(cb_country_add, pattern="^country_add$"))
    app.add_handler(CallbackQueryHandler(cb_admin_manage_services, pattern="^admin_manage_services$"))
    app.add_handler(CallbackQueryHandler(cb_svc_list, pattern="^svc_list$"))
    app.add_handler(CallbackQueryHandler(cb_svc_add, pattern="^svc_add$"))
    app.add_handler(CallbackQueryHandler(cb_admin_upload, pattern="^admin_upload$"))
    app.add_handler(CallbackQueryHandler(cb_upload_svc, pattern="^upload_svc:"))
    app.add_handler(CallbackQueryHandler(cb_admin_delete, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(cb_del_confirm, pattern="^del_confirm:"))
    app.add_handler(CallbackQueryHandler(cb_del_exec, pattern="^del_exec:"))
    app.add_handler(CallbackQueryHandler(cb_admin_back, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(cb_admin_cancel, pattern="^admin_cancel$"))
    app.add_handler(CallbackQueryHandler(cb_admin_logout, pattern="^admin_logout$"))

    app.add_handler(CallbackQueryHandler(cb_admin_global_wa, pattern="^admin_global_wa$"))
    app.add_handler(CallbackQueryHandler(cb_global_wa_connect, pattern="^global_wa_connect$"))
    app.add_handler(CallbackQueryHandler(cb_global_wa_toggle, pattern="^global_wa_toggle$"))
    app.add_handler(CallbackQueryHandler(cb_global_wa_disconnect, pattern="^global_wa_disconnect$"))
    app.add_handler(CallbackQueryHandler(cb_admin_panels, pattern="^admin_panels$"))
    app.add_handler(CallbackQueryHandler(cb_panel_add, pattern="^panel_add:"))
    app.add_handler(CallbackQueryHandler(cb_panel_del, pattern="^panel_del$"))
    app.add_handler(CallbackQueryHandler(cb_panel_del_confirm, pattern="^panel_del_confirm:"))
    app.add_handler(CallbackQueryHandler(cb_panel_restart, pattern="^panel_restart$"))

    app.add_handler(MessageHandler(filters.Chat(OTP_GROUP_ID) & ~filters.COMMAND, handle_otp_group_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text))

    # ── Real-time group member change (leave/join) ──
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    async def post_init(application):
        global _tg_app
        _tg_app = application
        asyncio.create_task(scheduled_membership_check(application))
        asyncio.create_task(green_api_monitor(application))
        await start_http_server()
        start_all_panels(application)  # ── OTP Panels শুরু করো ──

    app.post_init = post_init

    logger.info("="*50)
    logger.info("🚀 Starting Earning Hub Bot (Python)...")
    logger.info(f"📢 Main Channel: {MAIN_CHANNEL_ID}")
    logger.info(f"💬 Chat Group: {CHAT_GROUP_ID}")
    logger.info(f"📨 OTP Group: {OTP_GROUP_ID}")
    logger.info("="*50)

    app.run_polling(allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"])

if __name__ == "__main__":
    main()
