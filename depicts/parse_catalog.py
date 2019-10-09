from depicts import wd_catalog, relaxed_ssl

import lxml.html
import os.path
import requests
import hashlib

user_agent = 'Mozilla/5.0 (X11; Linux i586; rv:32.0) Gecko/20160101 Firefox/32.0'

def get_description_from_page(html):
    root = lxml.html.fromstring(html)
    div = root.find('.//div[@itemprop="description"]')
    if div is not None:
        return div.text

    meta_twitter_description = root.find('.//meta[@name="twitter:description"]')
    if meta_twitter_description is None:
        return
    twitter_description = meta_twitter_description.get('content')
    if not twitter_description:
        return
    twitter_description = twitter_description.strip()

    if not twitter_description:
        return

    for element in root.getiterator():
        if not element.text:
            continue
        text = element.text.strip()
        if not text:
            continue
        if text != twitter_description and text.startswith(twitter_description):
            return text

    return twitter_description

def get_catalog_page(property_id, value):
    detail = wd_catalog.lookup(property_id, value)
    url = detail['url']
    catalog_id = value.replace('/', '_')

    filename = f'cache/{property_id}_{catalog_id}.html'

    if os.path.exists(filename):
        html = open(filename, 'rb').read()
    else:
        r = requests.get(url, headers={'User-Agent': user_agent}, timeout=2)
        html = r.content
        open(filename, 'wb').write(html)

    return html

def get_catalog_url(url):
    md5_filename = hashlib.md5(url.encode('utf-8')).hexdigest() + '.html'
    filename = 'cache/' + md5_filename

    if os.path.exists(filename):
        html = open(filename, 'rb').read()
    else:
        r = relaxed_ssl.get(url,
                            headers={'User-Agent': user_agent},
                            timeout=2)
        html = r.content
        open(filename, 'wb').write(html)

    return html
