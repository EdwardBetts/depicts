from . import utils
import re
import calendar

month_pattern = '|'.join(m for m in calendar.month_name if m)
re_date_based = re.compile(r'^(\d{4}-\d{2}-\d{2}|(' + month_pattern + r') \d{4}|\d{4}s?|\d{1,2}(st|nd|rd|th)-century) ')

ns_cat = 'Category:'

class Category:
    def __init__(self, title, site):
        if title.startswith(ns_cat):
            title = title[len(ns_cat):]
        self.title = title
        self.site = site
        self.item = None

    def __repr__(self):
        return f'{self.__class__.__name__}({self.title!r}, {self.site!r})'

    def set_item(self, item):
        self.item = item

    @property
    def url(self):
        return utils.wiki_url(self.title, self.site, ns='Category')

    def date_based(self):
        return bool(re_date_based.match(self.title))

    def contains_artist_name(self):
        if not self.item:
            return
        return any(artist.lower() in self.title.lower()
                   for artist in self.item.artist_labels())

    def parents(self):
        if not self.item:
            return []
        return self.item.parent_categories[self.site].get(self.title, [])

    def is_exhibition(self):
        return any(parent.title.startswith('Art exhibitions ')
                   for parent in self.parents())

    def names_for_wikidata(self):
        highlight = self.check()
        interesting = len(highlight) > 1

        if not interesting:
            if self.date_based() or self.contains_artist_name() or self.is_exhibition():
                return []

            return utils.also_singular(self.title)

        for significant, text in highlight:
            if not significant:
                continue
            title = text.strip()
            title = title[0].upper() + title[1:]
            for sep in ' with ', ' at ', ' wearing ':
                if sep in title:
                    before, _, after = title.partition(sep)
                    names = []
                    for x in title, before, after:
                        names += utils.also_singular(x)
                    return names
            return utils.also_singular(title)

    def urls_for_wikidata(self):
        return [utils.wiki_url(name, self.site, ns='Category')
                for name in self.names_for_wikidata()]

    def check(self):
        cat = self.title
        lc_cat = cat.lower()
        by_endings = ['title', 'technique', 'period', 'century', 'country', 'movement',
                      'medium', 'year', 'painter']

        if self.item:
            by_endings += self.item.artist_labels()

        for after in ('in art', 'in portrait paintings', 'in landscape paintings', 'in culture', 'in popular culture', 'in painting', 'in 1', 'in 2', 'looking at viewer'):
            pos = lc_cat.find(after)
            # don't highlight "1512 in art"
            if pos == -1 or cat[:pos - 1].isdigit():
                continue
            return [(True, cat[:pos]), (False, cat[pos:])]

        for before in ('paintings of', 'portraits of', 'landscapes of',
                       'portraits with', 'paintings with', 'paintings depicting',
                       'portraits depicting', 'landscapes depicting', 'works about'):
            pos = lc_cat.find(before)
            if pos == -1:
                continue
            pos += len(before)
            for by_ending in by_endings:
                ending = ' by ' + by_ending
                if lc_cat.endswith(ending):
                    return [(False, cat[:pos]),
                            (True, cat[pos:-len(ending)]),
                            (False, cat[-len(ending):])]

            return [(False, cat[:pos]), (True, cat[pos:])]

        pos = lc_cat.find('of ')
        if pos != -1:
            return [(True, cat[:pos]), (False, cat[pos:])]

        return [(False, cat)]
