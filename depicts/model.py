from sqlalchemy.ext.declarative import declarative_base
from .database import session, now_utc
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
    commons = Column(String)
    count = Column(Integer)
    entity = Column(postgresql.JSON)
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

class ArtworkItem(Base):
    __tablename__ = 'artwork'
    item_id = Column(Integer, primary_key=True, autoincrement=False)
    label = Column(String)
    entity = Column(postgresql.JSON)
    qid = column_property('Q' + cast(item_id, String))

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
    artwork_id = Column(Integer, ForeignKey('artwork.item_id'), primary_key=True)
    depicts_id = Column(Integer, ForeignKey('depicts.item_id'), primary_key=True)
    timestamp = Column(DateTime, default=now_utc())
    lastrevid = Column(Integer, nullable=True)

    artwork_qid = column_property('Q' + cast(artwork_id, String))
    depicts_qid = column_property('Q' + cast(depicts_id, String))

    artwork = relationship('ArtworkItem')
    depicts = relationship('DepictsItem')

    @property
    def url_norm_username(self):
        return quote(self.username.replace(' ', '_'))

    @property
    def user_wikidata_url(self):
        return 'https://www.wikidata.org/wiki/User:' + self.url_norm_username
