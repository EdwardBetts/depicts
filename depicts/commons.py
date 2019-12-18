from . import mediawiki, utils

commons_url = 'https://www.wikidata.org/w/api.php'
page_size = 50

def image_detail(filenames, thumbheight=None, thumbwidth=None):
    if not isinstance(filenames, list):
        filenames = [filenames]
    if not filenames:
        return {}

    params = {
        'action': 'query',
        'prop': 'imageinfo',
        'iiprop': 'url',
    }
    if thumbheight is not None:
        params['iiurlheight'] = thumbheight
    if thumbwidth is not None:
        params['iiurlwidth'] = thumbwidth

    images = {}

    for cur in utils.chunk(filenames, page_size):
        call_params = params.copy()
        call_params['titles'] = '|'.join(f'File:{f}' for f in cur)

        r = mediawiki.api_call(call_params, api_url=commons_url)

        for image in r.json()['query']['pages']:
            filename = utils.drop_start(image['title'], 'File:')
            images[filename] = image['imageinfo'][0] if 'imageinfo' in image else None

    return images


