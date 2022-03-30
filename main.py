import requests
from datetime import date, time, datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import sys, traceback
import timeago
import os
import re

URL = 'https://vancouver.craigslist.org/jsonsearch/apa/'

CONFIG = {
    'hasPic' : 1,
    'min_price' : 2000,
    'max_price' : 3000,
    'min_bedrooms': 2,
    'minSqft': 1000,
    'lat' : 49.27665738550376,
    'lon' : -123.06877162609734,
    'search_distance': 7,
    'availabilityMode' : 0,
    'sale_date' : 'all+dates'
}


LAST_TIME = datetime.now() - timedelta(minutes = 31)
NEXT_MON_TRIP = datetime.combine(date.today() + timedelta( x if (x := (0-date.today().weekday()) % 7) else 7 ), time(7, 0)) # 0 is for Monday

TEL_TOKEN = os.environ['TEL_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

MAPS_TOKEN = os.environ['MAPS_TOKEN']
DAYCARE_GEO = '49.282,-123.120'


def escape_markdown(text):
    escape_chars = r'_*`['
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text) 


def parse_res(res):
    if len(res) == 2:
        for r in res[0]:
            if 'CategoryID' in r:
                if datetime.fromtimestamp(r['PostedDate']) >= LAST_TIME:
                    try:
                        maps_res = requests.get(url='https://maps.googleapis.com/maps/api/distancematrix/json',
                            params={
                                'destinations': DAYCARE_GEO,
                                'origins': f"{r['Latitude']},{r['Longitude']}",
                                'departure_time': int(NEXT_MON_TRIP.timestamp()),
                                'mode': 'driving',
                                'traffic_model': 'pessimistic',
                                'key': MAPS_TOKEN
                            }
                        )
                        maps_res = maps_res.json()
                        if 'error_message' in maps_res:
                            raise Exception(f"_Maps Error_: \n{maps_res['error_message']}")

                        post_res = requests.get(url=r['PostingURL'])

                        soup = BeautifulSoup(post_res.text, "html.parser")
                        suburb = x.text.strip() if (x := soup.find(class_='postingtitletext').small) else ''
                        attr = '\n'.join([f'_ - {escape_markdown(x.text)}_' for x in soup.find_all(class_='shared-line-bubble')])
                        addr = soup.find(class_='mapaddress').find(text=True).strip() if soup.find_all(class_='mapaddress') else ''
                        post_date = '\n'.join([f"*{x.next.strip()[:-1].capitalize()}*: {timeago.format(datetime.strptime(x.find(class_='date timeago')['datetime'], '%Y-%m-%dT%H:%M:%S%z'), datetime.now(timezone.utc))} _({x.find(class_='date timeago').text})_" for x in soup.find(class_='postinginfos').find_all(class_='postinginfo reveal')])
                        
                        message = f"{r['PostingTitle']}\n" + \
                            f"{suburb + chr(10) if suburb else ''}\n" + \
                            f"*Bedrooms*: {r['bedrooms']}\n" + \
                            f"*Price*: {r['price']}\n" + \
                            f"{attr}\n"+ \
                            f"*Address*: {escape_markdown(addr if addr else maps_res['origin_addresses'][0])}\n" + \
                            f"*Distance*: {escape_markdown(maps_res['rows'][0]['elements'][0]['distance']['text'])}\n" + \
                            f"*Duration*: {escape_markdown(maps_res['rows'][0]['elements'][0]['duration']['text'])}\n" + \
                            f"*In traffic*: {escape_markdown(maps_res['rows'][0]['elements'][0]['duration_in_traffic']['text'])}\n" + \
                            f"\n{post_date}\n" + \
                            f"\n{r['PostingURL']}"
                    except Exception as e:
                        print(f"Parsing error\n{e}")
                        message = f"*Data Parsing Error*\n{escape_markdown(str(e))}\n\n{r['PostingURL'] if 'PostingURL' in r else ''}"
                    
                    try:
                        print(r['PostingURL'])
                        tel_res = requests.get(url=f'https://api.telegram.org/bot{TEL_TOKEN}/sendMessage', params={'chat_id' : CHAT_ID, 'text' : message, 'parse_mode' : 'markdown', 'silent': True, 'disable_notification': True})
                        if not tel_res.ok:
                            print(f"Telegram error\n{tel_res.text}")
                    except Exception as e:
                        print(f"Telegram error\n{e}")
                    
            elif 'GeoCluster' in r:
                geocluster, key = parse_qs(urlparse(r['url']).query).values()
                get_geocluster(geocluster[0], key[0], CONFIG)
            else:
                print(f'UNKNOWN RESPONSE MESSAGE\n{r}')


def get_geocluster(geocluster, key, params):
    res = requests.get(url=URL, params=params | {'geocluster' : geocluster, 'key': key})
    parse_res(res.json())


def get_list(params):
    res = requests.get(url=URL, params=params)
    parse_res(res.json())



def main(a='', b=''):
    print('-'*30, 'Start', '-'*30)
    try:
       get_list(CONFIG)
    except Exception as e:
       print("Unhandled Exception!!!")
       print(e)
       traceback.print_exc(file=sys.stdout)
    print('-'*31, 'End', '-'*31)


if __name__ == "__main__":
    main()