import re
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
from bs4 import BeautifulSoup

from data.types import Source

__URL = "https://www.england.nhs.uk/statistics/statistical-work-areas/covid-19-vaccinations/"
__URL_REGEX = re.compile(
    r"https://www.england.nhs.uk/statistics/wp-content/uploads/sites"
    r"/\d/\d{4}/\d{2}/"
    r"COVID-19-([Dd]aily|weekly|total)-announced-vaccinations-(\d+-[a-zA-Z]+-\d+)(-\d+)?.xlsx"
)
__CACHE_DIR = Path("/tmp/vaxtldr")
__DATES_WITH_2ND_SHEET = {
    date(2021, 1, 12),
    date(2021, 1, 13),
    date(2021, 1, 14),
    date(2021, 1, 16),
}


def get_data_sources() -> Iterable[Source]:
    html = urllib.request.urlopen(__URL).read()
    urls = [
        tag["href"]
        for tag in BeautifulSoup(html, "html.parser").find_all()
        if tag.name == "a" and "announced vaccinations" in tag.text
    ]

    for url in urls:
        match = __URL_REGEX.match(url)
        if match is None:
            continue
        assert match, url
        period = match.group(1).lower()
        if period == "total":
            period = "weekly"
        data_date_str = match.group(2)
        data_date = datetime.strptime(data_date_str, "%d-%B-%Y").date()
        delay = timedelta(days=1 if period == "daily" else 4)
        yield Source(url=url, data_date=data_date, real_date=data_date - delay, period=period)


def get_sheet(source: Source) -> pd.DataFrame:
    if not __CACHE_DIR.is_dir():
        __CACHE_DIR.mkdir(parents=True)
    name = source.url.split("/")[-1]
    cache_file = __CACHE_DIR / name
    if not cache_file.is_file():
        sheet_data = urllib.request.urlopen(source.url).read()
        cache_file.write_bytes(sheet_data)
    else:
        sheet_data = cache_file.read_bytes()

    sheet_number = 0
    if source.data_date in __DATES_WITH_2ND_SHEET:
        sheet_number = 1
    if source.period == "weekly":
        sheet_number = 1
    return pd.read_excel(sheet_data, sheet_name=sheet_number)
