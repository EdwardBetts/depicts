from . import mediawiki, utils

commons_url = 'https://www.wikidata.org/w/api.php'

def image_detail(filenames, thumbheight=None, thumbwidth=None):
    if not isinstance(filenames, list):
        filenames = [filenames]
    if not filenames:
        return {}

    params = {
        'action': 'query',
        'titles': '|'.join(f'File:{f}' for f in filenames),
        'prop': 'imageinfo',
        'iiprop': 'url',
    }
    if thumbheight is not None:
        params['iiurlheight'] = thumbheight
    if thumbwidth is not None:
        params['iiurlwidth'] = thumbwidth
    r = mediawiki.api_call(params, api_url=commons_url)

    images = {}

    for image in r.json()['query']['pages']:
        filename = utils.drop_start(image['title'], 'File:')
        images[filename] = image['imageinfo'][0]

    return images


