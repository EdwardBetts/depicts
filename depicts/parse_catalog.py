import lxml.html

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
