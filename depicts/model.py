from sqlalchemy.ext.declarative import declarative_base
from .database import session, now_utc
from . import wikibase, utils
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import Integer, String, DateTime, Boolean
from sqlalchemy.orm import column_property, relationship, synonym
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.sql.expression import cast
from sqlalchemy.dialects import postgresql
from urllib.parse import quote

Base = declarative_base()
Base.query = session.query_property()

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, autoincrement=False)
    username = Column(String, unique=True)
    options = Column(postgresql.JSON)
    first_seen = Column(DateTime, default=now_utc())
    is_admin = Column(Boolean, default=False)

class DepictsItem(Base):
    __tablename__ = 'depicts'
    item_id = Column(Integer, primary_key=True, autoincrement=False)
    label = Column(String)
    description = Column(String)
    count = Column(Integer)
    qid = column_property('Q' + cast(item_id, String))
    db_alt_labels = relationship('DepictsItemAltLabel',
                                 collection_class=set,
                                 cascade='save-update, merge, delete, delete-orphan',
                                 backref='item')
    alt_labels = association_proxy('db_alt_labels', 'alt_label')

class DepictsItemAltLabel(Base):
    __tablename__ = 'depicts_alt_label'
    item_id = Column(Integer,
                     ForeignKey('depicts.item_id'),
                     primary_key=True,
                     autoincrement=False)
    alt_label = Column(String, primary_key=True)

    def __init__(self, alt_label):
        self.alt_label = alt_label

class Item(Base):
    __tablename__ = 'item'
    item_id = Column(Integer, primary_key=True, autoincrement=False)
    # label = Column(String)  # column removed 2019-12-18
    entity = Column(postgresql.JSON)
    lastrevid = Column(Integer, nullable=True, unique=True)
    modified = Column(DateTime, nullable=True)
    is_artwork = Column(Boolean, nullable=False, default=False)
    qid = column_property('Q' + cast(item_id, String))

    def image_count(self):
        p18 = self.entity['claims'].get('P18')
        return len(p18) if p18 else 0

    def image_filename(self):
        p18 = self.entity['claims'].get('P18')
        if not p18:
            return

        try:
            return p18[0]['mainsnak']['datavalue']['value']
        except KeyError:
            return

    @property
    def label(self):
        return wikibase.get_entity_label(self.entity)

    @property
    def artist(self):
        v = wikibase.first_datavalue(self.entity, 'P170')
        if not v:
            return
        return v['id']

    @property
    def depicts(self):
        return self.linked_qids('P180')

    @property
    def instance_of(self):
        return self.linked_qids('P31')

    def linked_qids(self, prop):
        values = self.entity['claims'].get(prop) or []
        return [v['mainsnak']['datavalue']['value']['id']
                for v in values
                if 'datavalue' in v['mainsnak']]

    @property
    def date(self):
        v = wikibase.first_datavalue(self.entity, 'P571')
        if v:
            return utils.format_time(v['time'], v['precision'])

class Triple(Base):
    __tablename__ = 'triple'
    subject_id = Column(Integer,
                        ForeignKey('item.item_id'),
                        primary_key=True)
    predicate_id = Column(Integer, primary_key=True, index=True)
    object_id = Column(Integer, primary_key=True, index=True)

    subject = relationship('Item', backref='triples')

class HumanItem(Base):
    __tablename__ = 'human'
    item_id = Column(Integer, primary_key=True, autoincrement=False)
    year_of_birth = Column(Integer, nullable=False)
    year_of_death = Column(Integer, nullable=False)
    age_at_death = column_property(year_of_death - year_of_birth)
    qid = column_property('Q' + cast(item_id, String))

    yob = synonym('year_of_birth')
    yod = synonym('year_of_death')

class Language(Base):
    __tablename__ = 'language'
    item_id = Column(Integer, primary_key=True, autoincrement=False)
    wikimedia_language_code = Column(String, index=True, unique=True)
    en_label = Column(String, nullable=False)

    code = synonym('wikimedia_language_code')
    label = synonym('en_label')

    @classmethod
    def get_by_code(cls, code):
        return cls.query.filter_by(wikimedia_language_code=code).one()


class Edit(Base):
    __tablename__ = 'edit'
    username = Column(String, primary_key=True)
    artwork_id = Column(Integer, ForeignKey('item.item_id'), primary_key=True)
    depicts_id = Column(Integer, ForeignKey('depicts.item_id'), primary_key=True)
    timestamp = Column(DateTime, default=now_utc())
    lastrevid = Column(Integer, nullable=True)

    artwork_qid = column_property('Q' + cast(artwork_id, String))
    depicts_qid = column_property('Q' + cast(depicts_id, String))

    artwork = relationship('Item')
    depicts = relationship('DepictsItem')

    @property
    def url_norm_username(self):
        return quote(self.username.replace(' ', '_'))

    @property
    def user_wikidata_url(self):
        return 'https://www.wikidata.org/wiki/User:' + self.url_norm_username

class WikidataQuery(Base):
    __tablename__ = 'wikidata_query'
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    sparql_query = Column(String)
    path = Column(String)
    status_code = Column(Integer)
    error_text = Column(String)
    query_template = Column(String)
    row_count = Column(Integer)
    page_title = Column(String)
    endpoint = Column(String)

    @property
    def duration(self):
        if self.end_time:
            return self.end_time - self.start_time

    @property
    def display_seconds(self):
        return f'{self.duration.total_seconds():.1f}'

    @property
    def template(self):
        if not self.query_template:
            return

        t = self.query_template
        if t.startswith('query/'):
            t = t[6:]
        if t.endswith('.sparql'):
            t = t[:-7]

        return t

    @property
    def bad(self):
        return self.status_code and self.status_code != 200
