"""心情小語：時段判斷、讀寫小語與播放統計、洗牌輪播。"""

import random

from appconfig import APP_DIR, at_today, read_json, write_json
from default_quotes import DEFAULT_QUOTES

QUOTES_PATH = APP_DIR / "quotes.json"
STATS_PATH = APP_DIR / "stats.json"
PERIODS = ("morning", "noon", "afternoon")
PERIOD_NAMES = {"morning": "早上", "noon": "中午", "afternoon": "下午"}


def period_by_time(now, config):
    if now < at_today(now, config["lunch_start"]):
        return "morning"
    if now < at_today(now, config["lunch_end"]):
        return "noon"
    return "afternoon"


def period_of(now, config):
    """自動播放用的時段；週末或下班後回傳 None，不跳小語。"""
    if now.weekday() >= 5 or now >= at_today(now, config["end_time"]):
        return None
    return period_by_time(now, config)


def load_quotes():
    # 沒有 quotes.json 或某個時段格式不對，就用內建的預設小語
    data = read_json(QUOTES_PATH, {})
    if not isinstance(data, dict):
        data = {}
    quotes = {}
    for period in PERIODS:
        items = data.get(period)
        if isinstance(items, list):
            quotes[period] = [str(q).strip() for q in items if str(q).strip()]
        else:
            quotes[period] = list(DEFAULT_QUOTES[period])
    return quotes


def save_quotes(quotes):
    return write_json(QUOTES_PATH, quotes)


def load_stats():
    data = read_json(STATS_PATH, {})
    if not isinstance(data, dict):
        data = {}
    stats = {}
    for period in PERIODS:
        counts = data.get(period)
        stats[period] = {str(q): n for q, n in counts.items() if isinstance(n, int)} if isinstance(counts, dict) else {}
    return stats


def record_play(period, quote):
    stats = load_stats()
    stats[period][quote] = stats[period].get(quote, 0) + 1
    write_json(STATS_PATH, stats)


def clear_stats():
    return write_json(STATS_PATH, {period: {} for period in PERIODS})


class QuotePicker:
    """每個時段各自洗牌，整輪播完才重新洗牌，換輪時也不會連續重複同一句。"""

    def __init__(self, quotes):
        self.set_quotes(quotes)

    def set_quotes(self, quotes):
        self.quotes = quotes
        self.bags = {period: [] for period in PERIODS}
        self.last = {period: None for period in PERIODS}

    def pick(self, period):
        pool = self.quotes.get(period) or []
        if not pool:
            return None
        bag = self.bags[period]
        if not bag:
            bag.extend(pool)
            random.shuffle(bag)
            if len(bag) > 1 and bag[-1] == self.last[period]:
                bag[0], bag[-1] = bag[-1], bag[0]
        quote = bag.pop()
        self.last[period] = quote
        return quote
