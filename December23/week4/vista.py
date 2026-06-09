"""
VISTA — Verification & Integrated Systems for Trusted Analytics
Single-file Flask app. No internet required after install.
Run: python vista_app.py  →  open http://localhost:8000

SECTIONS IN THIS FILE:
  §1  Imports & Flask Setup
  §2  Database / API connectivity  (graceful fallback if unavailable)
  §3  Core matching functions      (near_strict, near_round, compute_mode, large_diff)
  §4  Action constants & colours   (4 actions: No Action / Push / Review / Escalate)
  §5  Rules config                 (DEFAULT_RULES, load_rules, save_rules)
  §6  Decision logic               (apply_logic — Entry Gates + Sections A–F + Prebuilt_num group)
  §7  Excel & API processing       (process_dataframe, process_excel_bytes, process_api_records)
  §8  Main UI HTML page            (PAGE)
  §9  Rules editor HTML page       (RULES_PAGE, HISTORY_PAGE)
  §10 Rule groups & editor data    (RULE_GROUPS, ALL_ACTIONS)
  §11 Flask routes                 (@app.route)
  §12 Entry point
"""

# ══════════════════════════════════════════════════════════════════
#  §1  IMPORTS & FLASK SETUP
# ══════════════════════════════════════════════════════════════════

import io, math, json, os, datetime, functools
import numpy as np
import pandas as pd
from flask import Flask, request, send_file, jsonify, render_template_string, redirect
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import base64
import re as _re


app = Flask(__name__) 
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB


# ══════════════════════════════════════════════════════════════════
#  §2  DATABASE / API CONNECTIVITY  (graceful fallback)
# ══════════════════════════════════════════════════════════════════

import requests as _requests
from requests.auth import HTTPBasicAuth

# Try to load DB settings — if unavailable the app still runs in file-upload mode
_db_available = False
_ticker_list   = []

try:
    from dotenv import load_dotenv
    from pydantic_settings import BaseSettings, SettingsConfigDict
    import pyodbc

    load_dotenv()

    class AppConfig(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")
        server34:   str
        database34: str
        username34: str
        password34: str
        apiusername :str
        apipassword :str
        DATA_API_URL :str
    _settings = AppConfig()

    def _get_conn_str() -> str:
        s = _settings
        return (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={s.server34};DATABASE={s.database34};"
            f"UID={s.username34};PWD={s.password34}"
        )

    # Probe the DB at startup — populate ticker list if reachable
    try:
        with pyodbc.connect(_get_conn_str(), timeout=5) as _c:
            _cur = _c.cursor()
            _cur.execute("SELECT DISTINCT Ticker FROM [TickerInfo] WITH(NOLOCK)")
            _ticker_list = [r[0] for r in _cur.fetchall()]
        _db_available = True
    except Exception as _e:
        print(f"[VISTA] DB not reachable ({_e}) — running in file-upload mode")

except Exception as _imp_e:
    print(f"[VISTA] DB dependencies not installed ({_imp_e}) — running in file-upload mode")



def fetch_ticker_data(ticker: str) -> list:
    s = _settings
    """Fetch rows for a ticker from the live API. Raises on failure."""
    userpass = f"{s.apiusername}:{s.apipassword}"
    b64 = base64.b64encode(userpass.encode()).decode()
    headers = {
        "Authorization": f"Basic {b64}",
        "User-Agent": "python-requests/2.31",
        "Accept": "application/json",
    }
    url  = f"{s.DATA_API_URL}Tickername={ticker}"
    try:
        resp = _requests.get(url, timeout=600, headers=headers)
    except _requests.exceptions.ConnectionError:
        raise ConnectionError(f"API unreachable — cannot connect to data server. Check network/VPN.")
    except _requests.exceptions.Timeout:
        raise TimeoutError(f"API timed out after 180s for ticker '{ticker}'. Try again or use Excel upload.")

    if resp.status_code == 401 or resp.status_code == 403:
        raise PermissionError(f"API authentication failed ({resp.status_code}). Check API credentials in .env.")
    if resp.status_code == 404:
        raise ValueError(f"Ticker '{ticker}' not found on API (404). Verify the ticker symbol.")
    if resp.status_code == 500:
        raise RuntimeError(f"Data API server error (500) for ticker '{ticker}'. The API is having issues — try again later or use Excel upload.")
    if not resp.ok:
        raise RuntimeError(f"API returned HTTP {resp.status_code} for ticker '{ticker}'.")

    data = resp.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    raise ValueError(f"Unexpected API response format for '{ticker}': {type(data)}")


# ══════════════════════════════════════════════════════════════════
#  §3  CORE MATCHING FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _isval(x) -> bool:
    """Fast inline check: is x a valid finite number."""
    return isinstance(x, (int, float)) and not math.isnan(x)

TOL = 0.01


@functools.lru_cache(maxsize=4096)
def get_con_decimals(con) -> int:
    """Count decimal places. Uses math — no string formatting."""
    if not isinstance(con, (int, float)) or math.isnan(con) or math.isinf(con):
        return 0
    # Fast path: whole number
    if con == int(con):
        return 0
    # Use modulo scaling to find decimal places (max 6)
    for dp in range(1, 7):
        if abs(con * (10 ** dp) - round(con * (10 ** dp))) < 1e-9:
            return dp
    return 6


@functools.lru_cache(maxsize=8192)
def near_strict(a, b, tol=TOL) -> bool:
    """Exact match within ±TOL (float-safe)."""
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return False
    if math.isnan(a) or math.isnan(b):
        return False
    return round(abs(float(a) - float(b)), 10) <= tol


@functools.lru_cache(maxsize=8192)
def near_round(con, src) -> bool:
    """
    Bidirectional round-off match using Con's decimal precision.
    """
    if not (isinstance(con, (int, float)) and isinstance(src, (int, float))):
        return False
    if math.isnan(con) or math.isnan(src):
        return False
    # Zero should never round-match non-zero
    if con == 0 or src == 0:
        return False
    # Identical values handled by near_strict only
    if con == src:
        return False
    dp_con = get_con_decimals(con)
    dp_src = get_con_decimals(src)
    if dp_con == 0 and dp_src == 0:
        return False   # both whole → strict only
    # Whole con, decimal src: e.g. con=805, src=804.9 → round(804.9,0)=805
    if dp_con == 0 and dp_src > 0:
        return round(float(src), 0) == float(con)
    if dp_con > 0 and round(float(src), dp_con) == round(float(con), dp_con):
        return True
    if dp_src > 0 and round(float(con), dp_src) == round(float(src), dp_src):
        return True
    return False


def compute_mode(va, k10, k8n, br, tol=TOL):
    """
    Compute the consensus mode across up to 4 sources.
    Two sources agree if near_strict OR near_round.
    Returns (mode_value, count, [source_labels]).
    """
    vals, labels = [], []
    for v, lbl in [(va,"VA"),(k10,"10K"),(k8n,"8K"),(br,"Broker")]:
        if isinstance(v, (int, float)) and not math.isnan(v):
            vals.append(v); labels.append(lbl)
    if not vals:
        return None, 0, []
    best_val, best_count, best_members = vals[0], 1, [labels[0]]
    for i, v in enumerate(vals):
        matches = [(j, labels[j]) for j, w in enumerate(vals)
                   if near_strict(v, w, tol) or near_round(v, w)]
        if len(matches) > best_count:
            best_count   = len(matches)
            best_val     = v
            best_members = [m[1] for m in matches]
    return best_val, best_count, best_members


def large_diff(con, suggested, threshold=None,web_fmt: str = "N") -> bool:
    """
    Tiered gap threshold based on value magnitude AND webnumberformat:
      web_fmt="P" (percentage) → 0.5% threshold regardless of magnitude
      web_fmt="N" (number), |value| >= 100  → 1.0%
      web_fmt="N" (number), |value| <  100  → 0.5%
    Optional threshold param overrides everything.
    """
    try:
        con = float(con); suggested = float(suggested)
    except (TypeError, ValueError):
        return False
    if math.isnan(con) or math.isnan(suggested): return False
    if con == suggested: return False
    denom = max(abs(con), abs(suggested), 0.0001)
    pct   = abs(con - suggested) / denom
    if threshold is not None:
        return pct > threshold
    if str(web_fmt).strip().upper() == "P":
        thr = 0.005          # percentage values — always 0.5%
    else:
        thr = 0.005 if max(abs(con), abs(suggested)) < 100 else 0.01
    return pct > thr


# ══════════════════════════════════════════════════════════════════
#  §4  ACTION CONSTANTS & COLOUR MAPS
# ══════════════════════════════════════════════════════════════════
#
#  Four output actions only:
#    No Action  — consensus verified, nothing to do
#    Push       — system pushes a correction automatically
#    Review     — human must review before any change
#    Escalate   — serious conflict, senior human required
#
# ══════════════════════════════════════════════════════════════════

SYSTEM_ACTIONS = {"No Action", "Push", "Derived"}

ACTION_COLORS = {
    "No Action": ("10b981", "FFFFFF"),  # green
    "Push":      ("1d4ed8", "FFFFFF"),  # blue
    "Review":    ("dc2626", "FFFFFF"),  # red
    "Escalate":  ("be185d", "FFFFFF"),  # pink
    "Derived":   ("7c3aed", "FFFFFF"),  # violet
    "No Data":   ("64748b", "FFFFFF"),  # slate — B6/B7 no sources
}

STATUS_COLORS = {
    "Verified":     ("d1fae5", "065f46"),
    "Not Verified": ("fee2e2", "7f1d1d"),
    "No Data":      ("f1f5f9", "475569"),  # new status for B6/B7
}

ERROR_COLORS = {
    "High":   ("fef2f2", "991b1b"),
    "Medium": ("fefce8", "854d0e"),
    "Low":    ("f0fdf4", "166534"),
}

WHO_COLORS = {
    "System": ("dbeafe", "1e3a8a"),
    "Human":  ("fce7f3", "831843"),
}

REASON_ALIASES = ["Reason", "Mode Reason"]


def _who(action: str) -> str:
    return "System" if action in SYSTEM_ACTIONS else "Human"


# ══════════════════════════════════════════════════════════════════
#  §5  RULES CONFIGURATION
# ══════════════════════════════════════════════════════════════════

RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")

DEFAULT_RULES = {
    "matching": {
        "strict_tolerance":         0.01,
        "large_diff_threshold_large": 0.01,   # >=100 → 1.0%
        "large_diff_threshold_small": 0.005,  # <100  → 0.5%
        "broker_min_model_match":   2,
        "raw_unit_ratio":           500
    },
    "sections": {
        # Entry gates
        "calc_no_va":        {"action":"No Action", "error":"Low",    "who":"System"},
        "calc_va_mismatch":  {"action":"Review",    "error":"High",   "who":"Human"},
        # B — Push
        "B0_broker":         {"action":"Push",      "error":"Low",    "who":"System"},
        "B0_large_diff":     {"action":"Review",    "error":"Medium", "who":"Human"},
        "B0_va_broker_only": {"action":"Review",    "error":"High",   "who":"Human"},
        "B0_no_broker":      {"action":"Review",    "error":"Medium", "who":"Human"},
        "B1_broker":         {"action":"Push",      "error":"Low",    "who":"System"},
        "B1_large_diff":     {"action":"Review",    "error":"High",   "who":"Human"},
        "B1_no_broker":      {"action":"Review",    "error":"Medium", "who":"Human"},
        "B2_broker":         {"action":"Push",      "error":"Low",    "who":"System"},
        "B2_no_broker":      {"action":"Push",      "error":"Medium", "who":"System"},
        "B2_con_ne_ef":      {"action":"Review",    "error":"High",   "who":"Human"},
        "B3_ge2_match":      {"action":"Push",      "error":"Medium", "who":"System"},
        "B3_con_ne_broker":  {"action":"Review",    "error":"High",   "who":"Human"},
        "B3_mismatch":       {"action":"Review",    "error":"High",   "who":"Human"},
        "B4":                {"action":"Push",      "error":"Low",    "who":"System"},
        "B5_broker":         {"action":"Push",      "error":"Medium", "who":"System"},
        "B5_no_broker":      {"action":"Push",      "error":"High",   "who":"System"},
        # C — Review
        "C1_broker":         {"action":"Review",    "error":"Medium", "who":"Human"},
        "C1_no_broker":      {"action":"Review",    "error":"High",   "who":"Human"},
        "C2":                {"action":"Review",    "error":"High",   "who":"Human"},
        "C3":                {"action":"Review",    "error":"High",   "who":"Human"},
        "C4":                {"action":"Review",    "error":"Medium", "who":"System"},
        # D — Push (rectification)
        "D1_broker":         {"action":"Push",      "error":"Low",    "who":"System"},
        "D1_no_broker":      {"action":"Review",    "error":"Medium", "who":"Human"},
        "D2_broker":         {"action":"Push",      "error":"Low",    "who":"System"},
        "D2_no_broker":      {"action":"Review",    "error":"Medium", "who":"Human"},
        "D3_broker":         {"action":"Push",      "error":"Low",    "who":"System"},
        "D3_no_broker":      {"action":"Review",    "error":"Medium", "who":"Human"},
        "D4":                {"action":"Review",    "error":"High",   "who":"Human"},
        "D5":                {"action":"Escalate",  "error":"High",   "who":"Human"},
        # E — EF-only / Broker-only
        "E1_no_broker":      {"action":"Push",      "error":"Low",    "who":"System"},
        "E1_with_broker":    {"action":"Review",    "error":"Medium", "who":"Human"},
        "E2":                {"action":"No Action", "error":"Low",    "who":"System"},
        "E3":                {"action":"Review",    "error":"High",   "who":"Human"},
        # F — Escalation
        "F2":                {"action":"Escalate",  "error":"High",   "who":"Human"},
        "fallback_calc":     {"action":"Review",    "error":"High",   "who":"Human"},
        "fallback_other":    {"action":"Review",    "error":"Medium", "who":"System"},
    }
}


def load_rules() -> dict:
    rules = json.loads(json.dumps(DEFAULT_RULES))
    try:
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE) as f:
                saved = json.load(f)
            for k, v in saved.get("matching", {}).items():
                rules["matching"][k] = v
            for k, v in saved.get("sections", {}).items():
                if k in rules["sections"]:
                    rules["sections"][k].update(v)
    except Exception:
        pass
    return rules

# Module-level rules cache — avoids disk read on every row
_rules_cache  = None
_rules_mtime  = 0.0
_rules_checked = 0.0   # timestamp of last mtime check

def load_rules_cached() -> dict:
    """Load rules once; re-check disk at most every 5 seconds."""
    global _rules_cache, _rules_mtime, _rules_checked
    import time as _time
    now = _time.monotonic()
    if _rules_cache is not None and (now - _rules_checked) < 5.0:
        return _rules_cache          # fast path — no disk I/O
    _rules_checked = now
    try:
        mtime = os.path.getmtime(RULES_FILE) if os.path.exists(RULES_FILE) else 0.0
    except OSError:
        mtime = 0.0
    if _rules_cache is None or mtime != _rules_mtime:
        _rules_cache = load_rules()
        _rules_mtime = mtime
    return _rules_cache


def save_rules(rules: dict):
    global _rules_cache, _rules_mtime
    with open(RULES_FILE, "w") as f:
        json.dump(rules, f, indent=2)
    # Invalidate cache so next request picks up new rules
    _rules_cache = None
    _rules_mtime = 0.0


# ══════════════════════════════════════════════════════════════════
#  §6  DECISION LOGIC  — apply_logic()
#
#  Execution order:
#    Entry Gates  (Calc + no sources / Calc + Broker / Calc + VA mismatch / EF-only)
#    Section A    (Auto Verified — A0 → A4)
#    Section B    (Push — B0 → B5)
#    Section C    (Review — C1 → C5)
#    Section D    (Push Rectification — D1 → D5)
#    Section E    (EF-only / Broker-only — E1, E2, E3)
#    Section F    (Escalation — F2)
#    Late match   (con_eq_any / con_eq_mode fell through earlier sections)
#    Fallbacks
#
#  Returns 7-tuple:
#    (Action, Status, Reason, Final_Source, Suggested_Value, Error_Chance, Who)
# ══════════════════════════════════════════════════════════════════

def apply_logic(row: dict, rules: dict = None) -> tuple:
    """
    VISTA decision logic. Returns 8-tuple:
    (Action, Status, ReasonCategory, Reason, FinalSource, SuggestedValue, ErrorChance, Who)
    """
    if rules is None:
        rules = load_rules_cached()

    cfg           = rules["sections"]
    broker_min_mm = int(rules["matching"].get("broker_min_model_match", 2))
    raw_unit_ratio= rules["matching"].get("raw_unit_ratio", 500)

    def gcfg(key):
        s = cfg.get(key, DEFAULT_RULES["sections"].get(
            key, {"action": "Review", "error": "High", "who": "Human"}))
        return s["action"], s["error"], s["who"]

    # ── Read inputs ──────────────────────────────────────────────
    con          = row.get("Con_num")
    web_fmt      = str(row.get("webnumberformat", "N")).strip().upper()
    # IndStd Filling with fallback to VA Filling (case-insensitive column name)
    _is_col = next((k for k in row if str(k).strip().lower() in ("indstd filling","va filling")), None)
    va           = row.get(_is_col) if _is_col else None
    # Derived (pre-scaled) values — used for matching logic
    d_va    = row.get("d_IndStd") or row.get("d_VA")   # None if not present
    d_k10   = row.get("d_10K")    # None if not present
    d_k8    = row.get("d_8K")     # None if not present
    d_br    = row.get("d_Broker") # None if not present
    k10          = row.get("10K")
    k8           = row.get("8K")
    br           = row.get("Broker Mode")
    _br_raw      = br   # capture before scale adjustment
    _va_raw      = va
    _k10_raw     = k10
    _k8_raw      = k8
    bmc_raw      = row.get("ModelmatchCount", 0)
    revised_src  = str(row.get("Revised Source", "")).strip().lower()
    is_calc      = (revised_src == "calculated")
    is_sell_side = revised_src in ("sell-side", "sell-side calculated",
                                   "sellside", "sellside calculated")

    # ── 8K raw-unit normalisation ────────────────────────────────
    k8n = k8
    if isinstance(k8, (int, float)) and not math.isnan(k8):
        ref0 = (con if (isinstance(con, (int, float)) and not math.isnan(con) and con != 0)
                else (va if (isinstance(va, (int, float)) and not math.isnan(va) and va != 0) else None))
        if ref0 and abs(k8 / ref0) > raw_unit_ratio:
            k8n = k8 / 1000

    # ── Derived flags ────────────────────────────────────────────
    isval = _isval   # use module-level for speed (avoids closure overhead)

    has_VA     = isval(va)
    has_10K    = isval(k10)
    has_8K     = isval(k8n)
    has_EF     = has_10K or has_8K
    has_Broker = isval(br)
    con_blank  = not isval(con)
    con_zero   = isval(con) and con == 0   # zero consensus — skip scale & threshold
    bmc_int    = int(bmc_raw) if isval(bmc_raw) else 0

    def match(a, b):   return near_strict(a, b)
    def match_r(a, b): return near_strict(a, b) or near_round(a, b)

    # ── Helpers (defined before scale check — fmt_val needed early) ───
    def fmt_val(v):
        if v is None or not isval(v): return ""
        if v == int(v): return str(int(v))
        return str(round(float(v), 4))

    def gap_pct(a, b):
        if not isval(a) or not isval(b): return 0.0
        return abs(a - b) / max(abs(a), abs(b), 0.0001) * 100

    def safe_sug(con_val, sug_val):
        if not isval(con_val) or not isval(sug_val): return fmt_val(sug_val)
        if con_val == 0: return fmt_val(sug_val)
        if near_strict(con_val, sug_val) or near_round(con_val, sug_val): return ""
        ratio = abs(sug_val / con_val)
        if ratio > 50 or ratio < 0.02: return f"[SCALE: {fmt_val(sug_val)}]"
        return fmt_val(sug_val)

    def no_match_note(src_name: str, src_val) -> str:
        if not isval(src_val): return ""
        return f"[NO MATCH — {src_name}: {fmt_val(src_val)}]"

    # ── Scale cross-check ────────────────────────────────────────
    # If src × scale ≈ con (within threshold) → src is in different units.
    # Adjust the SOURCE to con's unit, keep con unchanged.
    # e.g. con=22717000, VA=22717 → VA×1000=22717000 → normalise VA to 22717000
    _SCALES = [-1, 100, -100, 1000, -1000, 10000, -10000, 100000, -100000, 1000000, -1000000]

    def _try_scale_src(con_v, src_v):
        """Scale first, then check % gap — accept if within 5% after scaling."""
        if not isval(con_v) or not isval(src_v) or src_v == 0 or con_v == 0:
            return None
        ratio = abs(con_v / src_v)
        for s in _SCALES:
            abs_s = abs(s)
            # ── Try multiplication: src × s ──
            expected_ratio_mul = abs_s if s > 0 else 1.0 / abs_s
            if abs(ratio / expected_ratio_mul - 1) <= 0.5:
                t = src_v * s
                if match_r(t, con_v) or not large_diff(con_v, t, threshold=0.05, web_fmt=web_fmt):
                    return (f"src×{s}", t)
            # ── Try division: src ÷ abs_s ──
            if abs_s > 1:
                expected_ratio_div = 1.0 / abs_s if s > 0 else abs_s
                if abs(ratio / expected_ratio_div - 1) <= 0.5:
                    try:
                        td = src_v / abs_s
                        if match_r(td, con_v) or not large_diff(con_v, td, threshold=0.05, web_fmt=web_fmt):
                            return (f"src÷{abs_s}", td)
                    except ZeroDivisionError:
                        pass
        return None

    _scale_notes  = []
    _scale_factor = ""
    if not con_blank and not con_zero:
        _scale_parts = []
        for _attr, _src_v, _src_lbl in [("va", va, "VA"), ("k10", k10, "10K"),
                                          ("k8n", k8n, "8K"), ("br", br, "Broker")]:
            if not isval(_src_v):
                continue
            _sm = _try_scale_src(con, _src_v)
            if _sm:
                _lbl = f"{_src_lbl}{_sm[0].replace('src','')}"
                _scale_parts.append(_lbl)
                _scale_notes.append(f"{_lbl}={fmt_val(_sm[1])}")
                if _attr == "va":    va  = _sm[1]
                elif _attr == "k10": k10 = _sm[1]
                elif _attr == "k8n": k8n = _sm[1]
                elif _attr == "br":  br  = _sm[1]
        if _scale_parts:
            _scale_factor = "; ".join(_scale_parts)
        # Re-derive has_ flags after all source adjustments
        has_VA     = isval(va)
        has_10K    = isval(k10)
        has_8K     = isval(k8n)
        has_EF     = has_10K or has_8K
        has_Broker = isval(br)

    # ── Round-off annotation ──────────────────────────────────────
    rn_parts = []
    if _scale_notes:
        rn_parts.append("Scale: " + "; ".join(_scale_notes) + " → normalised to Con unit")

    rn = "; ".join(rn_parts)

    broker_corr = (bmc_int >= 1) or (has_Broker and match(con, br))

    mode_val, mode_count, mode_sources = compute_mode(va, k10, k8n, br)
    mode_valid   = mode_count >= 2
    mode_src_str = ",".join(mode_sources) if mode_valid else ""

    # Match flags use derived (pre-scaled) values when available
    # Each flag fires on: exact/rounded match OR within gap threshold
    # _cmp values: prefer derived col, then scale-adjusted internal value
    _va_cmp    = d_va  if isval(d_va)  else va
    _k10_cmp   = d_k10 if isval(d_k10) else k10
    _k8_cmp    = d_k8  if isval(d_k8)  else k8n
    _br_cmp    = d_br  if isval(d_br)  else br   # br is already scale-adjusted here

    # Detect if scale was applied — either via d_ column or internal _try_scale_src
    _va_scaled  = (isval(d_va)  and isval(_va_raw)  and not near_strict(d_va,  _va_raw))  or (isval(va)  and isval(_va_raw)  and not near_strict(va,  _va_raw))
    _k10_scaled = (isval(d_k10) and isval(_k10_raw) and not near_strict(d_k10, _k10_raw)) or (isval(k10) and isval(_k10_raw) and not near_strict(k10, _k10_raw))
    _k8_scaled  = (isval(d_k8)  and isval(_k8_raw)  and not near_strict(d_k8,  _k8_raw))  or (isval(k8n) and isval(_k8_raw)  and not near_strict(k8n,  _k8_raw))
    _br_scaled  = (isval(d_br)  and isval(_br_raw)  and not near_strict(d_br,  _br_raw))  or (isval(br)  and isval(_br_raw)  and not near_strict(br,   _br_raw))

    # When a scale was applied, use 5% threshold (scaled values have inherent rounding)
    # When no scale, use the standard tiered large_diff
    def _ld_scaled(c, v, scaled): return not large_diff(c, v, threshold=0.05, web_fmt=web_fmt) if scaled else not large_diff(c, v, web_fmt=web_fmt)

    con_eq_VA  = has_VA     and not con_blank and (
        match_r(con, _va_cmp)  or _ld_scaled(con, _va_cmp,  _va_scaled))
    con_eq_10K = has_10K    and not con_blank and (
        match_r(con, _k10_cmp) or _ld_scaled(con, _k10_cmp, _k10_scaled))
    con_eq_8K  = has_8K     and not con_blank and (
        match_r(con, _k8_cmp)  or _ld_scaled(con, _k8_cmp,  _k8_scaled))
    con_eq_EF  = con_eq_10K or con_eq_8K
    con_eq_Br  = has_Broker and not con_blank and (
        match_r(con, _br_cmp)  or _ld_scaled(con, _br_cmp,  _br_scaled))
    con_eq_any = con_eq_VA or con_eq_EF or con_eq_Br
    con_eq_mode = (mode_count >= 2) and (match_r(con, mode_val) if not con_blank else False)

    VA_eq_EF  = ((has_VA and has_10K and match_r(va, k10)) or
                 (has_VA and has_8K  and match_r(va, k8n)))
    VA_eq_Br  = has_VA and has_Broker and match_r(va, br)
    EF_eq_Br  = has_Broker and ((has_10K and match_r(k10, br)) or
                                (has_8K  and match_r(k8n, br)))
    k8_eq_k10 = has_8K and has_10K and match_r(k8n, k10)

    def best_src():
        for flag, name in [(con_eq_VA,"VA Filing"),(con_eq_10K,"10K"),
                           (con_eq_8K,"8K"),(con_eq_Br,"Broker")]:
            if flag: return name
        for flag, name in [(has_VA,"VA Filing"),(has_10K,"10K"),
                           (has_8K,"8K"),(has_Broker,"Broker")]:
            if flag: return name
        return ""

    def get_best_val():
        if mode_count >= 2 and isval(mode_val): return mode_val
        for flag, val in [(con_eq_VA,va),(con_eq_10K,k10),(con_eq_8K,k8n),(con_eq_Br,br)]:
            if flag and isval(val): return val
        for flag, val in [(has_VA,va),(has_10K,k10),(has_8K,k8n),(has_Broker,br)]:
            if flag and isval(val): return val
        return con

    def split_reason(rsn: str):
        # Matches: A1.1, A2.2, B1, B3, G0a, G0b etc.
        m = _re.match(r'^([A-G]\d+(?:\.\d+)?[a-z]?)\s*[-\u2013]\s*(.*)', rsn, _re.DOTALL)
        if m: return m.group(1).strip(), m.group(2).strip()
        return "", rsn

    def add_rn(r): return f"{r}; {rn}" if rn else r

    def R(act, stat, rsn, src, sv, ec):
        cat, txt = split_reason(rsn.split(";")[0].strip())
        full_rsn = (f"{txt}; {rn}" if rn else txt) if cat else (f"{rsn}; {rn}" if rn else rsn)
        return (act, stat, cat, full_rsn, src, sv, ec, _who(act), _scale_factor)


    # ──────────────────────────────────────────────────────────────
    #  ENTRY GATES
    # ──────────────────────────────────────────────────────────────

    # Gate 0a: Revised=Calculated → Derived, System
    if is_calc:
        cat0a, txt0a = "G0a", "Calculated Data"
        rsn0a = f"{txt0a}; {rn}" if rn else txt0a
        return ("Derived", "Not Verified", cat0a, rsn0a, "", fmt_val(con), "Medium", "System", _scale_factor)

    # Gate 0b: Revised=Sell-Side → Derived, System
    if is_sell_side:
        cat0b, txt0b = "G0b", "Sell-Side Average"
        rsn0b = f"{txt0b}; {rn}" if rn else txt0b
        return ("Derived", "Not Verified", cat0b, rsn0b, "", fmt_val(con), "Medium", "System", _scale_factor)

    # Gate 1: Con=10K only, no other sources → A3.3
    if not con_blank and con_eq_10K and not has_VA and not has_8K and not has_Broker:
        return R("No Action", "Verified",
                 add_rn("A3.3 - Consensus = 10K"),
                 "10K", fmt_val(_k10_cmp), "Low")

    # ──────────────────────────────────────────────────────────────
    #  SECTION A — Auto Verified
    # ──────────────────────────────────────────────────────────────

    if not con_blank:
        # A1.1: Con = Mode (4x: VA, 10K, 8K, Broker)
        if con_eq_mode and mode_count >= 4:
            lbl = f"A1.1 - Consensus=Mode [4x: {mode_src_str}]"
            return R("No Action", "Verified", add_rn(lbl), best_src(), fmt_val(con), "Low")

        # A1.2: Con = Mode (3x sources)
        if con_eq_mode and mode_count == 3:
            lbl = f"A1.2 - Consensus=Mode [3x: {mode_src_str}]"
            return R("No Action", "Verified", add_rn(lbl), best_src(), fmt_val(con), "Low")

        # A1.3: Con = Mode (2x sources)
        if con_eq_mode and mode_count == 2:
            lbl = f"A1.3 - Consensus=Mode [2x: {mode_src_str}]"
            return R("No Action", "Verified", add_rn(lbl), best_src(), fmt_val(con), "Low")

        # A2.1: Con = VA, sole source (no EF/Broker)
        if con_eq_VA and not has_EF and not has_Broker:
            return R("No Action", "Verified",
                     add_rn("A2.1 - Consensus = VA"),
                     "VA Filing", fmt_val(con), "Low")

        # A2.2: Con = VA (rounded) — push the rounded value
        if con_eq_VA:
            return R("Push", "Verified",
                     add_rn("A2.2 - Consensus = VA (Rounded)"),
                     "VA Filing", fmt_val(con), "Low")

        # A3.1: Con = EF (8K exact)
        if con_eq_8K and not has_VA:
            sv_a31 = fmt_val(_k8_cmp)
            if not near_round(con, k8n) or near_strict(con, k8n):
                return R("No Action", "Verified",
                         add_rn("A3.1 - Consensus = 8K"),
                         "8K", sv_a31, "Low")
            # A3.2: Con = EF (8K rounded)
            return R("No Action", "Verified",
                     add_rn("A3.2 - Consensus = 8K (Rounded)"),
                     "8K", sv_a31, "Low")

        # A3.3: Con = 10K sole source (handled in Gate 1 above)
        # A3.4: Con = 10K rounded
        if con_eq_10K and not has_VA:
            return R("No Action", "Verified",
                     add_rn("A3.4 - Consensus = 10K (Rounded)"),
                     "10K", fmt_val(_k10_cmp), "Low")

        # A4.1: Con = Broker, no VA or EF
        if con_eq_Br and not has_VA and not has_EF:
            if near_strict(con, br):
                return R("No Action", "Verified",
                         add_rn("A4.1 - Consensus = Broker Mode"),
                         "Broker", fmt_val(_br_cmp), "Low")
            # A4.2: Con = Broker (rounded) — push
            return R("Push", "Verified",
                     add_rn("A4.2 - Consensus = Broker Mode (Rounded)"),
                     "Broker", fmt_val(_br_cmp), "Low")

    # ──────────────────────────────────────────────────────────────
    #  SECTION B — Conditional Push
    # ──────────────────────────────────────────────────────────────

    # A5: Mode valid, Con ≠ Mode, diff ≤ threshold (rounded), ≥1 broker match
    if not con_blank and not con_zero and not con_eq_any and not con_eq_mode and mode_valid:
        dp_con = get_con_decimals(con)
        dp_str = (f"{mode_val:.{dp_con}f}" if dp_con > 0
                  else str(int(round(float(mode_val)))))
        gp     = gap_pct(con, mode_val)
        sv     = safe_sug(con, mode_val)
        src    = best_src()
        if broker_corr and not large_diff(con, mode_val, web_fmt=web_fmt):
            mode_has_ef = any(s in mode_sources for s in ("10K","8K"))
            if not ("VA" in mode_sources and "Broker" in mode_sources and not mode_has_ef):
                return R("Push", "Verified",
                         add_rn(f"A5 - Consensus = System Value (Rounded) [{mode_src_str}]"),
                         src, sv, "Low")
        dp_con = get_con_decimals(con)
        dp_str = (f"{mode_val:.{dp_con}f}" if dp_con > 0
                  else str(int(round(float(mode_val)))))
        gp     = gap_pct(con, mode_val)
        reason = f"B4 - Consensus ≠ Mode Available – Check & Deploy [{mode_src_str}]"
        sv     = safe_sug(con, mode_val)
        src    = best_src()
        if broker_corr:
            if large_diff(con, mode_val, web_fmt=web_fmt):
                return R("Review", "Not Verified", add_rn(reason + ""), src, sv, "High")
            mode_has_ef = any(s in mode_sources for s in ("10K","8K"))
            if "VA" in mode_sources and "Broker" in mode_sources and not mode_has_ef:
                return R("Review", "Not Verified", add_rn(reason + ", Mode=[VA,Broker] only"), src, sv, "High")
            return R("Review", "Not Verified", add_rn(reason + ", ≥1 broker match"), src, sv, "High")
        else:
            return R("Review", "Not Verified", add_rn(reason + ", 0 broker match"), src, sv, "High")

    if not con_blank and not con_zero and not con_eq_any:
        # B1: VA missing, EF only → No Mode Available
        if not has_VA and has_EF and not has_Broker:
            src    = "10K" if has_10K else "8K"
            ef_val = _k10_cmp if has_10K else _k8_cmp
            gp     = gap_pct(con, ef_val)
            sv     = safe_sug(con, ef_val)
            return R("Review", "Not Verified",
                     add_rn(f"B1 - No Mode Available, VA missing, EF only"),
                     src, sv, "High")

        # B2: Broker sole, ≥2 model match, Con≠Broker
        if not has_VA and not has_EF and has_Broker:
            gp = gap_pct(con, _br_cmp)
            sv = safe_sug(con, _br_cmp)
            if bmc_int >= broker_min_mm and not con_eq_Br:
                return R("Review", "Not Verified",
                         add_rn(f"B2 - Broker sole, ≥{broker_min_mm} model match, Con≠Broker (MMC={bmc_int})"),
                         "Broker", sv, "High")
            return R("Review", "Not Verified",
                     add_rn(f"B2 - Broker sole, Con≠Broker (MMC={bmc_int})"),
                     "Broker", sv, "High")

        # (EF+Broker agree handled via mode path above)

    # B3: Blank consensus, unconfirmed
    if con_blank and (has_VA or has_EF or has_Broker):
        src = ("VA Filing" if has_VA else
               ("10K" if has_10K else ("8K" if has_8K else "Broker")))
        # Suggested value blank if < 2 parameters agree (per spec)
        best_v = get_best_val()
        sv = fmt_val(best_v) if mode_valid else ""
        return R("Review", "Not Verified",
                 add_rn(f"B3 - Blank Consensus, unconfirmed (MMC={bmc_int}, src={src})"),
                 src, sv, "High")

    # ──────────────────────────────────────────────────────────────
    #  SECTION C — Human Review
    # ──────────────────────────────────────────────────────────────

    if not con_blank and not con_zero and not con_eq_any and not con_eq_mode:
        # B4: Mode conflict, gap > threshold → Check & Deploy
        if has_VA and not VA_eq_EF and not VA_eq_Br:
            gp    = gap_pct(con, _va_cmp)
            is_lg = large_diff(con, va, web_fmt=web_fmt)
            ec    = "High" if is_lg else "Medium"
            return R("Review", "Not Verified",
                     add_rn(f"B4 - Consensus ≠ Mode Available – Check & Deploy, VA isolated"),
                     "", fmt_val(con), ec)

        # B5: 3-way mismatch: VA ≠ EF ≠ Broker
        if has_VA and has_EF and has_Broker:
            ef_c2 = k10 if has_10K else k8n
            ef_src_c2 = "10K" if has_10K else "8K"
            if (not match_r(va, ef_c2) and not match_r(va, br)
                    and not match_r(ef_c2, br)):
                gp_va_ef = gap_pct(va, ef_c2)
                gp_va_br = gap_pct(va, br)
                _a,_e,_w = gcfg("C2")
                return R(_a, "Not Verified",
                         add_rn(f"B5 - VA ≠ EF ≠ Broker, 3-way mismatch: VA≠{ef_src_c2}, VA≠Broker"),
                         "", fmt_val(con), _e)

        # C3: EF intra-conflict (8K ≠ 10K) — report gap
        if has_8K and has_10K and not k8_eq_k10:
            gp_ef = gap_pct(k8n, k10)
            _a,_e,_w = gcfg("C3")
            return R(_a, "Not Verified",
                     add_rn(f"B5 - EF intra-conflict: 8K≠10K"),
                     "", fmt_val(con), _e)

        # B6: Con unverifiable — no sources but con has value
        # B7: All data blank
        if not has_VA and not has_EF and not has_Broker:
            if not con_blank:
                return ("No Data", "Not Verified", "B6",
                        add_rn(f"B6 - Consensus Unverifiable: no sources (MMC={bmc_int})"),
                        "", fmt_val(con), "Medium", "Human", _scale_factor)
            else:
                return ("No Data", "Not Verified", "B7",
                        add_rn("B7 - All data blank"),
                        "", "", "Medium", "Human", _scale_factor)

        # C5: Calculated fallback
        if is_calc:
            return R("Review", "Not Verified",
                     add_rn("G0a - Calculated Data, no corroborating source"),
                     "", fmt_val(con), "High")

        # ──────────────────────────────────────────────────────────
        #  SECTION D — Rectification Push
        # ──────────────────────────────────────────────────────────

        # D1: Con≠VA, VA+EF agree — report gap
        if has_VA and VA_eq_EF and not con_eq_VA:
            gp_d1  = gap_pct(con, _va_cmp)
            is_lg  = large_diff(con, va, web_fmt=web_fmt)
            _a_b,_e_b,_w_b = gcfg("D1_broker")
            _a_n,_e_n,_w_n = gcfg("D1_no_broker")
            sv_push   = safe_sug(con, _va_cmp)
            sv_review = no_match_note("VA", va)
            ec_adj_b  = "High" if is_lg else _e_b
            ec_adj_n  = "High" if is_lg else _e_n
            if broker_corr:
                sv = sv_push if _a_b == "Push" else sv_review
                return R(_a_b, "Not Verified",
                         add_rn(f"D1 - Con≠VA, VA+EF agree, ≥1 broker match"),
                         "VA Filing", sv, ec_adj_b)
            else:
                sv = sv_push if _a_n == "Push" else sv_review
                return R(_a_n, "Not Verified",
                         add_rn(f"D1 - Con≠VA, VA+EF agree, 0 broker match"),
                         "VA Filing", sv, ec_adj_n)

        # D2: Con≠EF, VA missing, EF+Broker agree — report gap
        if not has_VA and has_EF and EF_eq_Br and not con_eq_EF:
            src      = "10K" if has_10K else "8K"
            ef_val_d = k10 if has_10K else k8n
            gp_d2    = gap_pct(con, ef_val_d)
            is_lg    = large_diff(con, ef_val_d, web_fmt=web_fmt)
            _a_b,_e_b,_w_b = gcfg("D2_broker")
            _a_n,_e_n,_w_n = gcfg("D2_no_broker")
            sv_push   = safe_sug(con, ef_val_d)
            sv_review = no_match_note(src, ef_val_d)
            ec_adj_b  = "High" if is_lg else _e_b
            ec_adj_n  = "High" if is_lg else _e_n
            if broker_corr:
                sv = sv_push if _a_b == "Push" else sv_review
                return R(_a_b, "Not Verified",
                         add_rn(f"D2 - Con≠EF, VA missing, EF+Broker agree, ≥1 match"),
                         src, sv, ec_adj_b)
            else:
                sv = sv_push if _a_n == "Push" else sv_review
                return R(_a_n, "Not Verified",
                         add_rn(f"D2 - Con≠EF, VA missing, EF+Broker agree, 0 match"),
                         src, sv, ec_adj_n)

        # D3: Con≠VA, VA+Broker agree, no EF — report gap
        if has_VA and VA_eq_Br and not has_EF and not con_eq_VA:
            gp_d3  = gap_pct(con, _va_cmp)
            is_lg  = large_diff(con, va, web_fmt=web_fmt)
            _a_b,_e_b,_w_b = gcfg("D3_broker")
            _a_n,_e_n,_w_n = gcfg("D3_no_broker")
            sv_push   = safe_sug(con, _va_cmp)
            sv_review = no_match_note("VA", va)
            ec_adj_b  = "High" if is_lg else _e_b
            ec_adj_n  = "High" if is_lg else _e_n
            if broker_corr:
                sv = sv_push if _a_b == "Push" else sv_review
                return R(_a_b, "Not Verified",
                         add_rn(f"D3 - Con≠VA, VA+Broker agree, EF missing, ≥1 match"),
                         "VA Filing", sv, ec_adj_b)
            else:
                sv = sv_push if _a_n == "Push" else sv_review
                return R(_a_n, "Not Verified",
                         add_rn(f"D3 - Con≠VA, VA+Broker agree, EF missing, 0 match"),
                         "VA Filing", sv, ec_adj_n)

        # D4: Broker only, Con suspect — check gap
        if not has_VA and not has_EF and has_Broker:
            gp_d4 = gap_pct(con, _br_cmp)
            is_lg  = large_diff(con, br, web_fmt=web_fmt)
            _a,_e,_w = gcfg("D4")
            ec = "High" if is_lg else _e
            return R(_a, "Not Verified",
                     add_rn("D4 - Broker only, Con suspect"),
                     "", fmt_val(con), ec)

        # D5: No structured source
        if not has_VA and not has_EF and not has_Broker:
            _a,_e,_w = gcfg("D5")
            return R(_a, "Not Verified",
                     add_rn("D5 - No structured source"), "", fmt_val(con), _e)

    # ──────────────────────────────────────────────────────────────
    #  SECTION E — EF-only / Broker-only
    # ──────────────────────────────────────────────────────────────

    if not con_blank:
        # E1: Con=EF, no VA
        if con_eq_EF and not has_VA:
            src   = "10K" if has_10K else "8K"
            ef_e1 = k10 if has_10K else k8n
            sv    = fmt_val(ef_e1)
            if not has_Broker:
                _a,_e,_w = gcfg("E1_no_broker")
                return R(_a, "Verified",
                         add_rn(f"A3.1 - Consensus = 8K/10K"), src, sv, _e)
            else:
                gp_e1 = gap_pct(con, _br_cmp)
                is_lg = large_diff(con, br, web_fmt=web_fmt)
                _a,_e,_w = gcfg("E1_with_broker")
                ec  = ("High" if is_lg else _e) if not broker_corr else _e
                lbl = ("A3.1 - Consensus = EF, VA missing, ≥1 broker match" if broker_corr
                       else f"A3.1 - Consensus = EF, VA missing, 0 broker match ({gp_e1:.2f}% vs Broker)")
                return R(_a, "Not Verified", add_rn(lbl), src, sv, ec)

        # A4.1 / A4.2: Con=Broker, no VA, no EF (handled in Section A above)
        # E2 exact — should have been caught in Section A; catch stragglers here
        if con_eq_Br and not has_VA and not has_EF:
            if near_strict(con, br):
                return R("No Action", "Verified",
                         add_rn("A4.1 - Consensus = Broker Mode"), "Broker", fmt_val(_br_cmp), "Low")
            return R("Push", "Verified",
                     add_rn("A4.2 - Consensus = Broker Mode (Rounded)"), "Broker", fmt_val(_br_cmp), "Low")

        # B2 fallback: Broker sole but Con≠Broker (not caught above)
        if not con_eq_Br and not has_VA and not has_EF and has_Broker:
            gp_e2 = gap_pct(con, _br_cmp)
            is_lg = large_diff(con, br, web_fmt=web_fmt)
            ec    = "High" if is_lg else "Medium"
            return R("Review", "Not Verified",
                     add_rn(f"B2 - Consensus≠Broker, sole source: Broker={fmt_val(_br_cmp)} (MMC={bmc_int})"),
                     "Broker", no_match_note("Broker", br), ec)

        # B8: Con=Broker but EF present and EF≠Con
        if con_eq_Br and not has_VA and has_EF and not con_eq_EF:
            ef_e3  = k10 if has_10K else k8n
            ef_src = "10K" if has_10K else "8K"
            gp_e3  = gap_pct(con, ef_e3)
            is_lg  = large_diff(con, ef_e3, web_fmt=web_fmt)
            suffix = "; broker match confirmed" if broker_corr else "; 0 broker match"
            ec     = "High" if is_lg else "Medium"
            return R("Review", "Not Verified",
                     add_rn(f"B8 - Consensus=Broker≠EF, {ef_src}≠Con, VA missing{suffix}"),
                     "Broker", no_match_note(ef_src, ef_e3), ec)

    # ──────────────────────────────────────────────────────────────
    #  SECTION F — Escalation
    # ──────────────────────────────────────────────────────────────

    if not con_blank and has_VA and not con_eq_VA and con_eq_Br and is_calc:
        gp_f2 = gap_pct(con, _va_cmp)
        _a,_e,_w = gcfg("F2")
        return R(_a, "Not Verified",
                 add_rn("F2 - VA≠Con, Con=Broker, Revised=Calculated"),
                 "", fmt_val(con), _e)

    # ──────────────────────────────────────────────────────────────
    #  LATE MATCH BLOCK
    # ──────────────────────────────────────────────────────────────

    if not con_blank and (con_eq_any or con_eq_mode):
        if   con_eq_VA:  src = "VA Filing"
        elif con_eq_10K: src = "10K"
        elif con_eq_8K:  src = "8K"
        elif con_eq_Br:  src = "Broker"
        else:            src = ""
        active_v = con

        # Sign conflict: VA = −Con → B4
        if has_VA and not con_eq_VA and isval(va):
            if abs(con + va) < 0.01 * max(abs(con), 0.0001):
                return R("Review", "Not Verified",
                         add_rn(f"B4 - Sign conflict: VA={fmt_val(va)} vs Con={fmt_val(con)} (opposite sign)"),
                         "", fmt_val(con), "High")

        # Sign conflict: EF = −Con
        for ef_val, ef_name in [(k10,"10K"),(k8n,"8K")]:
            if isval(ef_val) and not near_strict(con, ef_val) and not near_round(con, ef_val):
                if abs(con + ef_val) < 0.01 * max(abs(con), 0.0001):
                    return R("Review", "Not Verified",
                             add_rn(f"B5 - Sign conflict: {ef_name}={fmt_val(ef_val)} vs Con={fmt_val(con)} (opposite sign)"),
                             "", fmt_val(con), "High")

        # VA material conflict — use gap threshold
        if has_VA and not con_eq_VA:
            gp_late = gap_pct(con, _va_cmp)
            if large_diff(con, va, web_fmt=web_fmt):
                return R("Review", "Not Verified",
                         add_rn(f"B4 - VA conflicts"),
                         "", fmt_val(con), "High")
            else:
                return R("No Action", "Verified",
                         add_rn(f"A2.2 - Consensus = VA (Rounded)"),
                         src, fmt_val(active_v), "Medium")

        # Clean match labels
        if src == "Broker" and not has_VA and not has_EF:
            return R("No Action", "Verified", add_rn("A4.1 - Consensus = Broker Mode"), src, fmt_val(active_v), "Low")
        elif src == "VA Filing" and (con_eq_Br or con_eq_EF):
            return R("No Action", "Verified", add_rn("A1.3 - Consensus=Mode [VA cross-validated]"), src, fmt_val(active_v), "Low")
        elif src == "VA Filing":
            return R("No Action", "Verified", add_rn("A2.1 - Consensus = VA"), src, fmt_val(active_v), "Low")
        elif src in ("10K","8K") and con_eq_VA:
            return R("No Action", "Verified", add_rn("A1.2 - Consensus=Mode [VA+EF dual confirmation]"), src, fmt_val(active_v), "Low")
        else:
            return R("No Action", "Verified", add_rn(f"A0 - Con=Mode [{src}]"), src, fmt_val(active_v), "Low")

    # ── FALLBACKS ─────────────────────────────────────────────────
    if is_calc:
        _a,_e,_w = gcfg("fallback_calc")
        return R(_a, "Not Verified", add_rn("G0a - Calculated Data, no data match"), "", fmt_val(con), _e)
    _a,_e,_w = gcfg("fallback_other")
    return ("Review", "Not Verified", "C4",
            add_rn("B7 - All data blank or unresolvable"),
            "", fmt_val(con), "Medium", "System", _scale_factor)


# ══════════════════════════════════════════════════════════════════
#  §7  EXCEL & API PROCESSING
# ══════════════════════════════════════════════════════════════════

def process_dataframe(df: pd.DataFrame, col_map: dict,
                      source_bytes: bytes = None) -> tuple:
    """
    Apply decision logic and write output in fixed column order.
    Returns (out_bytes, summary_dict, row_count, summary_flat).
    """
    import openpyxl as _opx

    # ── Column renames ────────────────────────────────────────────
    rename = {custom: std for std, custom in col_map.items()
              if custom and custom != std and custom in df.columns}
    if rename:
        df = df.rename(columns=rename)

    reason_col = next((c for c in REASON_ALIASES if c in df.columns), "Reason")

    # Reset index — prevents alignment errors after period/row filtering
    df = df.reset_index(drop=True)

    # Drop any existing VISTA output columns from df to prevent duplicate columns
    # after pd.concat — this happens when user uploads a previously processed file
    _OUTPUT_COLS = {"Action", "Status", "Reason Category", "Final Source",
                    "Suggested Value", "Scale Factor", "% Diff", "Num Diff",
                    "d_8K", "d_10K", "d_IndStd", "d_Broker",
                    "Error Chance", "Who", reason_col}
    df = df.drop(columns=[c for c in _OUTPUT_COLS if c in df.columns], errors="ignore")

    # ── Apply logic ───────────────────────────────────────────────
    _rules   = load_rules_cached()
    _cols    = ["Action", "Status", "Reason Category", reason_col,
                "Final Source", "Suggested Value", "Error Chance", "Who", "Scale Factor"]
    _records = df.to_dict("records")
    results  = pd.DataFrame(
        [apply_logic(r, _rules) for r in _records],
        columns=_cols, index=df.index,
    )

    # ── Merge input + output into one flat DataFrame ──────────────
    # MUST happen before % Diff / Num Diff which need merged["Con_num"]
    # ── Derived scaled columns ───────────────────────────────────────
    _D_SCALES = [1, -1, 100, -100, 1000, -1000, 10000, -10000, 100000, -100000]

    def _best_scale(con_v, src_v):
        """Return src scaled to best match con, or src as-is if no scale improves."""
        if not (isinstance(con_v, (int,float)) and isinstance(src_v, (int,float))):
            return None
        if math.isnan(con_v) or math.isnan(src_v) or src_v == 0 or con_v == 0:
            return src_v if (isinstance(src_v,(int,float)) and not math.isnan(src_v)) else None
        best_val, best_diff = src_v, abs(con_v - src_v)
        for s in _D_SCALES:
            try:
                t_mul = src_v * s
                d_mul = abs(con_v - t_mul)
                if d_mul < best_diff:
                    best_diff, best_val = d_mul, t_mul
                if abs(s) > 1:
                    t_div = src_v / abs(s)
                    d_div = abs(con_v - t_div)
                    if d_div < best_diff:
                        best_diff, best_val = d_div, t_div
            except Exception:
                continue
        return round(best_val, 6)

    _con_arr = pd.to_numeric(df.get("Con_num", pd.Series(dtype=float)), errors="coerce")
    for _dcol, _srcol in [("d_8K","8K"), ("d_10K","10K"),
                           ("d_IndStd","IndStd Filling"), ("d_Broker","Broker Mode")]:
        _src_arr = pd.to_numeric(df.get(_srcol, pd.Series(dtype=float, index=df.index)), errors="coerce")                    if _srcol in df.columns else pd.Series(dtype=float, index=df.index)
        df[_dcol] = [_best_scale(c, s) for c, s in zip(_con_arr, _src_arr)]

    merged = pd.concat([df, results], axis=1)

    # ── Compute % Diff and Num Diff (fully vectorised, no apply) ──
    if "Con_num" in merged.columns:
        con_series = pd.to_numeric(merged["Con_num"], errors="coerce")
    else:
        con_series = pd.Series(0.0, index=merged.index)
    sv_series = pd.to_numeric(merged["Suggested Value"], errors="coerce")

    both_valid = con_series.notna() & sv_series.notna() & (con_series != 0)
    abs_con = con_series.abs().fillna(0).values
    abs_sv  = sv_series.abs().fillna(0).values
    denom   = np.where(np.maximum(abs_con, abs_sv) < 0.0001, 0.0001,
                       np.maximum(abs_con, abs_sv))
    pct_vals = np.where(both_valid.values,
                        np.round(np.abs(con_series.values - sv_series.values) / denom * 100, 2),
                        np.nan)
    num_vals = np.where(both_valid.values,
                        np.round(sv_series.values - con_series.values, 4),
                        np.nan)

    # Convert to string/numeric without apply()
    pct_list = [f"{v}%" if not (isinstance(v, float) and np.isnan(v)) else "" for v in pct_vals]
    num_list = [v if not (isinstance(v, float) and np.isnan(v)) else "" for v in num_vals]
    merged["% Diff"]   = pct_list
    merged["Num Diff"] = num_list

    # ── Fixed output column order ─────────────────────────────────
    DESIRED = [
        "Ukey", "Ticker", "LineItem", "Source Derived", "Revised Source",
        "UIC", "Fiscalperiod", "Restated", "webnumberformat",
        "Prebuilt_num", "Con_num", "8K", "10K", "IndStd Filling", "Broker Mode",
        "d_8K", "d_10K", "d_IndStd", "d_Broker",
        "Final Source", "Suggested Value", "Scale Factor", "% Diff", "Num Diff",
        "Action", "Status",
        "Reason Category", reason_col,
        "Error Chance", "Who",
        "IndStd Actuals", "Broker Avg", "Total BrokerCount", "Mode BrokerCount",
        "ModelmatchCount", "ModelName",
        "Source8K", "Source10K", "Source Broker",
    ]
    final_cols = [c for c in DESIRED if c in merged.columns]
    extras     = [c for c in merged.columns if c not in final_cols]
    merged     = merged[final_cols + extras]

    # ── Column widths ─────────────────────────────────────────────
    COL_WIDTHS = {
        "Ukey":14, "Ticker":10, "LineItem":22, "Source Derived":16,
        "Revised Source":16, "UIC":10, "Fiscalperiod":12, "Restated":9,
        "webnumberformat":14, "Con_num":13, "8K":12, "10K":12,
        "IndStd Filling":12, "Broker Mode":12,
        "d_8K":12, "d_10K":12, "d_IndStd":12, "d_Broker":12,
        "Suggested Value":16, "Scale Factor":12, "% Diff":10, "Num Diff":14,
        "Error Chance":12, "Who":10,
        "Action":14, "Status":14,
        reason_col:62, "Reason":62,
        "Final Source":14,
        "IndStd Actuals":12, "Broker Avg":12,
        "Total BrokerCount":16, "Mode BrokerCount":16,
        "ModelmatchCount":16, "ModelName":18,
        "Prebuilt_num":13, "Source8K":14, "Source10K":14, "Source Broker":14,
        "Reason Category":14,
    }

    # ── Header colour bands ───────────────────────────────────────
    VERIDEX_OUT = {"Action", "Status", "Reason Category", reason_col,
                   "Final Source", "Suggested Value", "Scale Factor",
                   "% Diff", "Num Diff", "Error Chance", "Who"}
    HDR_INPUT  = "1e3a5f"
    HDR_OUTPUT = "1e4d2b"
    HDR_CAT    = "312e81"
    HDR_DERIVED= "0e4f4f"   # teal — derived/scaled source columns

    ctr = Alignment(horizontal="center", vertical="center", wrap_text=False)
    lft = Alignment(horizontal="left",   vertical="center", wrap_text=False)

    # ── Build workbook ────────────────────────────────────────────
    wb = _opx.Workbook()
    ws = wb.active
    ws.title = "VISTA Output"

    # Header row
    for ci, col in enumerate(merged.columns, 1):
        hc           = ws.cell(1, ci, value=col)
        hc.alignment = ctr
        hc.font      = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
        if col == "Reason Category":
            hc.fill = PatternFill("solid", fgColor=HDR_CAT)
        elif col in {"d_8K", "d_10K", "d_IndStd", "d_Broker"}:
            hc.fill = PatternFill("solid", fgColor=HDR_DERIVED)
            hc.font = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
        elif col in VERIDEX_OUT:
            hc.fill = PatternFill("solid", fgColor=HDR_OUTPUT)
        else:
            hc.fill = PatternFill("solid", fgColor=HDR_INPUT)
        ws.column_dimensions[get_column_letter(ci)].width = COL_WIDTHS.get(col, 14)

    # Data rows — write values in bulk first, then apply formatting by column
    # Step 1: write all values at once via ws.append (much faster than cell-by-cell)
    col_list    = list(merged.columns)
    action_idx  = col_list.index("Action")  if "Action"  in col_list else -1
    status_idx  = col_list.index("Status")  if "Status"  in col_list else -1
    reason_idx  = col_list.index(reason_col) if reason_col in col_list else -1
    ec_idx      = col_list.index("Error Chance") if "Error Chance" in col_list else -1
    who_idx     = col_list.index("Who")     if "Who"     in col_list else -1
    sv_idx      = col_list.index("Suggested Value") if "Suggested Value" in col_list else -1
    sf_idx      = col_list.index("Scale Factor")    if "Scale Factor"    in col_list else -1
    pd_idx      = col_list.index("% Diff")  if "% Diff"  in col_list else -1
    nd_idx      = col_list.index("Num Diff") if "Num Diff" in col_list else -1
    rc_idx      = col_list.index("Reason Category") if "Reason Category" in col_list else -1

    # Pre-convert merged to list of lists for fast iteration
    data_rows = merged.values.tolist()
    n_cols    = len(col_list)

    for ri, data_row in enumerate(data_rows, 2):
        # Clean values
        clean = []
        for v in data_row:
            try:
                clean.append("" if (not isinstance(v, str) and pd.isna(v)) or str(v) == "nan" else v)
            except (TypeError, ValueError):
                clean.append(v)

        # Bulk write the row
        for ci, val in enumerate(clean, 1):
            cell = ws.cell(ri, ci, value=val)
            cell.font      = Font(name="Calibri", size=9)
            cell.alignment = ctr

        # Targeted formatting — only touch columns that need special treatment
        status_val = str(clean[status_idx]) if status_idx >= 0 else ""

        if action_idx >= 0:
            val = str(clean[action_idx])
            bg, fg = ACTION_COLORS.get(val, ("94a3b8","FFFFFF"))
            c = ws.cell(ri, action_idx+1)
            c.font = Font(name="Calibri", bold=True, size=9, color=fg)
            c.fill = PatternFill("solid", fgColor=bg)

        if status_idx >= 0:
            val = str(clean[status_idx])
            bg, fg = STATUS_COLORS.get(val, ("f1f5f9","374151"))
            c = ws.cell(ri, status_idx+1)
            c.font = Font(name="Calibri", bold=True, size=9, color=fg)
            c.fill = PatternFill("solid", fgColor=bg)

        if rc_idx >= 0:
            c = ws.cell(ri, rc_idx+1)
            c.font = Font(name="Calibri", bold=True, size=9, color="1e3a5f")
            c.fill = PatternFill("solid", fgColor="e0e7ff")

        if reason_idx >= 0:
            c = ws.cell(ri, reason_idx+1)
            c.alignment = lft
            c.font = Font(name="Calibri", size=9)

        if ec_idx >= 0:
            ec_clean = str(clean[ec_idx]) if str(clean[ec_idx]) in ("Low","Medium","High") else ""
            c = ws.cell(ri, ec_idx+1)
            bg, fg = ERROR_COLORS.get(ec_clean, ("ffffff","374151"))
            c.font  = Font(name="Calibri", bold=True, size=9, color=fg)
            if ec_clean:
                c.fill = PatternFill("solid", fgColor=bg)
            c.value = ec_clean

        if who_idx >= 0:
            who_clean = str(clean[who_idx]) if str(clean[who_idx]) in ("System","Human") else ""
            c = ws.cell(ri, who_idx+1)
            bg, fg = WHO_COLORS.get(who_clean, ("f8fafc","374151"))
            c.font  = Font(name="Calibri", bold=True, size=9, color=fg)
            if who_clean:
                c.fill = PatternFill("solid", fgColor=bg)
            c.value = who_clean

        if sv_idx >= 0:
            val = clean[sv_idx]
            c = ws.cell(ri, sv_idx+1)
            c.font = Font(name="Calibri", bold=True, size=9)
            if status_val == "Verified":
                c.fill = PatternFill("solid", fgColor="f0fdf4")
            elif val:
                c.fill = PatternFill("solid", fgColor="eff6ff")

        if sf_idx >= 0:
            val = clean[sf_idx]
            c = ws.cell(ri, sf_idx+1)
            if val and str(val).strip():
                c.font = Font(name="Calibri", bold=True, size=9, color="92400e")
                c.fill = PatternFill("solid", fgColor="fef3c7")
            else:
                c.font = Font(name="Calibri", size=9, color="94a3b8")

        if pd_idx >= 0:
            val = clean[pd_idx]
            c = ws.cell(ri, pd_idx+1)
            c.font = Font(name="Calibri", bold=True, size=9)
            if val and str(val).strip():
                try:
                    pct_v = float(str(val).replace("%",""))
                    if pct_v > 10:
                        c.fill = PatternFill("solid", fgColor="fee2e2")
                        c.font = Font(name="Calibri", bold=True, size=9, color="991b1b")
                    elif pct_v > 1:
                        c.fill = PatternFill("solid", fgColor="fef3c7")
                        c.font = Font(name="Calibri", bold=True, size=9, color="92400e")
                    else:
                        c.fill = PatternFill("solid", fgColor="f0fdf4")
                        c.font = Font(name="Calibri", bold=True, size=9, color="166534")
                except (ValueError, TypeError):
                    pass

        if nd_idx >= 0:
            val = clean[nd_idx]
            c = ws.cell(ri, nd_idx+1)
            c.font = Font(name="Calibri", size=9)
            if val and str(val).strip():
                try:
                    num_v = float(val)
                    if num_v < 0:
                        c.fill = PatternFill("solid", fgColor="fff1f2")
                        c.font = Font(name="Calibri", size=9, color="be123c")
                    elif num_v > 0:
                        c.fill = PatternFill("solid", fgColor="eff6ff")
                        c.font = Font(name="Calibri", size=9, color="1e40af")
                except (ValueError, TypeError):
                    pass

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(merged.columns))}1"
    ws.row_dimensions[1].height = 20
    for _ri in range(2, len(merged) + 2):
        ws.row_dimensions[_ri].height = 15

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)

    summary = {
        "actions": results["Action"].value_counts().to_dict(),
        "status":  results["Status"].value_counts().to_dict(),
        "who":     results["Who"].value_counts().to_dict(),
    }
    summary_flat = results["Action"].value_counts().to_dict()
    return out.read(), summary, len(results), summary_flat


    # ── Fixed output column order ─────────────────────────────────
    DESIRED = [
        "Ukey", "Ticker", "LineItem", "Source Derived", "Revised Source",
        "UIC", "Fiscalperiod", "Restated", "webnumberformat",
        "Prebuilt_num", "Con_num", "8K", "10K", "IndStd Filling", "Broker Mode",
        "d_8K", "d_10K", "d_IndStd", "d_Broker",
        "Final Source", "Suggested Value", "Scale Factor", "% Diff", "Num Diff",
        "Action", "Status",
        "Reason Category", reason_col,
        "Error Chance", "Who",
        "IndStd Actuals", "Broker Avg", "Total BrokerCount", "Mode BrokerCount",
        "ModelmatchCount", "ModelName",
        "Source8K", "Source10K", "Source Broker",
    ]
    final_cols = [c for c in DESIRED if c in merged.columns]
    extras     = [c for c in merged.columns if c not in final_cols]
    merged     = merged[final_cols + extras]

    # ── Column widths ─────────────────────────────────────────────
    COL_WIDTHS = {
        "Ukey":14, "Ticker":10, "LineItem":22, "Source Derived":16,
        "Revised Source":16, "UIC":10, "Fiscalperiod":12, "Restated":9,
        "webnumberformat":14, "Con_num":13, "8K":12, "10K":12,
        "IndStd Filling":12, "Broker Mode":12,
        "d_8K":12, "d_10K":12, "d_IndStd":12, "d_Broker":12,
        "Suggested Value":16, "Scale Factor":12, "% Diff":10, "Num Diff":14,
        "Error Chance":12, "Who":10,
        "Action":14, "Status":14,
        reason_col:62, "Reason":62,
        "Final Source":14,
        "IndStd Actuals":12, "Broker Avg":12,
        "Total BrokerCount":16, "Mode BrokerCount":16,
        "ModelmatchCount":16, "ModelName":18,
        "Prebuilt_num":13, "Source8K":14, "Source10K":14, "Source Broker":14,
        "Reason Category":14,
    }

    # ── Header colour bands ───────────────────────────────────────
    VERIDEX_OUT = {"Action", "Status", "Reason Category", reason_col,
                   "Final Source", "Suggested Value", "Scale Factor",
                   "% Diff", "Num Diff", "Error Chance", "Who"}
    HDR_INPUT  = "1e3a5f"   # dark blue  — input columns
    HDR_OUTPUT = "1e4d2b"   # dark green — VISTA output columns
    HDR_CAT    = "312e81"   # indigo     — Reason Category

    ctr = Alignment(horizontal="center", vertical="center", wrap_text=False)
    lft = Alignment(horizontal="left",   vertical="center", wrap_text=False)

    # ── Build workbook ────────────────────────────────────────────
    wb = _opx.Workbook()
    ws = wb.active
    ws.title = "VISTA Output"

    # Header row
    for ci, col in enumerate(merged.columns, 1):
        hc           = ws.cell(1, ci, value=col)
        hc.alignment = ctr
        hc.font      = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
        if col == "Reason Category":
            hc.fill = PatternFill("solid", fgColor=HDR_CAT)
        elif col in {"d_8K", "d_10K", "d_IndStd", "d_Broker"}:
            hc.fill = PatternFill("solid", fgColor=HDR_DERIVED)
            hc.font = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
        elif col in VERIDEX_OUT:
            hc.fill = PatternFill("solid", fgColor=HDR_OUTPUT)
        else:
            hc.fill = PatternFill("solid", fgColor=HDR_INPUT)
        ws.column_dimensions[get_column_letter(ci)].width = COL_WIDTHS.get(col, 14)

    # Data rows
    for ri, (_, row) in enumerate(merged.iterrows(), 2):
        status_val = str(row.get("Status", ""))
        for ci, col in enumerate(merged.columns, 1):
            raw  = row[col]
            if not isinstance(raw, str) and pd.isna(raw):
                raw = ""
            val  = "" if str(raw) == "nan" else raw
            cell = ws.cell(ri, ci, value=val)
            cell.font      = Font(name="Calibri", size=9)
            cell.alignment = ctr

            if col == "Action":
                bg, fg = ACTION_COLORS.get(str(val), ("94a3b8","FFFFFF"))
                cell.font = Font(name="Calibri", bold=True, size=9, color=fg)
                cell.fill = PatternFill("solid", fgColor=bg)

            elif col == "Status":
                bg, fg = STATUS_COLORS.get(str(val), ("f1f5f9","374151"))
                cell.font = Font(name="Calibri", bold=True, size=9, color=fg)
                cell.fill = PatternFill("solid", fgColor=bg)

            elif col == "Reason Category":
                cell.font = Font(name="Calibri", bold=True, size=9, color="1e3a5f")
                cell.fill = PatternFill("solid", fgColor="e0e7ff")

            elif col in (reason_col, "Reason"):
                cell.alignment = lft
                cell.font      = Font(name="Calibri", size=9)

            elif col == "Error Chance":
                ec_clean = str(val) if str(val) in ("Low","Medium","High") else ""
                bg, fg = ERROR_COLORS.get(ec_clean, ("ffffff","374151"))
                cell.font = Font(name="Calibri", bold=True, size=9, color=fg)
                if ec_clean:
                    cell.fill = PatternFill("solid", fgColor=bg)
                cell.value = ec_clean

            elif col == "Who":
                who_clean = str(val) if str(val) in ("System","Human") else ""
                bg, fg = WHO_COLORS.get(who_clean, ("f8fafc","374151"))
                cell.font = Font(name="Calibri", bold=True, size=9, color=fg)
                if who_clean:
                    cell.fill = PatternFill("solid", fgColor=bg)
                cell.value = who_clean

            elif col == "Suggested Value":
                cell.font = Font(name="Calibri", bold=True, size=9)
                if status_val == "Verified":
                    cell.fill = PatternFill("solid", fgColor="f0fdf4")
                elif val:
                    cell.fill = PatternFill("solid", fgColor="eff6ff")

            elif col == "Scale Factor":
                # Highlight in amber when a scale adjustment was applied
                if val and str(val).strip():
                    cell.font = Font(name="Calibri", bold=True, size=9, color="92400e")
                    cell.fill = PatternFill("solid", fgColor="fef3c7")
                else:
                    cell.font = Font(name="Calibri", size=9, color="94a3b8")

            elif col in ("d_8K", "d_10K", "d_IndStd", "d_Broker"):
                # Derived scaled column — light teal background, right-aligned
                cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=False)
                if val is not None and val != "":
                    try:
                        float(val)
                        cell.fill = PatternFill("solid", fgColor="e6f7f7")
                        cell.font = Font(name="Calibri", size=9, color="0e4f4f")
                    except (ValueError, TypeError):
                        pass

            elif col == "% Diff":
                # Red gradient by size: >10% deep red, 1-10% amber, <1% light
                cell.font = Font(name="Calibri", bold=True, size=9)
                if val and str(val).strip():
                    try:
                        pct_v = float(str(val).replace("%", ""))
                        if pct_v > 10:
                            cell.fill = PatternFill("solid", fgColor="fee2e2")
                            cell.font = Font(name="Calibri", bold=True, size=9, color="991b1b")
                        elif pct_v > 1:
                            cell.fill = PatternFill("solid", fgColor="fef3c7")
                            cell.font = Font(name="Calibri", bold=True, size=9, color="92400e")
                        else:
                            cell.fill = PatternFill("solid", fgColor="f0fdf4")
                            cell.font = Font(name="Calibri", bold=True, size=9, color="166534")
                    except (ValueError, TypeError):
                        pass

            elif col == "Num Diff":
                # Colour by sign: negative = red tint, positive = blue tint
                cell.font = Font(name="Calibri", size=9)
                if val and str(val).strip():
                    try:
                        num_v = float(val)
                        if num_v < 0:
                            cell.fill = PatternFill("solid", fgColor="fff1f2")
                            cell.font = Font(name="Calibri", size=9, color="be123c")
                        elif num_v > 0:
                            cell.fill = PatternFill("solid", fgColor="eff6ff")
                            cell.font = Font(name="Calibri", size=9, color="1e40af")
                    except (ValueError, TypeError):
                        pass

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(merged.columns))}1"
    ws.row_dimensions[1].height = 20
    # Set all data rows to fixed height to prevent auto-wrap expansion
    for _ri in range(2, len(merged) + 2):
        ws.row_dimensions[_ri].height = 15

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)

    # Rich summary: action counts + status counts + who counts
    summary = {
        "actions": results["Action"].value_counts().to_dict(),
        "status":  results["Status"].value_counts().to_dict(),
        "who":     results["Who"].value_counts().to_dict(),
    }
    # Keep flat action dict for backward compat with download history chips
    summary_flat = results["Action"].value_counts().to_dict()
    return out.read(), summary, len(results), summary_flat

def process_excel_bytes(file_bytes: bytes, col_map: dict) -> tuple:
    """Entry point for Excel upload path."""
    df = pd.read_excel(io.BytesIO(file_bytes), header=0)
    return process_dataframe(df, col_map, source_bytes=file_bytes)


def process_api_records(records: list, col_map: dict) -> tuple:
    """Entry point for API ticker path."""
    df = pd.DataFrame(records)
    out, summary, rows, flat = process_dataframe(df, col_map, source_bytes=None)
    return out, summary, rows, flat


# ══════════════════════════════════════════════════════════════════
#  §8  MAIN UI HTML PAGE
# ══════════════════════════════════════════════════════════════════

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VISTA v3.2</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07090f;--s1:#0d1117;--s2:#111827;--s3:#161f30;
  --b1:#1c2a42;--b2:#243554;
  --tx:#b8cce4;--tx2:#6a84a8;--tx3:#e8f1ff;
  --ac:#2563eb;--ac2:#06b6d4;--gr:#10b981;--rd:#ef4444;--pk:#be185d;
}
html{scroll-behavior:smooth}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;
  background-image:radial-gradient(circle at 20% 20%,rgba(37,99,235,.07) 0,transparent 50%),
                   radial-gradient(circle at 80% 80%,rgba(6,182,212,.05) 0,transparent 50%),
                   linear-gradient(rgba(37,99,235,.025) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(37,99,235,.025) 1px,transparent 1px);
  background-size:auto,auto,48px 48px,48px 48px;pointer-events:none;z-index:0}
.shell{position:relative;z-index:1;display:grid;grid-template-columns:240px 1fr;min-height:100vh}

/* Sidebar */
.sidebar{background:var(--s1);border-right:1px solid var(--b1);padding:0;
  position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column}
.sidebar::-webkit-scrollbar{width:4px}
.sidebar::-webkit-scrollbar-thumb{background:var(--b2);border-radius:2px}
.sb-logo{padding:20px 18px 16px;border-bottom:1px solid var(--b1);display:flex;align-items:center;gap:10px}
.sb-logo-icon{width:32px;height:32px;border-radius:8px;flex-shrink:0;
  background:linear-gradient(135deg,var(--ac),var(--ac2));
  display:flex;align-items:center;justify-content:center;font-size:16px}
.sb-logo-text{font-size:13px;font-weight:700;color:var(--tx3)}
.sb-logo-ver{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--ac2)}
.sb-nav{padding:10px 8px;flex:1}
.sb-section{margin-bottom:4px}
.sb-label{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--tx2);
  letter-spacing:.1em;text-transform:uppercase;padding:6px 10px 4px}
.sb-link{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:7px;
  cursor:pointer;color:var(--tx);font-size:13px;font-weight:500;transition:all .15s;
  border:none;background:none;width:100%;text-align:left;text-decoration:none}
.sb-link:hover{background:var(--s2);color:var(--tx3)}
.sb-link.active{background:rgba(37,99,235,.18);color:#93c5fd;font-weight:600}
.sb-divider{height:1px;background:var(--b1);margin:6px 10px}
.sb-footer{padding:12px 16px;border-top:1px solid var(--b1);
  font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--tx2);line-height:1.7}

/* Main */
.main{display:flex;flex-direction:column;min-height:100vh}
.topbar{background:rgba(13,17,23,.85);backdrop-filter:blur(12px);
  border-bottom:1px solid var(--b1);padding:14px 28px;
  display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:50}
.topbar-title{font-size:15px;font-weight:700;color:var(--tx3)}
.topbar-sub{font-size:11px;color:var(--tx2);margin-top:1px}
.status-dot{display:inline-flex;align-items:center;gap:5px;
  font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--gr);
  background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);padding:3px 9px;border-radius:20px}
.status-dot::before{content:'';width:5px;height:5px;border-radius:50%;
  background:var(--gr);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}

/* Panels */
.panel{display:none;padding:28px;animation:fadeIn .2s ease}
.panel.active{display:block}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* Page head */
.page-head{margin-bottom:24px}
.page-head h2{font-size:20px;font-weight:800;color:var(--tx3);letter-spacing:-.02em;margin-bottom:4px}
.page-head p{font-size:12px;color:var(--tx2);line-height:1.6}

/* Cards */
.card{background:var(--s1);border:1px solid var(--b1);border-radius:10px;overflow:hidden;margin-bottom:14px}
.card-head{background:var(--s2);border-bottom:1px solid var(--b1);
  padding:12px 18px;display:flex;align-items:center;gap:10px}
.card-head-icon{width:26px;height:26px;border-radius:6px;
  display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0}
.card-head-title{font-size:13px;font-weight:700;color:var(--tx3)}
.card-head-sub{font-size:11px;color:var(--tx2);margin-top:1px}
.card-body{padding:20px}

/* Mode toggle */
.mode-toggle{display:flex;gap:8px;margin-bottom:16px}
.mode-btn{flex:1;padding:10px;border-radius:8px;font-family:'Outfit',sans-serif;font-size:13px;
  font-weight:600;border:1px solid var(--b1);cursor:pointer;transition:all .15s;background:var(--s2);color:var(--tx2)}
.mode-btn.active{background:rgba(37,99,235,.2);color:#93c5fd;border-color:rgba(37,99,235,.4)}

/* Form elements */
.styled-select{width:100%;padding:10px 12px;border-radius:8px;
  border:1px solid rgba(255,255,255,.12);background:rgba(15,23,42,.8);
  color:#fff;font-size:13px;outline:none;appearance:none;cursor:pointer;margin-bottom:12px}
.styled-select:focus{border-color:var(--ac);box-shadow:0 0 0 2px rgba(37,99,235,.25)}
.col-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px;margin-bottom:16px}
.col-field label{font-size:10px;color:var(--tx2);font-family:'JetBrains Mono',monospace;
  text-transform:uppercase;letter-spacing:.07em;display:block;margin-bottom:3px}
.col-field input{width:100%;background:var(--s2);border:1px solid var(--b1);border-radius:6px;
  padding:6px 10px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--tx3)}
.col-field input:focus{outline:none;border-color:var(--ac)}
.col-field input::placeholder{color:var(--tx2)}

/* Buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;
  padding:11px 20px;border-radius:8px;font-family:'Outfit',sans-serif;
  font-size:13px;font-weight:700;border:none;cursor:pointer;transition:all .2s}
.btn-primary{background:linear-gradient(135deg,var(--ac),#1d4ed8);color:#fff;width:100%;margin-top:12px}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 5px 18px rgba(37,99,235,.4)}
.btn-primary:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}
.btn-dl{background:linear-gradient(135deg,var(--gr),#059669);color:#fff;width:100%}
.btn-dl:hover{transform:translateY(-1px);box-shadow:0 5px 18px rgba(16,185,129,.4)}
.btn-bc{background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;width:100%}
.btn-bc:hover{transform:translateY(-1px);box-shadow:0 5px 18px rgba(124,58,237,.4)}
.btn-bc:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}
.dual-btn-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.period-dropdown{position:relative;width:100%;font-family:'Outfit',sans-serif}
.period-trigger{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;background:var(--s2);border:1px solid var(--b1);border-radius:8px;cursor:pointer;font-size:13px;color:var(--tx);transition:border-color .15s;user-select:none}
.period-trigger:hover,.period-trigger.open{border-color:#06b6d4}
.period-trigger .arrow{transition:transform .2s;color:var(--tx2);font-size:10px}
.period-trigger.open .arrow{transform:rotate(180deg)}
.period-badge{background:#06b6d4;color:#fff;font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px;margin-left:6px}
.period-panel{display:none;position:fixed;background:var(--s2);border:1px solid var(--b1);border-radius:8px;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.5);overflow:hidden;min-width:200px}
.period-panel.open{display:block}
.period-search-wrap{padding:8px 10px;border-bottom:1px solid var(--b1);display:flex;align-items:center;gap:7px}
.period-search-wrap input{flex:1;background:var(--s3);border:1px solid var(--b1);border-radius:5px;padding:5px 9px;font-size:12px;color:var(--tx3);outline:none;font-family:'JetBrains Mono',monospace}
.period-search-wrap input:focus{border-color:#06b6d4}
.period-actions{display:flex;gap:6px;padding:0 10px 7px;border-bottom:1px solid var(--b1)}
.period-act-btn{font-size:10px;color:#06b6d4;background:none;border:none;cursor:pointer;padding:0;font-family:'Outfit',sans-serif;font-weight:600}
.period-act-btn:hover{text-decoration:underline}
.period-list{max-height:200px;overflow-y:auto;padding:4px 0}
.period-list::-webkit-scrollbar{width:4px}
.period-list::-webkit-scrollbar-thumb{background:var(--b2);border-radius:2px}
.period-item{display:flex;align-items:center;gap:9px;padding:6px 12px;cursor:pointer;font-size:12px;color:var(--tx);transition:background .1s;font-family:'JetBrains Mono',monospace}
.period-item:hover{background:var(--s3)}
.period-item input[type=checkbox]{width:14px;height:14px;accent-color:#06b6d4;cursor:pointer;flex-shrink:0}

/* Dropzone */
.dropzone{border:2px dashed var(--b2);border-radius:10px;padding:36px 20px;
  text-align:center;cursor:pointer;transition:all .2s;background:var(--s2);position:relative}
.dropzone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.dropzone:hover,.dropzone.over{border-color:var(--ac);background:rgba(37,99,235,.06)}
.dz-icon{font-size:36px;display:block;margin-bottom:12px}
.dz-title{font-size:14px;font-weight:700;color:var(--tx3);margin-bottom:4px}
.dz-sub{font-size:11px;color:var(--tx2)}
.dz-sub span{color:var(--ac)}
.dz-file{margin-top:12px;padding:7px 12px;background:rgba(16,185,129,.1);
  border:1px solid rgba(16,185,129,.25);border-radius:7px;font-family:'JetBrains Mono',monospace;
  font-size:11px;color:#6ee7b7;display:none;align-items:center;gap:7px}

/* Progress */
.prog-wrap{display:none;margin-top:16px}
.prog-bar{height:3px;background:var(--s3);border-radius:2px;overflow:hidden}
.prog-fill{height:100%;background:linear-gradient(90deg,var(--ac),var(--ac2));
  border-radius:2px;width:0;transition:width .3s}
.prog-lbl{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tx2);margin-top:6px;text-align:center}

/* Results */
.result-card{display:none;margin-top:16px;border-radius:10px;overflow:hidden;
  border:1px solid rgba(16,185,129,.25);animation:fadeIn .3s ease}
.result-head{background:rgba(16,185,129,.08);padding:12px 16px;
  display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid rgba(16,185,129,.18)}
.result-title{font-size:13px;font-weight:700;color:#6ee7b7}
.result-rows{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tx2)}
.result-body{padding:16px 18px}
.stats-section{margin-bottom:14px}
.stats-section-label{font-size:9px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.1em;color:var(--tx2);margin-bottom:6px;padding-left:2px}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px}
.stat{padding:10px 16px;background:var(--s2);border:1px solid var(--b1);border-radius:8px;min-width:110px;text-align:center}
.stat-lbl{font-size:10px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;font-weight:600}
.stat-val{font-size:22px;font-weight:800;color:var(--tx3)}
.stat{padding:9px 12px;background:var(--s2);border:1px solid var(--b1);border-radius:8px}
.stat-lbl{font-size:9px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:2px}
.stat-val{font-size:18px;font-weight:800;color:var(--tx3)}

/* Error */
.err{display:none;margin-top:12px;padding:11px 14px;background:rgba(239,68,68,.08);
  border:1px solid rgba(239,68,68,.28);border-radius:8px;font-size:12px;color:#fca5a5}

/* Spinner */
.spinner{width:14px;height:14px;border:2px solid rgba(255,255,255,.25);
  border-top-color:#fff;border-radius:50%;animation:spin .65s linear infinite;display:none}
@keyframes spin{to{transform:rotate(360deg)}}

/* Sections / guide grid */
.guide-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
@media(max-width:700px){.guide-grid{grid-template-columns:1fr}}
.guide-card{background:var(--s2);border:1px solid var(--b1);border-radius:10px;padding:16px}
.guide-card h4{font-size:12px;font-weight:700;color:var(--tx3);margin-bottom:9px;
  display:flex;align-items:center;gap:7px}
.guide-card ul{list-style:none;display:flex;flex-direction:column;gap:5px}
.guide-card li{font-size:11px;color:var(--tx);line-height:1.5;display:flex;align-items:flex-start;gap:7px}
.li-dot{width:5px;height:5px;border-radius:50%;flex-shrink:0;margin-top:5px}
.sec-badge{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:9px;
  font-weight:700;padding:2px 7px;border-radius:4px;margin-right:4px}
.badge-a{background:rgba(16,185,129,.2);color:#6ee7b7}
.badge-b{background:rgba(29,78,216,.2);color:#93c5fd}
.badge-c{background:rgba(239,68,68,.2);color:#fca5a5}
.badge-d{background:rgba(29,78,216,.2);color:#93c5fd}
.badge-e{background:rgba(249,115,22,.2);color:#fdba74}
.badge-f{background:rgba(190,24,93,.2);color:#f9a8d4}
.rule-table{width:100%;border-collapse:collapse;font-size:11px}
.rule-table th{background:var(--s3);color:var(--tx2);font-family:'JetBrains Mono',monospace;
  font-size:9px;text-transform:uppercase;letter-spacing:.07em;
  padding:7px 10px;text-align:left;border-bottom:1px solid var(--b1)}
.rule-table td{padding:7px 10px;border-bottom:1px solid var(--b1);color:var(--tx);vertical-align:top}
.rule-table tr:last-child td{border-bottom:none}
.rule-table tr:hover td{background:rgba(255,255,255,.012)}
.mono{font-family:'JetBrains Mono',monospace;font-size:10px;color:#93c5fd}
.callout{padding:12px 14px;border-radius:8px;font-size:12px;line-height:1.6;margin:12px 0;
  display:flex;align-items:flex-start;gap:10px}
.callout-warn{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);color:#fcd34d}
.callout-ok{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);color:#6ee7b7}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--b2);border-radius:3px}
</style>
</head>
<body>
<div class="shell">

<!-- ══ SIDEBAR ══ -->
<nav class="sidebar">
  <div class="sb-logo">
    <div class="sb-logo-icon">⚡</div>
    <div>
      <div class="sb-logo-text">VISTA</div>
      <div class="sb-logo-ver">v3.2 · Production</div>
    </div>
  </div>
  <div class="sb-nav">
    <div class="sb-section">
      <div class="sb-label">Main</div>
      <button class="sb-link active" onclick="nav('upload')">
        <span>📊</span> Select &amp; Process
      </button>
    </div>
    <div class="sb-divider"></div>
    <div class="sb-section">
      <div class="sb-label">Logic Reference</div>
      <button class="sb-link" onclick="nav('sections')">
        <span>🌳</span> All Sections (A–F)
      </button>
      <button class="sb-link" onclick="nav('columns')">
        <span>📋</span> Column Reference
      </button>
    </div>
    <div class="sb-divider"></div>
    <div class="sb-section">
      <div class="sb-label">Settings</div>

      <a href="/downloads" class="sb-link" style="text-decoration:none">
        <span>⬇</span> Download History
      </a>
    </div>
  </div>
  <div class="sb-footer">
    VISTA · Python · Flask · openpyxl<br>
    4 Actions: No Action · Push · Review · Escalate
  </div>
</nav>

<!-- ══ MAIN ══ -->
<div class="main">
  <div class="topbar">
    <div>
      <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:2px">
        <span style="font-size:20px;font-weight:900;letter-spacing:0.1em;color:var(--tx3);font-family:'JetBrains Mono',monospace;line-height:1">VISTA</span>
        <span style="font-size:9.5px;color:var(--tx2);line-height:1.35">Verification &amp; Integrated Systems for Trusted Analytics</span>
      </div>
      <div class="topbar-sub" id="topbar-sub">Apply VISTA decision logic to your consensus data</div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <div style="text-align:right;line-height:1.3">
        <div style="font-size:22px;font-weight:900;letter-spacing:0.18em;
             background:linear-gradient(135deg,#2563eb,#06b6d4);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
             background-clip:text">VISTA</div>
        <div style="font-size:8px;color:var(--tx2);letter-spacing:0.04em;font-weight:400;
             white-space:nowrap">Verification &amp; Integrated Systems<br>for Trusted Analytics</div>
      </div>
      <div class="status-dot">v3.2 · running</div>
    </div>
  </div>

  <!-- ─── UPLOAD PANEL ─── -->
  <div class="panel active" id="panel-upload">
    <div class="page-head">
      <h2>Select &amp; Process</h2>
      <p>Choose a ticker from the live database <em>or</em> upload an Excel file directly.</p>
    </div>

    <!-- Mode toggle -->
    <div class="mode-toggle">
      <button class="mode-btn active" id="btnModeTicker" onclick="setMode('ticker')">
        📡 Live Ticker (API)
      </button>
      <button class="mode-btn" id="btnModeFile" onclick="setMode('file')">
        📁 Upload Excel File
      </button>
    </div>

    <!-- TICKER MODE -->
    <div id="modeTicker">
      <div class="card">
        <div class="card-head">
          <div class="card-head-icon" style="background:rgba(37,99,235,.15)">📊</div>
          <div>
            <div class="card-head-title">Select Ticker(s)</div>
            <div class="card-head-sub">Excel-style dropdown — search, check one or many</div>
          </div>
        </div>
        <div class="card-body">
          {% if tickers %}

          <!-- Excel-style multi-select dropdown -->
          <style>
            .ticker-dropdown{position:relative;width:100%;margin-bottom:12px;font-family:'Outfit',sans-serif}
            .ticker-trigger{display:flex;align-items:center;justify-content:space-between;
              padding:9px 12px;background:var(--s2);border:1px solid var(--b1);border-radius:8px;
              cursor:pointer;font-size:13px;color:var(--tx);transition:border-color .15s;user-select:none}
            .ticker-trigger:hover,.ticker-trigger.open{border-color:var(--ac)}
            .ticker-trigger .arrow{transition:transform .2s;color:var(--tx2);font-size:10px}
            .ticker-trigger.open .arrow{transform:rotate(180deg)}
            .ticker-badge{background:var(--ac);color:#fff;font-size:10px;font-weight:700;
              padding:1px 6px;border-radius:10px;margin-left:6px}
            .ticker-panel{display:none;position:fixed;
              background:var(--s2);border:1px solid var(--b1);border-radius:8px;
              z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.5);overflow:hidden;
              min-width:200px}
            .ticker-panel.open{display:block}
            .ticker-search-wrap{padding:8px 10px;border-bottom:1px solid var(--b1);display:flex;align-items:center;gap:7px}
            .ticker-search-wrap input{flex:1;background:var(--s3);border:1px solid var(--b1);
              border-radius:5px;padding:5px 9px;font-size:12px;color:var(--tx3);outline:none;
              font-family:'JetBrains Mono',monospace}
            .ticker-search-wrap input:focus{border-color:var(--ac)}
            .ticker-actions{display:flex;gap:6px;padding:0 10px 7px;border-bottom:1px solid var(--b1)}
            .ticker-act-btn{font-size:10px;color:var(--ac);background:none;border:none;
              cursor:pointer;padding:0;font-family:'Outfit',sans-serif;font-weight:600}
            .ticker-act-btn:hover{text-decoration:underline}
            .ticker-list{max-height:220px;overflow-y:auto;padding:4px 0}
            .ticker-list::-webkit-scrollbar{width:4px}
            .ticker-list::-webkit-scrollbar-thumb{background:var(--b2);border-radius:2px}
            .ticker-item{display:flex;align-items:center;gap:9px;padding:6px 12px;
              cursor:pointer;font-size:12px;color:var(--tx);transition:background .1s}
            .ticker-item:hover{background:var(--s3)}
            .ticker-item.checked{color:var(--tx3);font-weight:500}
            .ticker-item input[type=checkbox]{width:14px;height:14px;accent-color:var(--ac);
              cursor:pointer;flex-shrink:0}
            .ticker-empty{padding:16px;text-align:center;font-size:12px;color:var(--tx2)}
          </style>

          <div class="ticker-dropdown" id="tickerDropdown">
            <div class="ticker-trigger" id="tickerTrigger" onclick="toggleTickerPanel()">
              <span id="tickerTriggerLabel">— Select tickers —</span>
              <span class="arrow">▼</span>
            </div>
            <div class="ticker-panel" id="tickerPanel">
              <div class="ticker-search-wrap">
                <span style="color:var(--tx2);font-size:12px">🔍</span>
                <input type="text" id="tickerSearch" placeholder="Search tickers…"
                       oninput="filterTickers(this.value)" autocomplete="off">
              </div>
              <div class="ticker-actions">
                <button class="ticker-act-btn" onclick="tickerSelectAll()">Select All</button>
                <span style="color:var(--b2)">·</span>
                <button class="ticker-act-btn" onclick="tickerClearAll()">Clear All</button>
              </div>
              <div class="ticker-list" id="tickerList">
                {% for t in tickers %}
                <label class="ticker-item" id="ti_{{ t }}">
                  <input type="checkbox" value="{{ t }}" onchange="onTickerCheck()"> {{ t }}
                </label>
                {% endfor %}
              </div>
            </div>
          </div>

          {% else %}
          <div class="callout callout-warn">
            ⚠ Database / API not reachable — ticker list unavailable.
            Switch to <strong>Upload Excel File</strong> mode below.
          </div>
          {% endif %}

          <button class="btn btn-primary" id="btnRun" onclick="run()"
            {% if not tickers %}disabled{% endif %}>
            <div class="spinner" id="spin"></div>
            <span id="btnTxt">⚡ Fetch &amp; Process</span>
          </button>
        </div>
      </div>
    </div>

    <!-- FILE MODE -->
    <div id="modeFile" style="display:none">
      <div class="card">
        <div class="card-head">
          <div class="card-head-icon" style="background:rgba(16,185,129,.15)">📁</div>
          <div>
            <div class="card-head-title">Upload Excel File</div>
            <div class="card-head-sub">No API needed — process any .xlsx file directly</div>
          </div>
        </div>
        <div class="card-body">
          <div class="dropzone" id="dz">
            <input type="file" accept=".xlsx,.xls" id="fileInput" onchange="onFile(this)">
            <span class="dz-icon">📂</span>
            <div class="dz-title">Drop your Excel file here</div>
            <div class="dz-sub">or <span>click to browse</span> · .xlsx / .xls</div>
            <div class="dz-file" id="dzFile">📄 <span id="dzFileName"></span></div>
          </div>
          <button class="btn btn-primary" id="btnRunFile" onclick="runFile()" disabled>
            <div class="spinner" id="spinFile"></div>
            <span id="btnTxtFile">⚡ Process File</span>
          </button>
        </div>
      </div>
    </div>


    <!-- Column overrides (shared) -->
    <div class="card">
      <div class="card-head">
        <div class="card-head-icon" style="background:rgba(139,92,246,.15)">⚙</div>
        <div>
          <div class="card-head-title">Column Name Overrides</div>
          <div class="card-head-sub">Only needed if your file uses non-standard column names</div>
        </div>
      </div>
      <div class="card-body">
        <div class="col-grid">
          <div class="col-field"><label>Con_num</label><input id="c0" placeholder="Con_num"></div>
          <div class="col-field"><label>IndStd Filling</label><input id="c1" placeholder="IndStd Filling"></div>
          <div class="col-field"><label>10K</label><input id="c2" placeholder="10K"></div>
          <div class="col-field"><label>8K</label><input id="c3" placeholder="8K"></div>
          <div class="col-field"><label>Broker Mode</label><input id="c4" placeholder="Broker Mode"></div>
          <div class="col-field"><label>ModelmatchCount</label><input id="c5" placeholder="ModelmatchCount"></div>
          <div class="col-field"><label>Revised Source</label><input id="c6" placeholder="Revised Source"></div>
        </div>
      </div>
    </div>

    <!-- Shared results -->
    <div class="err" id="errBox"></div>
    <div class="prog-wrap" id="progWrap">
      <div class="prog-bar"><div class="prog-fill" id="progFill"></div></div>
      <div class="prog-lbl" id="progLbl">Processing…</div>
    </div>
    <div class="result-card" id="resCard">
      <div class="result-head">
        <div class="result-title">✅ Processing complete</div>
        <div style="display:flex;align-items:center;gap:14px">
          <div class="result-rows" id="resRows"></div>
          <div style="font-family:'JetBrains Mono',monospace;font-size:10px;
               color:#6ee7b7;background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.25);
               padding:2px 9px;border-radius:10px;display:none" id="resTime"></div>
        </div>
      </div>
      <div class="result-body">
        <div id="statsGrid"></div>
        <button class="btn btn-dl" onclick="dl()">⬇&nbsp; Download Results (.xlsx)</button>
      </div>
    </div>
  </div>

  <!-- ─── ALL SECTIONS PANEL ─── -->
  <div class="panel" id="panel-sections">
    <div class="page-head">
      <h2>All Sections — Logic Reference</h2>
      <p>Conditions evaluated top-down. First match wins. Actions:
        <strong style="color:#10b981">No Action</strong> ·
        <strong style="color:#1d4ed8">Push</strong> ·
        <strong style="color:#dc2626">Review</strong> ·
        <strong style="color:#7c3aed">Derived</strong> ·
        <strong style="color:#64748b">No Data</strong></p>
    </div>

    <!-- Entry Gates -->
    <div class="card" style="margin-bottom:14px">
      <div class="card-head">
        <div class="card-head-icon" style="background:rgba(6,182,212,.15)">⚡</div>
        <div>
          <div class="card-head-title">Entry Gates — evaluated before all sections</div>
          <div class="card-head-sub">Scale cross-check also runs here: Con ×/÷ −1, 100, 1000, 10000, 100000 — if within threshold, treated as normal number</div>
        </div>
      </div>
      <div class="card-body" style="padding:14px 18px">
        <table class="rule-table">
          <thead><tr><th>Code</th><th>Condition</th><th>Action · Status · Error · Who</th></tr></thead>
          <tbody>
            <tr><td><span class="mono">G0a</span></td><td>Revised Source = "Calculated"</td><td style="color:#7c3aed">Derived · Not Verified · Medium · System</td></tr>
            <tr><td><span class="mono">G0b</span></td><td>Revised Source = "Sell-Side" / "Sell-Side Calculated"</td><td style="color:#7c3aed">Derived · Not Verified · Medium · System</td></tr>
            <tr><td><span class="mono">A3.3</span></td><td>Con = 10K only (no VA / 8K / Broker)</td><td style="color:#10b981">No Action · Verified · Low · System</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="guide-grid">
      <!-- Section A -->
      <div class="guide-card">
        <h4><span class="sec-badge badge-a">A</span>Auto Verified — No Action / Push · System</h4>
        <ul>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A1.1</span>Con = Mode [4x: VA, 10K, 8K, Broker] → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A1.2</span>Con = Mode [3x: e.g. 10K, 8K, Broker] → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A1.3</span>Con = Mode [2x: e.g. VA, Broker] → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A2.1</span>Con = VA, sole source (no EF / Broker) → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#1d4ed8"></div><span class="mono" style="font-size:9px;margin-right:4px">A2.2</span>Con = VA (rounded) → <strong>Push</strong> · Verified · Low</li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A3.1</span>Con = 8K exact, no VA → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A3.2</span>Con = 8K (rounded), no VA → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A3.3</span>Con = 10K sole source → No Action · Verified · Low <em>(Gate)</em></li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A3.4</span>Con = 10K (rounded), no VA → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#10b981"></div><span class="mono" style="font-size:9px;margin-right:4px">A4.1</span>Con = Broker exact, no VA or EF → No Action · Verified · Low</li>
          <li><div class="li-dot" style="background:#1d4ed8"></div><span class="mono" style="font-size:9px;margin-right:4px">A4.2</span>Con = Broker (rounded), no VA or EF → <strong>Push</strong> · Verified · Low</li>
          <li><div class="li-dot" style="background:#1d4ed8"></div><span class="mono" style="font-size:9px;margin-right:4px">A5</span>Mode valid, Con wrong (rounded, ≤threshold), ≥1 broker match → <strong>Push</strong> · Verified · Low</li>
        </ul>
      </div>

      <!-- Section B -->
      <div class="guide-card">
        <h4><span class="sec-badge badge-c">B</span>Review — Human Required</h4>
        <ul>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B1</span>VA missing, EF only → No Mode Available · Not Verified · High · Human</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B2</span>Broker sole, ≥2 model match, Con≠Broker → Consensus≠Broker · Not Verified · High · Human</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B3</span>Blank consensus, unconfirmed → Not Verified · High · Human<br><small style="color:var(--tx2)">Suggested Value blank if &lt;2 params agree</small></li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B4</span>Mode conflict, gap &gt;threshold (1%/0.5%) → Check &amp; Deploy · Not Verified · High · Human</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B4</span>VA isolated / sign conflict → Not Verified · High · Human</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B5</span>3-way mismatch: VA ≠ EF ≠ Broker → Not Verified · High · Human</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B5</span>EF intra-conflict: 8K ≠ 10K → Not Verified · High · Human</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B5</span>EF / VA sign conflict → Not Verified · High · Human</li>
          <li><div class="li-dot" style="background:#64748b"></div><span class="mono" style="font-size:9px;margin-right:4px">B6</span>Consensus Unverifiable: no sources → <strong>No Data</strong> · Not Verified · Medium · Human</li>
          <li><div class="li-dot" style="background:#64748b"></div><span class="mono" style="font-size:9px;margin-right:4px">B7</span>All data blank → <strong>No Data</strong> · Not Verified · Medium · Human</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">B8</span>Con=Broker but EF present and EF≠Con → Not Verified · Medium · Human</li>
        </ul>
      </div>

      <!-- Section D -->
      <div class="guide-card">
        <h4><span class="sec-badge badge-d">D</span>Push — Rectification</h4>
        <ul>
          <li><div class="li-dot" style="background:#1d4ed8"></div><span class="mono" style="font-size:9px;margin-right:4px">D1</span>Con≠VA, VA+EF agree, ≥1 broker → Push · Low (High if gap&gt;threshold) · System</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">D1</span>VA+EF agree, 0 broker → Review · Medium · Human</li>
          <li><div class="li-dot" style="background:#1d4ed8"></div><span class="mono" style="font-size:9px;margin-right:4px">D2</span>Con≠EF, VA missing, EF+Broker agree → Push · Low · System</li>
          <li><div class="li-dot" style="background:#1d4ed8"></div><span class="mono" style="font-size:9px;margin-right:4px">D3</span>Con≠VA, VA+Broker agree, no EF → Push · Low · System</li>
          <li><div class="li-dot" style="background:#dc2626"></div><span class="mono" style="font-size:9px;margin-right:4px">D4</span>Broker only, Con suspect → Review · High · Human</li>
          <li><div class="li-dot" style="background:#be185d"></div><span class="mono" style="font-size:9px;margin-right:4px">D5</span>No structured source → Review · High · Human</li>
        </ul>
        <div style="margin-top:8px;padding:8px;background:var(--s3);border-radius:6px;font-size:11px;color:var(--tx2)">
          Review paths → Suggested Value shows <span class="mono">[NO MATCH — Src: val]</span>
        </div>
      </div>

      <!-- Entry Gates / G codes -->
      <div class="guide-card">
        <h4><span class="sec-badge badge-f">G</span>Derived — System Auto-Flag</h4>
        <ul>
          <li><div class="li-dot" style="background:#7c3aed"></div><span class="mono" style="font-size:9px;margin-right:4px">G0a</span>Revised Source = Calculated → Derived · Not Verified · Medium · System</li>
          <li><div class="li-dot" style="background:#7c3aed"></div><span class="mono" style="font-size:9px;margin-right:4px">G0b</span>Revised Source = Sell-Side → Derived · Not Verified · Medium · System</li>
        </ul>
        <div style="margin-top:10px;padding:9px;background:var(--s3);border-radius:7px;font-size:11px;color:var(--tx2);line-height:1.8">
          <strong style="color:var(--tx3)">Threshold logic:</strong><br>
          1) Consensus as base<br>
          2) Cross-check with 8K, 10K, VA, Broker Mode<br>
          3) Gap % threshold: P format → 0.5% · N format ≥100 → 1.0% · N &lt;100 → 0.5%<br>
          4) Scale check: Con × or ÷ −1 / 100 / 1000 / 10000 / 100000<br>
          5) Compare each parameter for mode within parameter<br>
          <br>
          <strong style="color:var(--tx3)">Suggested Value:</strong> blank when consensus is blank or fewer than 2 parameters agree<br>
          <br>
          <strong style="color:var(--tx3)">8K auto-norm:</strong> |8K÷Con|&gt;500 → ÷1,000
        </div>
      </div>
    </div>
  </div>


    <!-- ─── COLUMN REFERENCE ─── -->
  <div class="panel" id="panel-columns">
    <div class="page-head">
      <h2>Column Reference</h2>
      <p>Required input columns and what VISTA writes back.</p>
    </div>
    <div class="card">
      <div class="card-head">
        <div class="card-head-icon" style="background:rgba(6,182,212,.15)">📥</div>
        <div><div class="card-head-title">Input Columns</div></div>
      </div>
      <div class="card-body">
        <table class="rule-table">
          <thead><tr><th>Column</th><th>Required</th><th>Notes</th></tr></thead>
          <tbody>
            <tr><td><span class="mono">Con_num</span></td><td>Yes</td><td>Consensus current value. Blank = treated as incorrect.</td></tr>
            <tr><td><span class="mono">IndStd Filling</span></td><td>Recommended</td><td>VA Filing source value. Highest priority source.</td></tr>
            <tr><td><span class="mono">10K</span></td><td>Optional</td><td>Earnings Filing 10-K value.</td></tr>
            <tr><td><span class="mono">8K</span></td><td>Optional</td><td>Earnings Filing 8-K. Auto-normalised if raw units detected.</td></tr>
            <tr><td><span class="mono">Broker Mode</span></td><td>Optional</td><td>Mode value from broker models. Lowest priority source.</td></tr>
            <tr><td><span class="mono">ModelmatchCount</span></td><td>Optional</td><td>Number of broker models matching Con_num.</td></tr>
            <tr><td><span class="mono">Revised Source</span></td><td>Optional</td><td>If = "Calculated", routes to Calc gates / C5.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="card-head">
        <div class="card-head-icon" style="background:rgba(16,185,129,.15)">📤</div>
        <div><div class="card-head-title">Output Columns (filled by VISTA)</div></div>
      </div>
      <div class="card-body">
        <table class="rule-table">
          <thead><tr><th>Column</th><th>Values</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><span class="mono">Action</span></td>
                <td>No Action · Push · Review · Escalate</td>
                <td>Recommended action — always one of 4 values</td></tr>
            <tr><td><span class="mono">Status</span></td>
                <td>Verified · Not Verified</td>
                <td>Whether VISTA is confident in the consensus value</td></tr>
            <tr><td><span class="mono">Reason Category</span></td>
                <td>A0, B1, C3, G0a … (code only)</td>
                <td>Short code identifying which rule fired — section letter + number</td></tr>
            <tr><td><span class="mono">Reason</span></td>
                <td>Text description</td>
                <td>Full reason including round-off notes</td></tr>
            <tr><td><span class="mono">Final Source</span></td>
                <td>VA Filing · 10K · 8K · Broker · blank</td>
                <td>Authoritative source used for the confirmed or suggested value</td></tr>
            <tr><td><span class="mono">Suggested Value</span></td>
                <td>Number · [NO MATCH — Src: val] · [RAW UNIT ERROR: val] · blank</td>
                <td>Push paths: corrected value. Review paths: reference note. Blank if Con already matches.</td></tr>
            <tr><td><span class="mono">Error Chance</span></td>
                <td>Low · Medium · High</td>
                <td>Confidence level of the output</td></tr>
            <tr><td><span class="mono">Who</span></td>
                <td>System · Human</td>
                <td>System = can be automated. Human = needs manual review.</td></tr>        </table>
      </div>
    </div>
  </div>

</div><!-- end main -->
</div><!-- end shell -->

<script>
// ── NAV ───────────────────────────────────────────────────────
const PANELS = {
  upload:  { title:'Select & Process',   sub:'Apply VISTA decision logic to your consensus data' },
  sections:{ title:'All Sections (A–F)', sub:'Complete VISTA decision tree reference' },
  columns: { title:'Column Reference',   sub:'Input and output column documentation' },
};
function nav(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sb-link').forEach(l => l.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  const lnk = document.querySelector(`[onclick="nav('${id}')"]`);
  if (lnk) lnk.classList.add('active');
  document.getElementById('topbar-title').textContent = PANELS[id]?.title || id;
  document.getElementById('topbar-sub').textContent   = PANELS[id]?.sub   || '';
  window.scrollTo(0,0);
}

// ── Mode toggle ───────────────────────────────────────────────
let currentMode = 'ticker';
function setMode(mode) {
  currentMode = mode;
  ['ticker','file'].forEach(m => {
    const el = document.getElementById('mode' + m[0].toUpperCase() + m.slice(1));
    if (el) el.style.display = m === mode ? 'block' : 'none';
    const btn = document.getElementById('btnMode' + m[0].toUpperCase() + m.slice(1));
    if (btn) btn.classList.toggle('active', m === mode);
  });
  hideResults();
}

function hideResults() {
  document.getElementById('resCard').style.display = 'none';
  document.getElementById('errBox').style.display  = 'none';
  resultBlob = null;
}

// ── State ─────────────────────────────────────────────────────
let selectedTickers = [];
let selectedFile    = null;
let resultBlob      = null;
let dlFilename      = 'vista_output.xlsx';
let _runStart       = 0;   // performance.now() when processing started

// ── Ticker dropdown (Excel-style checkbox) ────────────────────
function toggleTickerPanel() {
  const panel   = document.getElementById('tickerPanel');
  const trigger = document.getElementById('tickerTrigger');
  const isOpen  = panel.classList.contains('open');
  if (isOpen) {
    panel.classList.remove('open');
    trigger.classList.remove('open');
  } else {
    // Position panel using fixed coords so it clears overflow:hidden parents
    const rect = trigger.getBoundingClientRect();
    panel.style.top   = (rect.bottom + 4) + 'px';
    panel.style.left  = rect.left + 'px';
    panel.style.width = rect.width + 'px';
    panel.classList.add('open');
    trigger.classList.add('open');
    document.getElementById('tickerSearch').focus();
  }
}

// Close panel when clicking outside
document.addEventListener('click', function(e) {
  const dd = document.getElementById('tickerDropdown');
  if (dd && !dd.contains(e.target)) {
    document.getElementById('tickerPanel')?.classList.remove('open');
    document.getElementById('tickerTrigger')?.classList.remove('open');
  }
});

function filterTickers(q) {
  const items = document.querySelectorAll('.ticker-item');
  const lq = q.toLowerCase();
  let visible = 0;
  items.forEach(item => {
    const match = item.textContent.trim().toLowerCase().includes(lq);
    item.style.display = match ? 'flex' : 'none';
    if (match) visible++;
  });
  const empty = document.getElementById('tickerEmpty');
  if (empty) empty.style.display = visible === 0 ? 'block' : 'none';
}

function onTickerCheck() {
  selectedTickers = Array.from(
    document.querySelectorAll('.ticker-list input[type=checkbox]:checked')
  ).map(cb => cb.value);
  _updateTickerTrigger();
  hideResults();
}

function tickerSelectAll() {
  document.querySelectorAll('.ticker-list input[type=checkbox]').forEach(cb => {
    if (cb.closest('.ticker-item').style.display !== 'none') cb.checked = true;
  });
  onTickerCheck();
}

function tickerClearAll() {
  document.querySelectorAll('.ticker-list input[type=checkbox]').forEach(cb => cb.checked = false);
  onTickerCheck();
}

function _updateTickerTrigger() {
  const lbl = document.getElementById('tickerTriggerLabel');
  const btn = document.getElementById('btnRun');
  const n   = selectedTickers.length;
  if (n === 0) {
    lbl.innerHTML = '— Select tickers —';
  } else if (n === 1) {
    lbl.innerHTML = `<strong>${selectedTickers[0]}</strong>`;
  } else {
    lbl.innerHTML = `<strong>${selectedTickers.slice(0,3).join(', ')}${n > 3 ? ` + ${n-3} more` : ''}</strong>
      <span class="ticker-badge">${n}</span>`;
  }
  if (btn) btn.disabled = n === 0;
}

function onFile(input) {
  selectedFile = input.files[0];
  if (!selectedFile) return;
  document.getElementById('dzFileName').textContent = selectedFile.name;
  document.getElementById('dzFile').style.display   = 'flex';
  document.getElementById('btnRunFile').disabled    = false;
  document.getElementById('btnRunFileBC').disabled  = false;
  hideResults();
  // Fetch periods
  (async()=>{const fd2=new FormData();fd2.append('file',selectedFile);try{const r=await fetch('/get_periods',{method:'POST',body:fd2});const d=await r.json();populatePeriods(d.periods||[]);}catch(e){console.warn(e);}})();
}

// ── Column map ────────────────────────────────────────────────
function buildColMap() {
  const keys = ['Con_num','IndStd Filling','10K','8K',
                'Broker Mode','ModelmatchCount','Revised Source'];
  const fd = new FormData();
  ['c0','c1','c2','c3','c4','c5','c6'].forEach((id,i) => {
    const v = (document.getElementById(id)?.value || '').trim();
    if (v) fd.append(keys[i], v);
  });
  return fd;
}

// ── Progress helpers ──────────────────────────────────────────
function startProgress(msg) {
  _runStart = performance.now();
  document.getElementById('progWrap').style.display = 'block';
  document.getElementById('progLbl').textContent    = msg;
  document.getElementById('errBox').style.display   = 'none';
  document.getElementById('resCard').style.display  = 'none';
  const rt = document.getElementById('resTime');
  if (rt) rt.style.display = 'none';
  let pct = 0;
  return setInterval(() => {
    pct = Math.min(pct + Math.random() * 4, 88);
    document.getElementById('progFill').style.width = pct + '%';
  }, 220);
}
function stopProgress(timer) {
  clearInterval(timer);
  document.getElementById('progFill').style.width = '100%';
  setTimeout(() => { document.getElementById('progWrap').style.display = 'none'; }, 600);
}
function showError(msg) {
  const e = document.getElementById('errBox');
  e.textContent = '❌ ' + msg; e.style.display = 'block';
}
function showResults(summary, rowCount, blob, fname) {
  resultBlob = blob; dlFilename = fname;
  document.getElementById('resRows').textContent = rowCount.toLocaleString() + ' rows processed';
  const grid = document.getElementById('statsGrid');
  grid.innerHTML = '';

  const actionColors = {
    'No Action':'#10b981','Push':'#1d4ed8','Review':'#dc2626',
    'Escalate':'#be185d','Derived':'#7c3aed','No Data':'#64748b'
  };
  const statusColors = {
    'Verified':'#10b981','Not Verified':'#ef4444','No Data':'#94a3b8'
  };
  const whoColors = { 'System':'#3b82f6','Human':'#f59e0b' };

  function makeGroup(label, entries, colorMap, defaultColor) {
    if (!entries || Object.keys(entries).length === 0) return;
    const sec = document.createElement('div');
    sec.className = 'stats-section';
    sec.innerHTML = `<div class="stats-section-label">${label}</div>`;
    const row = document.createElement('div');
    row.className = 'stats';
    Object.entries(entries).sort((a,b) => b[1]-a[1]).forEach(([k,v]) => {
      const col = colorMap[k] || defaultColor || '#64748b';
      const card = document.createElement('div');
      card.className = 'stat';
      card.style.borderTop = `3px solid ${col}`;
      card.innerHTML = `<div class="stat-lbl" style="color:${col}">${k}</div><div class="stat-val">${v.toLocaleString()}</div>`;
      row.appendChild(card);
    });
    sec.appendChild(row);
    grid.appendChild(sec);
  }

  makeGroup('Action', summary.actions || summary, actionColors);
  makeGroup('Who',    summary.who,    whoColors,    '#64748b');
  makeGroup('Status', summary.status, statusColors, '#94a3b8');

  document.getElementById('resCard').style.display = 'block';
  // Show processing time
  const elapsed = ((performance.now() - _runStart) / 1000);
  const timeStr = elapsed < 60
    ? elapsed.toFixed(1) + 's'
    : Math.floor(elapsed/60) + 'm ' + (elapsed%60).toFixed(0) + 's';
  const rt = document.getElementById('resTime');
  if (rt) { rt.textContent = '⏱ ' + timeStr; rt.style.display = 'block'; }
}

// ── Run — ticker API (supports multiple tickers) ─────────────
async function run() {
  if (!selectedTickers.length) return;
  const btn = document.getElementById('btnRun');
  const spin= document.getElementById('spin');
  const txt = document.getElementById('btnTxt');
  btn.disabled = true; spin.style.display = 'block';

  // Single ticker — standard path
  if (selectedTickers.length === 1) {
    const ticker = selectedTickers[0];
    txt.textContent = `Processing ${ticker}…`;
    const timer = startProgress(`Fetching ${ticker} from API…`);
    try {
      const fd = buildColMap();
      fd.append('ticker', ticker);
      const resp = await fetch('/process', {method:'POST', body:fd});
      stopProgress(timer);
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({error: `HTTP ${resp.status}`}));
        throw new Error(e.error || 'Server error');
      }
      const summary  = JSON.parse(resp.headers.get('X-Summary')   || '{}');
      const rowCount = parseInt(resp.headers.get('X-Row-Count')   || '0');
      showResults(summary, rowCount, await resp.blob(), ticker + '_vista.xlsx');
    } catch(e) {
      stopProgress(timer);
      showError(e.message);
    }
  } else {
    // Multiple tickers — fetch sequentially, merge results
    txt.textContent = `Processing ${selectedTickers.length} tickers…`;
    const timer = startProgress(`Fetching ${selectedTickers.length} tickers…`);
    try {
      const fd = buildColMap();
      fd.append('tickers', selectedTickers.join(','));
      const resp = await fetch('/process_multi', {method:'POST', body:fd});
      stopProgress(timer);
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({error: `HTTP ${resp.status}`}));
        throw new Error(e.error || 'Server error');
      }
      const summary  = JSON.parse(resp.headers.get('X-Summary')   || '{}');
      const rowCount = parseInt(resp.headers.get('X-Row-Count')   || '0');
      showResults(summary, rowCount, await resp.blob(),
                  selectedTickers.join('_') + '_vista.xlsx');
    } catch(e) {
      stopProgress(timer);
      showError(e.message);
    }
  }

  btn.disabled = false; spin.style.display = 'none';
  txt.textContent = '⚡ Fetch & Process';
}

// ── Run — file upload ─────────────────────────────────────────
async function runFile() {
  if (!selectedFile) return;
  const btn = document.getElementById('btnRunFile');
  const spin= document.getElementById('spinFile');
  const txt = document.getElementById('btnTxtFile');
  btn.disabled = true; spin.style.display = 'block'; txt.textContent = 'Processing…';
  const timer = startProgress('Applying VISTA logic…');
  try {
    const fd = buildColMap();
    fd.append('file', selectedFile);
    const resp = await fetch('/process_file', {method:'POST', body:fd});
    stopProgress(timer);
    if (!resp.ok) { const e = await resp.json(); throw new Error(e.error || 'Server error'); }
    const summary  = JSON.parse(resp.headers.get('X-Summary')   || '{}');
    const rowCount = parseInt(resp.headers.get('X-Row-Count')   || '0');
    showResults(summary, rowCount, await resp.blob(),
                selectedFile.name.replace('.xlsx','').replace('.xls','') + '_vista.xlsx');
  } catch(e) {
    stopProgress(timer);
    showError(e.message);
  }
  btn.disabled = false; spin.style.display = 'none'; txt.textContent = '⚡ Process File';
}

// ── Download ──────────────────────────────────────────────────
function dl() {
  if (!resultBlob) return;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(resultBlob);
  a.download = dlFilename;
  a.click();
  URL.revokeObjectURL(a.href);
}
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════
#  §9  RULES EDITOR HTML PAGE
# ══════════════════════════════════════════════════════════════════

RULES_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VISTA — Edit Decision Rules</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Outfit:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#07090f;--s1:#0d1117;--s2:#111827;--s3:#161f30;--b1:#1c2a42;--b2:#243554;
  --tx:#b8cce4;--tx2:#6a84a8;--tx3:#e8f1ff;--ac:#2563eb;--gr:#10b981;--rd:#ef4444;}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--tx);font-size:12px;min-height:100vh}
body::before{content:'';position:fixed;inset:0;
  background-image:radial-gradient(circle at 20% 20%,rgba(37,99,235,.07) 0,transparent 50%),
  linear-gradient(rgba(37,99,235,.025) 1px,transparent 1px),
  linear-gradient(90deg,rgba(37,99,235,.025) 1px,transparent 1px);
  background-size:auto,48px 48px,48px 48px;pointer-events:none;z-index:0}
.shell{display:grid;grid-template-columns:220px 1fr;min-height:100vh;position:relative;z-index:1}
.sidebar{background:var(--s1);border-right:1px solid var(--b1);padding:0;position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column}
.sb-logo{padding:18px 16px 14px;border-bottom:1px solid var(--b1);display:flex;align-items:center;gap:9px}
.sb-logo-icon{width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,var(--ac),#06b6d4);display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
.sb-logo-text{font-size:13px;font-weight:700;color:var(--tx3)}
.sb-logo-ver{font-family:'JetBrains Mono',monospace;font-size:9px;color:#06b6d4}
.sb-nav{padding:10px 8px;flex:1}
.sb-link{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:7px;cursor:pointer;color:var(--tx);font-size:13px;font-weight:500;transition:all .15s;border:none;background:none;width:100%;text-align:left;text-decoration:none}
.sb-link:hover{background:var(--s2);color:var(--tx3)}
.sb-divider{height:1px;background:var(--b1);margin:6px 8px}
.main{display:flex;flex-direction:column}
.topbar{background:rgba(13,17,23,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--b1);padding:14px 26px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:50}
.topbar-title{font-size:15px;font-weight:700;color:var(--tx3)}
.content{padding:22px 26px;flex:1}
.page-head{margin-bottom:20px}
.page-head h2{font-size:19px;font-weight:800;color:var(--tx3);letter-spacing:-.02em}
.page-head p{font-size:12px;color:var(--tx2);margin-top:4px}
.card{background:var(--s1);border:1px solid var(--b1);border-radius:10px;overflow:hidden;margin-bottom:12px}
.card-head{background:var(--s2);border-bottom:1px solid var(--b1);padding:11px 16px;display:flex;align-items:center;justify-content:space-between}
.card-head-left{display:flex;align-items:center;gap:8px}
.card-head-icon{width:24px;height:24px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0}
.card-head-title{font-size:13px;font-weight:700;color:var(--tx3)}
.card-head-sub{font-size:10px;color:var(--tx2);margin-top:1px}
.card-body{padding:16px}
.match-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.match-field label{font-size:10px;color:var(--tx2);font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.07em;display:block;margin-bottom:4px}
.match-field input{width:100%;background:var(--s2);border:1px solid var(--b1);border-radius:6px;padding:7px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--tx3)}
.match-field input:focus{outline:none;border-color:var(--ac)}
.match-field .help{font-size:9px;color:var(--tx2);margin-top:3px;line-height:1.4}
.rules-table{width:100%;border-collapse:collapse}
.rules-table .th-row th{padding:6px 10px;font-size:9px;font-weight:600;color:var(--tx2);text-transform:uppercase;letter-spacing:.07em;text-align:left;border-bottom:1px solid var(--b1);background:var(--s3)}
.rules-table .sec-label td{background:rgba(255,255,255,.02);font-size:9px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:.07em;padding:4px 10px;border-bottom:1px solid var(--b1)}
.rules-table tr.rule-row{border-bottom:1px solid var(--b1)}
.rules-table tr.rule-row:last-child{border-bottom:none}
.rules-table tr.rule-row:hover td{background:rgba(255,255,255,.01)}
.rules-table td{padding:7px 10px;vertical-align:middle;font-size:11px;color:var(--tx)}
.rules-table td:not(:last-child){border-right:1px solid var(--b1)}
.rule-desc{color:var(--tx2);font-size:10px;line-height:1.4}
.rule-desc strong{color:var(--tx3)}
select,input[type=text]{background:var(--s2);border:1px solid var(--b1);border-radius:5px;padding:5px 8px;font-size:11px;color:var(--tx3);font-family:'Outfit',sans-serif;transition:border-color .15s;width:100%}
select:focus,input[type=text]:focus{outline:none;border-color:var(--ac)}
.action-sel{min-width:140px}.error-sel{min-width:80px}.who-sel{min-width:80px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:9px 18px;border-radius:7px;font-family:'Outfit',sans-serif;font-size:13px;font-weight:700;border:none;cursor:pointer;transition:all .2s}
.btn-save{background:linear-gradient(135deg,var(--gr),#059669);color:#fff;width:100%;margin-top:12px}
.btn-save:hover{transform:translateY(-1px);box-shadow:0 5px 18px rgba(16,185,129,.4)}
.btn-reset{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.3);font-size:12px;padding:5px 12px}
.btn-back{background:rgba(37,99,235,.15);color:#93c5fd;border:1px solid rgba(37,99,235,.3);font-size:12px;padding:5px 12px}
.alert{padding:9px 12px;border-radius:7px;font-size:12px;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.alert-ok{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);color:#6ee7b7}
.sec-a td{border-left:3px solid #10b981}.sec-b td{border-left:3px solid #1d4ed8}
.sec-c td{border-left:3px solid #dc2626}.sec-d td{border-left:3px solid #1d4ed8}
.sec-e td{border-left:3px solid #f97316}.sec-f td{border-left:3px solid #be185d}
::-webkit-scrollbar{width:5px;height:5px}::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--b2);border-radius:3px}
</style>
</head>
<body>
<div class="shell">
<nav class="sidebar">
  <div class="sb-logo">
    <div class="sb-logo-icon">⚡</div>
    <div><div class="sb-logo-text">VISTA</div><div class="sb-logo-ver">Rules Editor</div></div>
  </div>
  <div class="sb-nav">
    <a href="/" class="sb-link">← Back to Main</a>
    <div class="sb-divider"></div>
    <a href="/rules/history" class="sb-link">📋 Rule Change History</a>
  </div>
</nav>
<div class="main">
  <div class="topbar">
    <div><div class="topbar-title">Edit Decision Rules</div></div>
    <div style="display:flex;gap:8px">
      <form method="POST" action="/rules/reset" style="margin:0">
        <button type="submit" class="btn btn-reset"
          onclick="return confirm('Reset all rules to defaults?')">↺ Reset Defaults</button>
      </form>
    </div>
  </div>
  <div class="content">
    <div class="page-head">
      <h2>Decision Rules</h2>
      <p>Adjust the action, error level, and who handles each condition. Changes are saved to rules.json.</p>
    </div>
    {% if saved %}
    <div class="alert alert-ok">✓ Rules saved successfully.</div>
    {% endif %}
    <form method="POST" action="/rules">
    <div class="card">
      <div class="card-head">
        <div class="card-head-left">
          <div class="card-head-icon" style="background:rgba(37,99,235,.15)">⚙</div>
          <div><div class="card-head-title">Matching Thresholds</div>
          <div class="card-head-sub">Core numeric parameters</div></div>
        </div>
      </div>
      <div class="card-body">
        <div class="match-grid">
          <div class="match-field">
            <label>Strict Tolerance</label>
            <input type="text" name="strict_tolerance" value="{{ rules.matching.strict_tolerance }}" placeholder="0.01">
            <div class="help">Exact match: |a−b| ≤ this value (default 0.01)</div>
          </div>
          <div class="match-field">
            <label>Broker Min Model Match</label>
            <input type="text" name="broker_min_model_match" value="{{ rules.matching.broker_min_model_match }}" placeholder="2">
            <div class="help">Min MMC for Broker to auto-verify calculated values</div>
          </div>
          <div class="match-field">
            <label>Raw Unit Ratio</label>
            <input type="text" name="raw_unit_ratio" value="{{ rules.matching.raw_unit_ratio }}" placeholder="500">
            <div class="help">If |8K÷Con| &gt; this → divide 8K by 1,000</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-head-left">
          <div class="card-head-icon" style="background:rgba(16,185,129,.15)">🌳</div>
          <div><div class="card-head-title">Section Rules</div>
          <div class="card-head-sub">Action · Error Chance · Who for every decision path</div></div>
        </div>
      </div>
      <div class="card-body" style="padding:0">
        <table class="rules-table">
          <thead class="th-row"><tr>
            <th style="width:40%">Rule / Condition</th>
            <th>Action</th><th>Error</th><th>Who</th>
          </tr></thead>
          <tbody>
          {% for group in rule_groups %}
            <tr class="sec-label {{ group.cls }}"><td colspan="4">{{ group.label }}</td></tr>
            {% for rule in group.rules %}
            <tr class="rule-row {{ group.cls }}">
              <td><div class="rule-desc"><strong>{{ rule.title }}</strong><br>{{ rule.desc }}</div></td>
              <td>
                <select name="{{ rule.key }}_action" class="action-sel">
                  {% for opt in actions %}
                  <option value="{{ opt }}" {% if rules.sections[rule.key].action == opt %}selected{% endif %}>{{ opt }}</option>
                  {% endfor %}
                </select>
              </td>
              <td>
                <select name="{{ rule.key }}_error" class="error-sel">
                  {% for opt in ['Low','Medium','High'] %}
                  <option value="{{ opt }}" {% if rules.sections[rule.key].error == opt %}selected{% endif %}>{{ opt }}</option>
                  {% endfor %}
                </select>
              </td>
              <td>
                <select name="{{ rule.key }}_who" class="who-sel">
                  <option value="System" {% if rules.sections[rule.key].who == 'System' %}selected{% endif %}>System</option>
                  <option value="Human"  {% if rules.sections[rule.key].who == 'Human'  %}selected{% endif %}>Human</option>
                </select>
              </td>
            </tr>
            {% endfor %}
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    <button type="submit" class="btn btn-save">💾  Save Rules</button>
    </form>
  </div>
</div>
</div>
</body>
</html>"""

HISTORY_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VISTA — Rule History</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Outfit:wght@400;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#07090f;--s1:#0d1117;--s2:#111827;--b1:#1c2a42;--tx:#b8cce4;--tx2:#6a84a8;--tx3:#e8f1ff;}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--tx);font-size:12px;min-height:100vh;padding:22px}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
h2{font-size:18px;font-weight:700;color:var(--tx3)}
a.back{color:#93c5fd;font-size:12px;text-decoration:none;background:rgba(37,99,235,.15);
  border:1px solid rgba(37,99,235,.3);padding:5px 12px;border-radius:6px}
.card{background:var(--s1);border:1px solid var(--b1);border-radius:10px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:7px 12px;font-size:9px;font-weight:600;color:var(--tx2);text-transform:uppercase;
  letter-spacing:.07em;text-align:left;border-bottom:1px solid var(--b1);background:var(--s2)}
td{padding:8px 12px;border-bottom:1px solid var(--b1);font-size:11px;color:var(--tx);vertical-align:top}
tr:last-child td{border-bottom:none}
.mono{font-family:'JetBrains Mono',monospace;font-size:10px;color:#93c5fd}
.old{color:#f87171}.new{color:#6ee7b7}
.empty{padding:36px;text-align:center;color:var(--tx2);font-size:13px}
</style>
</head>
<body>
<div class="topbar"><h2>Rule Change History</h2><a href="/rules" class="back">← Back to Rules</a></div>
<div class="card">
{% if history %}
<table>
  <thead><tr><th>When</th><th>Key</th><th>Field</th><th>Before</th><th>After</th></tr></thead>
  <tbody>
  {% for h in history|reverse %}
  <tr><td class="mono">{{ h.ts }}</td><td class="mono">{{ h.key }}</td>
      <td>{{ h.field }}</td><td class="old">{{ h.old }}</td><td class="new">{{ h.new }}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<div class="empty">No rule changes recorded yet.</div>
{% endif %}
</div>
</body>
</html>"""



# ══════════════════════════════════════════════════════════════════
#  §10b  DOWNLOAD HISTORY  (server-side store + re-download)
# ══════════════════════════════════════════════════════════════════

import uuid as _uuid

DOWNLOAD_HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_history.json")
DOWNLOAD_STORE_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_store")


def load_download_history() -> list:
    try:
        if os.path.exists(DOWNLOAD_HISTORY_FILE):
            with open(DOWNLOAD_HISTORY_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_download_history(history: list):
    try:
        with open(DOWNLOAD_HISTORY_FILE, "w") as f:
            json.dump(history[-200:], f, indent=2)
    except Exception:
        pass


def record_download(label: str, summary: dict, row_count: int, file_id: str):
    entry = {"id": file_id, "label": label,
             "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "rows": row_count, "summary": summary}
    history = load_download_history()
    history.append(entry)
    save_download_history(history)


def store_output(file_id: str, out_bytes: bytes):
    os.makedirs(DOWNLOAD_STORE_DIR, exist_ok=True)
    with open(os.path.join(DOWNLOAD_STORE_DIR, f"{file_id}.xlsx"), "wb") as f:
        f.write(out_bytes)


def get_stored_output(file_id: str):
    path = os.path.join(DOWNLOAD_STORE_DIR, f"{file_id}.xlsx")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


DOWNLOADS_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VISTA — Download History</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#07090f;--s1:#0d1117;--s2:#111827;--s3:#161f30;--b1:#1c2a42;
  --tx:#b8cce4;--tx2:#6a84a8;--tx3:#e8f1ff;--ac:#2563eb;--gr:#10b981;}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--tx);
  font-size:12px;min-height:100vh;padding:24px 28px}
body::before{content:'';position:fixed;inset:0;
  background-image:radial-gradient(circle at 20% 20%,rgba(37,99,235,.07) 0,transparent 50%),
  linear-gradient(rgba(37,99,235,.025) 1px,transparent 1px),
  linear-gradient(90deg,rgba(37,99,235,.025) 1px,transparent 1px);
  background-size:auto,48px 48px,48px 48px;pointer-events:none;z-index:0}
.wrap{position:relative;z-index:1;max-width:1100px;margin:0 auto}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}
.topbar-left h2{font-size:20px;font-weight:800;color:var(--tx3);letter-spacing:-.02em}
.topbar-left p{font-size:12px;color:var(--tx2);margin-top:3px}
a.btn-back{color:#93c5fd;font-size:12px;text-decoration:none;
  background:rgba(37,99,235,.15);border:1px solid rgba(37,99,235,.3);
  padding:6px 14px;border-radius:6px;font-weight:600}
a.btn-back:hover{background:rgba(37,99,235,.25)}
.card{background:var(--s1);border:1px solid var(--b1);border-radius:10px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:9px 14px;font-size:9px;font-weight:600;color:var(--tx2);text-transform:uppercase;
  letter-spacing:.07em;text-align:left;border-bottom:1px solid var(--b1);background:var(--s2)}
td{padding:11px 14px;border-bottom:1px solid var(--b1);font-size:11px;
  color:var(--tx);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.012)}
.mono{font-family:'JetBrains Mono',monospace;font-size:10px;color:#93c5fd}
.label-cell{font-weight:600;color:var(--tx3);font-size:12px}
.summary{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px}
.chip-ok  {background:rgba(16,185,129,.15);color:#6ee7b7}
.chip-push{background:rgba(29,78,216,.15);color:#93c5fd}
.chip-rev {background:rgba(239,68,68,.15);color:#fca5a5}
.chip-esc {background:rgba(190,24,93,.15);color:#f9a8d4}
.chip-unk {background:rgba(100,116,139,.15);color:#94a3b8}
.rows-badge{font-family:'JetBrains Mono',monospace;font-size:10px;
  background:var(--s2);border:1px solid var(--b1);padding:3px 8px;border-radius:4px;color:var(--tx2)}
.dl-btn{display:inline-flex;align-items:center;gap:5px;padding:6px 13px;border-radius:6px;
  font-size:11px;font-weight:700;text-decoration:none;
  background:rgba(16,185,129,.12);color:#6ee7b7;border:1px solid rgba(16,185,129,.3);transition:all .15s}
.dl-btn:hover{background:rgba(16,185,129,.25)}
.empty{padding:52px;text-align:center;color:var(--tx2);font-size:13px}
.empty-icon{font-size:36px;display:block;margin-bottom:12px}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--b1);border-radius:3px}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div class="topbar-left">
      <h2>⬇ Download History</h2>
      <p>All processed files stored on server — click any row to re-download</p>
    </div>
    <a href="/" class="btn-back">← Back to VISTA</a>
  </div>
  <div class="card">
    {% if history %}
    <table>
      <thead><tr>
        <th style="width:150px">When</th>
        <th>Label / Source</th>
        <th style="width:90px">Rows</th>
        <th>Action Summary</th>
        <th style="width:110px">Re-download</th>
      </tr></thead>
      <tbody>
      {% for h in history|reverse %}
      <tr>
        <td class="mono">{{ h.ts }}</td>
        <td class="label-cell">{{ h.label }}</td>
        <td><span class="rows-badge">{{ "{:,}".format(h.rows) }}</span></td>
        <td><div class="summary">
          {% for action, count in h.summary.items()|sort %}
            {% if   action == 'No Action' %}<span class="chip chip-ok">No Action {{ count }}</span>
            {% elif action == 'Push'      %}<span class="chip chip-push">Push {{ count }}</span>
            {% elif action == 'Review'    %}<span class="chip chip-rev">Review {{ count }}</span>
            {% elif action == 'Escalate'  %}<span class="chip chip-esc">Escalate {{ count }}</span>
            {% else %}<span class="chip chip-unk">{{ action }} {{ count }}</span>
            {% endif %}
          {% endfor %}
        </div></td>
        <td><a class="dl-btn" href="/downloads/{{ h.id }}">⬇ Download</a></td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="empty">
      <span class="empty-icon">📭</span>
      No processed files yet — run a ticker or upload a file first.
    </div>
    {% endif %}
  </div>
</div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════
#  §10 RULE GROUPS & ALL_ACTIONS  (editor UI data)
# ══════════════════════════════════════════════════════════════════

RULE_GROUPS = [
    {"cls":"sec-a", "label":"Entry Gates (run before all sections)", "rules":[
        {"key":"calc_no_va",        "title":"Revised=Calculated, no VA",           "desc":"Source is calculated, no VA to verify against, Broker confirms"},
        {"key":"calc_va_mismatch",  "title":"Revised=Calculated, VA mismatch",     "desc":"Calculated value conflicts with VA Filing"},
    ]},
    {"cls":"sec-b", "label":"Section B — Push", "rules":[
        {"key":"B0_broker",         "title":"B0 — Mode valid, ≥1 broker match, diff ≤threshold", "desc":"Mode correct, Con wrong, broker corroborates"},
        {"key":"B0_large_diff",     "title":"B0 — Mode valid, diff >threshold",   "desc":"Mode clearly differs from Con by more than threshold"},
        {"key":"B0_va_broker_only", "title":"B0 — Mode=[VA,Broker] no EF",        "desc":"Mode has no filing source, lower confidence"},
        {"key":"B0_no_broker",      "title":"B0 — Mode valid, 0 broker match",    "desc":"Mode valid but no broker corroboration"},
        {"key":"B1_broker",         "title":"B1 — VA missing, EF+Broker agree",   "desc":"EF and Broker agree, broker corroborates"},
        {"key":"B1_large_diff",     "title":"B1/B2 — Large diff >threshold",      "desc":"EF value differs greatly from Con"},
        {"key":"B1_no_broker",      "title":"B1 — VA missing, EF+Broker, 0 MMC", "desc":"EF and Broker agree but no model match count"},
        {"key":"B2_broker",         "title":"B2 — VA missing, EF only, ≥1 match", "desc":"Only EF available, broker corroborates"},
        {"key":"B2_no_broker",      "title":"B2 — VA missing, EF only, 0 match",  "desc":"Only EF, no broker corroboration, Con≈EF after round-off"},
        {"key":"B2_con_ne_ef",      "title":"B2 — Con≠EF after round-off",        "desc":"0 broker, Con doesn't match EF even approximately"},
        {"key":"B3_ge2_match",      "title":"B3 — Broker sole, ≥2 MMC, Con≈Broker","desc":"Broker sole source, high model match, Con≈Broker"},
        {"key":"B3_con_ne_broker",  "title":"B3 — Broker sole, Con≠Broker",       "desc":"≥2 model match but Con doesn't match Broker value"},
        {"key":"B3_mismatch",       "title":"B3 — Broker sole, <min MMC",         "desc":"Broker sole, insufficient model count"},
        {"key":"B4",                "title":"B4 — 8K = 10K intra-match",          "desc":"8K and 10K agree with each other"},
        {"key":"B5_broker",         "title":"B5 — Blank consensus, ≥1 broker",   "desc":"Con blank, broker corroborates source value"},
        {"key":"B5_no_broker",      "title":"B5 — Blank consensus, 0 broker",    "desc":"Con blank, no broker corroboration"},
    ]},
    {"cls":"sec-c", "label":"Section C — Review", "rules":[
        {"key":"C1_broker",         "title":"C1 — VA isolated, broker present",   "desc":"VA doesn't match EF/Broker, broker partially corroborates"},
        {"key":"C1_no_broker",      "title":"C1 — VA isolated, no broker",        "desc":"VA is only source, no corroboration"},
        {"key":"C2",                "title":"C2 — 3-way mismatch",               "desc":"VA, EF, and Broker all disagree"},
        {"key":"C3",                "title":"C3 — EF intra-conflict (8K≠10K)",   "desc":"8K and 10K filing values contradict"},
        {"key":"C4",                "title":"C4 — All sources blank / unverifiable","desc":"No VA, no EF, no Broker"},
    ]},
    {"cls":"sec-d", "label":"Section D — Push Rectification", "rules":[
        {"key":"D1_broker",         "title":"D1 — Con≠VA, VA+EF agree, ≥1 broker","desc":"VA and EF agree on a different value, broker confirms"},
        {"key":"D1_no_broker",      "title":"D1 — Con≠VA, VA+EF agree, 0 broker", "desc":"VA and EF agree but no broker corroboration"},
        {"key":"D2_broker",         "title":"D2 — Con≠EF, VA missing, EF+Broker", "desc":"EF and Broker agree on correction, no VA"},
        {"key":"D2_no_broker",      "title":"D2 — Con≠EF, VA missing, 0 broker",  "desc":"EF and Broker agree but no model match"},
        {"key":"D3_broker",         "title":"D3 — Con≠VA, VA+Broker, ≥1",        "desc":"VA and Broker agree, no EF, broker confirms"},
        {"key":"D3_no_broker",      "title":"D3 — Con≠VA, VA+Broker, 0",         "desc":"VA and Broker agree but no model match"},
        {"key":"D4",                "title":"D4 — Broker only, Con suspect",      "desc":"Only Broker available, Con doesn't match"},
        {"key":"D5",                "title":"D5 — No structured source",          "desc":"No VA, EF, or Broker available"},
    ]},
    {"cls":"sec-e", "label":"Section E — EF-only / Broker-only", "rules":[
        {"key":"E1_no_broker",      "title":"E1 — Con=EF, no VA, no Broker",      "desc":"Con matches EF and that's the only source"},
        {"key":"E1_with_broker",    "title":"E1 — Con=EF, no VA, has Broker",     "desc":"Con matches EF but Broker also present"},
        {"key":"E2",                "title":"E2 — Con=Broker exactly, no VA/EF",  "desc":"Con matches Broker and no other sources exist"},
        {"key":"E3",                "title":"E3 — Con=Broker but EF≠Con",         "desc":"Con=Broker but EF disagrees — EF is primary filing"},
    ]},
    {"cls":"sec-f", "label":"Section F — Escalation", "rules":[
        {"key":"F2",                "title":"F2 — VA conflict, Revised=Calculated","desc":"VA≠Con but Con=Broker AND Revised Source is Calculated"},
        {"key":"fallback_calc",     "title":"Fallback — Revised=Calculated",       "desc":"Catch-all for Calculated rows that don't match any section"},
        {"key":"fallback_other",    "title":"Fallback — Other source",             "desc":"Catch-all for non-Calculated rows"},
    ]},
]

ALL_ACTIONS = ["No Action", "Push", "Review", "Escalate"]

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules_history.json")

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []

def append_history(changes):
    h = load_history()
    h.extend(changes)
    h = h[-500:]
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(h, f, indent=2)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  §11 FLASK ROUTES
# ══════════════════════════════════════════════════════════════════



def _col_map_from_request() -> dict:
    """Build column name overrides dict from form fields."""
    return {
        "Con_num":         request.form.get("Con_num",         "Con_num"),
        "IndStd Filling":      request.form.get("IndStd Filling",      "IndStd Filling"),  # also accepts "VA Filling"
        "10K":             request.form.get("10K",             "10K"),
        "8K":              request.form.get("8K",              "8K"),
        "Broker Mode":     request.form.get("Broker Mode",     "Broker Mode"),
        "ModelmatchCount": request.form.get("ModelmatchCount", "ModelmatchCount"),
        "Source Derived":  request.form.get("Source Derived",  "Source Derived"),
        "Revised Source":     request.form.get("Revised Source",     "Revised Source"),
        "webnumberformat":    request.form.get("webnumberformat",     "webnumberformat"),
    }


def _send_excel(out_bytes: bytes, summary: dict, total_rows: int,
                label: str = "output", summary_flat: dict = None) -> object:
    file_id = _uuid.uuid4().hex
    store_output(file_id, out_bytes)
    # Use flat dict for history chips; full summary for response header
    _hist_summary = summary_flat if summary_flat else (summary.get("actions", summary))
    record_download(label, _hist_summary, total_rows, file_id)
    resp = send_file(
        io.BytesIO(out_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=False,
    )
    resp.headers["X-Summary"]   = json.dumps(summary if isinstance(summary, dict) and "actions" in summary else {"actions": summary})
    resp.headers["X-Row-Count"] = str(total_rows)
    resp.headers["X-File-ID"]   = file_id
    resp.headers["Access-Control-Expose-Headers"] = "X-Summary, X-Row-Count, X-File-ID"
    return resp


@app.route("/")
def index():
    """Serve main UI. Ticker list populated if DB is reachable."""
    return render_template_string(PAGE, tickers=_ticker_list)


@app.route("/process", methods=["POST"])
def process_ticker():
    """Fetch ticker data from API and apply VISTA logic."""
    print("Flask /process route called") 
    print(request.form)
    ticker = (request.form.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"error": "No ticker selected"}), 400
    try:
        records = fetch_ticker_data(ticker)
        if not records:
            return jsonify({"error": f"API returned no data for {ticker}"}), 400
        out_bytes, summary, total_rows, summary_flat = process_api_records(records, _col_map_from_request())
        resp = _send_excel(out_bytes, summary, total_rows, summary_flat=summary_flat, label=f"{ticker} (API)")
        resp.headers["X-Ticker"] = ticker
        resp.headers["Access-Control-Expose-Headers"] += ", X-Ticker"
        return resp
    except (ConnectionError, TimeoutError, PermissionError, RuntimeError, ValueError) as e:
        # Known API errors — return clean message, no stack trace needed
        return jsonify({"error": str(e), "source": "api"}), 502
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(), "source": "vista"}), 500
def process_multi():
    """Accept comma-separated tickers, fetch each, merge and apply VISTA logic."""
    tickers_raw = (request.form.get("tickers") or "").strip()
    if not tickers_raw:
        return jsonify({"error": "No tickers provided"}), 400
    ticker_list = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
    try:
        all_records = []
        for ticker in ticker_list:
            records = fetch_ticker_data(ticker)
            all_records.extend(records)
        if not all_records:
            return jsonify({"error": "API returned no data for any ticker"}), 400
        out_bytes, summary, total_rows, summary_flat = process_api_records(all_records, _col_map_from_request())
        label = ",".join(ticker_list) + " (API multi)"
        resp = _send_excel(out_bytes, summary, total_rows, summary_flat=summary_flat, label=label)
        resp.headers["X-Tickers"] = ",".join(ticker_list)
        resp.headers["Access-Control-Expose-Headers"] += ", X-Tickers"
        return resp
    except (ConnectionError, TimeoutError, PermissionError, RuntimeError, ValueError) as e:
        return jsonify({"error": str(e), "source": "api"}), 502
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(), "source": "vista"}), 500




@app.route("/process_file", methods=["POST"])
def process_file():
    """Accept an uploaded Excel file and apply VISTA logic."""
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "No file uploaded"}), 400
    try:
        file_bytes = uploaded.read()
        out_bytes, summary, total_rows, summary_flat = process_excel_bytes(file_bytes, _col_map_from_request())
        fname = uploaded.filename or "uploaded_file"
        return _send_excel(out_bytes, summary, total_rows, summary_flat=summary_flat, label=f"{fname} (upload)")
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/rules", methods=["GET"])
def rules_get():
    return render_template_string(
        RULES_PAGE, rules=load_rules(),
        rule_groups=RULE_GROUPS, actions=ALL_ACTIONS,
        saved=request.args.get("saved"), error=None,
    )


@app.route("/rules", methods=["POST"])
def rules_post():
    rules = load_rules()
    changes = []
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for key, cast in [("strict_tolerance", float),
                      ("broker_min_model_match", int),
                      ("raw_unit_ratio", float)]:
        val_str = request.form.get(key, "").strip()
        if val_str:
            try:
                val = cast(val_str)
                if rules["matching"].get(key) != val:
                    changes.append({"ts":ts,"key":f"matching.{key}","field":"value",
                                    "old":str(rules["matching"].get(key)),"new":str(val)})
                rules["matching"][key] = val
            except ValueError:
                pass

    for group in RULE_GROUPS:
        for rule in group["rules"]:
            k = rule["key"]
            for field in ["action","error","who"]:
                new_val = request.form.get(f"{k}_{field}", "").strip()
                if new_val:
                    old_val = rules["sections"][k][field]
                    if old_val != new_val:
                        changes.append({"ts":ts,"key":k,"field":field,"old":old_val,"new":new_val})
                    rules["sections"][k][field] = new_val

    save_rules(rules)
    if changes:
        append_history(changes)
    return redirect("/rules?saved=1")


@app.route("/rules/reset", methods=["POST"])
def rules_reset():
    if os.path.exists(RULES_FILE):
        os.remove(RULES_FILE)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_history([{"ts":ts,"key":"ALL","field":"reset","old":"custom","new":"defaults"}])
    return redirect("/rules?saved=1")


@app.route("/rules/history", methods=["GET"])
def rules_history():
    return render_template_string(HISTORY_PAGE, history=load_history())



@app.route("/downloads", methods=["GET"])
def downloads_page():
    """Show download history page."""
    return render_template_string(DOWNLOADS_PAGE, history=load_download_history())


@app.route("/downloads/<file_id>", methods=["GET"])
def redownload(file_id: str):
    """Re-download a previously processed file by its unique ID."""
    if not all(ch in "0123456789abcdef" for ch in file_id) or len(file_id) != 32:
        return jsonify({"error": "Invalid file ID"}), 400
    data = get_stored_output(file_id)
    if data is None:
        return jsonify({"error": "File not found — may have been cleared from server"}), 404
    return send_file(
        io.BytesIO(data),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"vista_{file_id[:8]}.xlsx",
    )


# ══════════════════════════════════════════════════════════════════
#  §12 ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import logging
    logging.basicConfig(level=logging.INFO)
    print()
    print("=" * 58)
    print("  VISTA — Verification & Integrated Systems for Trusted Analytics  v3.2")
    print(f"  ▶  Open browser: http://localhost:{port}")
    print(f"  DB / API available: {_db_available}")
    print(f"  Tickers loaded:     {len(_ticker_list)}")
    print("=" * 58)
    print()
    app.run(debug=False, host="0.0.0.0", port=port)