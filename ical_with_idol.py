import calendar
from datetime import date, datetime, timedelta
import re

from bs4 import BeautifulSoup as bs
import chromedriver_binary
from icalendar import Calendar, Event
import pytz
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


BASE_URL = 'https://cynhn.com'
CAL_URL = f'{BASE_URL}/calendar'
DATE_PAT = re.compile(r'(?P<date>[\d\.]+)')
RADIO_SUMMARY = 'FM-FUJI「GIRLS♥GIRLS♥GIRLS =flying high= CYNHNの歌いまスウィーニー」'
RADIO_CATEGORY = 'MEDIA'
RADIO_URL = f'{BASE_URL}/contents/289980'
RADIO_DESCRIPTION = (
    f'{RADIO_URL}\n'
    '毎週木曜 23:30～24:00（2018年4月5日より）\n'
    '出演：CYNHN（スウィーニー）\n'
    '▼メッセージ受付はこちら！\n'
    'cynhn@fmfuji.jp'
)
JST = pytz.timezone('Asia/Tokyo')
PATS = [
    re.compile(r'OPEN (?P<open>[:\d]+)'),
    re.compile(r'開場 (?P<open>[\d]+:[\d]+) / 開演 (?P<start>[\d]+:[\d]+)'),
    re.compile(r'開場(?P<open>[\d]+:[\d]+)/開演(?P<start>[\d]+:[\d]+)'),
    re.compile(r'開場/開演：(?P<open>[\d]+:[\d]+)/(?P<start>[\d]+:[\d]+)'),
    re.compile(r'OPEN START：(?P<open>[\d:]+) / (?P<start>[\d:]+)'),
]
START_PAT = re.compile(r'(?P<start>[\d]+:[\d]*)頃〜')


def ayase_shiki_noten(date_dt):
    dtstart = datetime(
        date_dt.year,
        date_dt.month,
        date_dt.day,
        12,
        00,
        tzinfo=JST,
    )
    dtend = dtstart + timedelta(hours=6, minutes=00)
    return dtstart, dtend


def init_driver() -> webdriver.Chrome:
    options = Options()
    driver = webdriver.Chrome(options=options)
    return driver


def get_source(driver):
    driver.implicitly_wait(2)
    driver.get(CAL_URL)
    return driver.page_source


def get_soup(html):
    return bs(html, 'html.parser')


def get_content_hrefs(source):
    soup = get_soup(source)
    div = soup.find('div', class_='details corner-details')
    anchors = div.find_all('a')
    hrefs = []
    for anchor in anchors:
        href = anchor['href']
        if href != '/vertical_calendar':
            hrefs.append(anchor['href'])
    return hrefs


def is_radio(summary):
    return 'FM-FUJI' in summary


def get_description(content_href, soup):
    body = soup.find('div', class_='body')
    paragraph = ''
    paragraph += f'{BASE_URL}/{content_href}\n'
    for p in body.find_all('p'):
        paragraph += f'{p.text}\n'
    paragraph = paragraph.replace(u'\xa0', ' ')
    return paragraph


def parse_open_time(description):
    g = START_PAT.search(description)
    start_time = ''
    if g:
        start_time = g['start']
    else:
        for pat in PATS:
            g = pat.search(description)
            if g:
                start_time = g['open']
                break
    if g:
        print(start_time)
        hour = start_time.split(':')[0]
        minutes = start_time.split(':')[1]
        return int(hour), int(minutes)
    return 0, 0


def make_event(ical, content_href):
    res = requests.get(f'{BASE_URL}/{content_href}')
    soup = get_soup(res.content)
    summary = soup.find('h2', class_='title').text
    category = soup.find('p', class_='tag').text
    date_raw = soup.find('p', class_='date').text
    description = get_description(content_href, soup)
    g = DATE_PAT.search(date_raw)
    date_dt = datetime.strptime(g['date'], '%Y.%m.%d')
    hour, minutes = parse_open_time(description)
    dtstart = datetime(
        date_dt.year,
        date_dt.month,
        date_dt.day,
        hour,
        minutes,
        tzinfo=JST,
    )
    dtend = dtstart + timedelta(hours=2, minutes=30)
    # 綾瀬志希展対応
    if '綾瀬志希展〜脳〜' in summary:
        dtstart, dtend = ayase_shiki_noten(date_dt)
    event = Event()
    summaries = [
        subcomponent['summary'].encode('utf-8')
        for subcomponent in ical.subcomponents
    ]
    byted_summary = summary.encode('utf-8')
    if not is_radio(summary) and byted_summary not in summaries:
        print(g['date'], category, summary, dtstart, dtend)
        event.add('summary', summary)
        event.add('dtstart', dtstart)
        event.add('dtend', dtend)
        event.add('category', category)
        event.add('description', description)
        ical.add_component(event)


def add_radio_schedule(ical):
    today = date.today()
    cal = calendar.Calendar(today.year)
    weeks = cal.monthdays2calendar(today.year, today.month)
    radio_days = []
    for week in weeks:
        for day in week:
            if day[1] == 3 and day[0] > 0:
                dtstart = datetime(
                    today.year,
                    today.month,
                    day[0],
                    23,
                    30,
                    tzinfo=JST,
                )
                dtend = datetime(
                    today.year,
                    today.month,
                    day[0]+1,
                    0,
                    0,
                    tzinfo=JST,
                )
                radio_days.append((dtstart, dtend))
    for times in radio_days:
        event = Event()
        event.add('summary', RADIO_SUMMARY)
        event.add('dtstart', times[0])
        event.add('dtend', times[1])
        event.add('category', RADIO_CATEGORY)
        event.add('description', RADIO_DESCRIPTION)
        ical.add_component(event)


def main():
    driver = init_driver()
    source = get_source(driver)
    driver.close()
    driver.quit()

    ical = Calendar()
    content_hrefs = get_content_hrefs(source)
    for content_href in content_hrefs:
        make_event(ical, content_href)
    add_radio_schedule(ical)
    ical.add('version', '2.0')
    ical.add('prodid', '-//nao_y//CYNHN Unofficial Calendar//JP')
    with open('CYNHN_Unofficial_Calendar.ics', 'ab') as fout:
        fout.write(ical.to_ical())


if __name__ == '__main__':
    main()
