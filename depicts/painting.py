from . import utils, wdqs, mediawiki
import nltk
import re

re_from_article = re.compile(r'(?:portrays|depicts|depictions of|it shows) (.+?)\.', re.I)

ignore_for_depicts = {
    43445,     # female organism - use: female (Q6581072)
    44148,     # male organism   - use: male (Q6581097)
    21075684,  # children        - use: child (Q7569)
    180788,    # National Gallery
    780294,    # human physical appearance
    2472587,   # people
    33659,     # People
}

query = '''
select distinct ?item ?itemLabel ?commonscat ?cat_url ?sitelink
where {
  service wikibase:label { bd:serviceParam wikibase:language "en" }
  filter (?item != wd:QID)

  {
    VALUES (?commonscat) { COMMONS_CAT }
    ?item wdt:P373 ?commonscat .
    filter not exists { ?item wdt:P31 wd:Q4167836 }  # Wikimedia category
    filter not exists { ?item wdt:P31 wd:Q4167410 }  # Wikimedia disambiguation page
    filter not exists { ?item wdt:P31 wd:Q24046192 } # Wikimedia category of stubs
    filter not exists { ?item wdt:P31 wd:Q4167836 }  # Wikimedia list article
    filter not exists { ?item wdt:P31 wd:Q4663903 }  # Wikimedia portal
  } union {
    VALUES (?commonscat) { COMMONS_CAT }
    ?cat_item wdt:P373 ?commonscat .
    ?cat_item wdt:P301 ?item .
  } union {
    VALUES (?cat_url) { CAT_URL }
    ?cat_url schema:about ?cat_item .
    ?cat_item wdt:P301 ?item .
  } union {
    VALUES (?sitelink) { SITELINK }
    ?sitelink schema:about ?item .
    filter not exists { ?item wdt:P31 wd:Q4167410 }
  }
}'''

class QueryResultRow:
    def __init__(self, row):
        self.row = {k: (v if k.startswith('item') else [v]) for k, v in row.items()}
        self.item_id = wdqs.row_id(row)
        self.label = wdqs.get_row_value(row, 'itemLabel')

    def update(self, row):
        for key, value in row.items():
            if key.startswith('item'):
                continue
            self.row.setdefault(key, []).append(value)

    @property
    def url(self):
        return self.row['item']['value']

    @property
    def qid(self):
        return f'Q{self.item_id}'

    def sources(self):
        return {k: v for k, v in self.row.items() if not k.startswith('item')}

    def sources_list(self):

        def get_value(i):
            if i['type'] != 'uri':
                return i['value']
            wiki_start = i['value'].rfind('/wiki/')
            return i['value'][wiki_start + 6:]

        return [(k, [get_value(i) for i in v])
                for k, v in self.row.items()
                if not k.startswith('item')]

class Painting:
    def __init__(self, qid):
        self.entity = mediawiki.get_entity_with_cache(qid)
        self.item_id = int(qid[1:])

        if self.enwiki:
            content, cats = mediawiki.get_content_and_categories(self.enwiki, 'enwiki')
            self.enwiki_content = content
            self.enwiki_categories = mediawiki.process_cats(cats, 'enwiki')
            for cat in self.enwiki_categories:
                cat.set_item(self)
        else:
            self.enwiki_content = None
            self.enwiki_categories = None

        sites = ['commons', 'enwiki']
        self.parent_categories = {site: {} for site in sites}

        self.categories = self.get_categories()

    @property
    def image_filename(self):
        return self.entity['claims']['P18'][0]['mainsnak']['datavalue']['value']

    @property
    def display_title(self):
        if 'en' not in self.entity['labels']:
            return self.qid
        return f'{self.en_title} ({self.qid})'

    @property
    def url(self):
        return 'https://www.wikidata.org/wiki/' + self.qid

    def get_artist_entities(self):
        self.artist_entities = []

        for artist in self.artists_claim:
            artist_qid = artist['id']
            self.artist_entities.append(mediawiki.get_entity(artist_qid))

    def artist_labels(self):
        if not hasattr(self, 'artist_entities'):
            self.get_artist_entities()
        return [artist['labels']['en']['value'] for artist in self.artist_entities]

    @property
    def commons_cats(self):
        return [i['mainsnak']['datavalue']['value']
                for i in self.entity['claims'].get('P373', [])]

    @property
    def commons_sitelink(self):
        return self.sitelinks['commons']['value'] if 'commons' in self.sitelinks else None

    @property
    def en_title(self):
        if 'en' in self.entity['labels']:
            return self.entity['labels']['en']['value']
        else:
            return self.qid

    @property
    def artists_claim(self):
        return [image['mainsnak']['datavalue']['value']
                 for image in self.entity['claims'].get('P170', [])]

    @property
    def artists(self):
        if not hasattr(self, 'artist_entities'):
            self.get_artist_entities()

        items = [image['mainsnak']['datavalue']['value']
                 for image in self.entity['claims'].get('P170', [])]

        lookup = {artist['id']: artist['labels'] for artist in self.artist_entities}

        for item in items:
            item['labels'] = lookup[item['id']]

        return items

    @property
    def qid(self):
        return f'Q{self.item_id}'

    @property
    def commons_filenames(self):
        return [image['mainsnak']['datavalue']['value']
                for image in self.entity['claims'].get('P18', [])]

    def commons_cat_from_sitelink(self):
        ns = 'Category:'
        if not self.commons_sitelink or not self.commons_sitelink.startswith(ns):
            return
        return self.commons_sitelink[len(ns):]

    @property
    def enwiki_url(self):
        enwiki = self.enwiki
        if not enwiki:
            return
        return 'https://en.wikipedia.org/wiki/' + enwiki.replace(' ', '_')

    @property
    def sitelinks(self):
        return self.entity['sitelinks']

    @property
    def claims(self):
        return self.entity['claims']

    @property
    def enwiki(self):
        return self.sitelinks['enwiki']['title'] if 'enwiki' in self.sitelinks else None

    def get_categories(self):
        titles = {'File:' + filename for filename in self.commons_filenames}
        for commons_cat in self.commons_cats:
            titles.add('Category:' + commons_cat)
        if self.commons_sitelink:
            titles.add(self.commons_sitelink)
        if not titles:
            return []

        cat_list = mediawiki.get_categories(titles, 'commons')

        for title, cats in cat_list:
            for cat in cats:
                cat.set_item(self)
            if not title.startswith('Category:'):
                continue
            self.parent_categories['commons'][utils.drop_category_ns(title)] = cats

        get_more_cats = []
        for _, cats in self.parent_categories['commons'].items():
            for cat in cats:
                if cat.title not in self.parent_categories:
                    get_more_cats.append('Category:' + cat.title)

        for title, cats in mediawiki.get_categories(get_more_cats, 'commons'):
            for cat in cats:
                cat.set_item(self)
            self.parent_categories['commons'][utils.drop_category_ns(title)] = cats

        if self.enwiki:
            cat_list.append((self.enwiki, self.enwiki_categories))

            get_more_cats = ['Category:' + cat.title for cat in self.enwiki_categories]
            for title, cats in mediawiki.get_categories(get_more_cats, 'enwiki'):
                self.parent_categories['enwiki'][utils.drop_category_ns(title)] = cats

        return cat_list

    def depicts_from_enwiki_content(self):
        if not self.enwiki_url:
            return
        for par in self.enwiki_content.split('\n\n'):
            m = re_from_article.search(par)
            if m:
                return m.group(1)

    def query_variables(self):
        commons_cat = []
        cat_url = []
        keywords = []
        for _, categories in self.categories:
            for cat in categories:
                names = cat.names_for_wikidata()
                keywords += names
                if cat.site == 'commons':
                    commons_cat += names
                cat_url += cat.urls_for_wikidata()

        text = self.depicts_from_enwiki_content()
        if text:
            sentences = nltk.sent_tokenize(text)

            for sentence in sentences:
                for word, pos in nltk.pos_tag(nltk.word_tokenize(str(sentence))):
                    if not utils.word_contains_letter(word):
                        continue
                    if not pos.startswith('NN'):
                        continue
                    word = word.strip('|')
                    for k in word.strip('|').split('|'):
                        if utils.word_contains_letter(k):
                            keywords += utils.also_singular(k)

        keywords = [k for k in keywords if utils.word_contains_letter(k)]

        return {
            'commons_cat': commons_cat,
            'cat_url': cat_url,
            'keywords': keywords,
        }

    def build_query(self):
        query_vars = self.query_variables()
        sitelinks = [utils.wiki_url(title, 'enwiki') for title in query_vars['keywords']]
        sitelinks = [url for url in sitelinks if url]

        q = query.replace('COMMONS_CAT', wdqs.quote_list(query_vars['commons_cat']))
        q = q.replace('CAT_URL', wdqs.url_list(query_vars['cat_url']))
        q = q.replace('QID', self.qid)
        q = q.replace('SITELINK', wdqs.url_list(sitelinks))
        return q

    def run_query(self):
        query = self.build_query()

        rows = wdqs.run_query_with_cache(query)
        by_id = {}
        results = []
        for row in rows:
            item_id = wdqs.row_id(row)
            if item_id in ignore_for_depicts:
                continue
            if item_id in by_id:
                by_id[item_id].update(row)
                continue
            hit = QueryResultRow(row)
            by_id[item_id] = hit
            results.append(hit)

        return sorted(results, key=lambda hit: hit.item_id)
