from depicts import (wikibase, relaxed_ssl, saam, dia, rijksmuseum, npg,
                     museodelprado, barnesfoundation)
import requests
import requests.exceptions
import lxml.html
import os.path
import hashlib

user_agent = 'Mozilla/5.0 (X11; Linux i586; rv:32.0) Gecko/20160101 Firefox/32.0'

table = {
    'P347': ('Joconde ID', 'https://www.pop.culture.gouv.fr/notice/joconde/$1'),
    'P350': ('RKDimages ID', 'https://rkd.nl/explore/images/$1'),
    'P1212': ('Atlas ID', 'http://cartelen.louvre.fr/cartelen/visite?srv=car_not_frame&idNotice=$1'),
    'P1428': ('Lost Art ID', 'http://www.lostart.de/EN/Verlust/$1'),
    'P1679': ('Art UK artwork ID', 'https://artuk.org/discover/artworks/$1'),
    'P1726': ('Florentine musea Inventario 1890 ID', 'http://www.polomuseale.firenze.it/inv1890/scheda.asp?position=1&ninv=$1'),
    'P2014': ('Museum of Modern Art work ID', 'http://www.moma.org/collection/works/$1'),
    'P2092': ('Bildindex der Kunst und Architektur ID', 'https://www.bildindex.de/document/obj$1'),
    'P2108': ('Kunstindeks Danmark artwork ID', 'https://www.kulturarv.dk/kid/VisVaerk.do?vaerkId=$1'),
    'P2242': ('Florentine musea catalogue ID', 'http://www.polomuseale.firenze.it/catalogo/scheda.asp?nctn=$1&value=1'),
    'P2282': ('Groeningemuseum work PID', 'http://groeningemuseum.be/collection/work/id/$1'),
    'P2344': ('AGORHA work ID', 'http://www.purl.org/inha/agorha/003/$1'),
    'P2511': ('MSK Gent work PID', 'http://mskgent.be/collection/work/id/$1'),
    'P2539': ('Nationalmuseum Sweden artwork ID', 'http://collection.nationalmuseum.se/eMuseumPlus?service=ExternalInterface&module=collection&objectId=$1&viewType=detailView'),
    'P2582': ('J. Paul Getty Museum object ID', 'http://www.getty.edu/art/collection/objects/$1'),
    'P3272': ('Zeri image ID', 'http://catalogo.fondazionezeri.unibo.it/scheda/opera/$1/'),
    'P3293': ('BALaT object ID', 'http://balat.kikirpa.be/object/$1'),
    'P3386': ('French Sculpture Census work ID', 'https://frenchsculpture.org/en/sculpture/$1'),
    'P3467': ('Inventario Sculture - Polo Museale Fiorentino', 'http://www.polomuseale.firenze.it/invSculture/scheda.asp?position=1&ninv=$1'),
    'P3504': ('Florentine Inventario Palatina art ID', 'http://www.polomuseale.firenze.it/invpalatina/scheda.asp?position=1&ninv=$1'),
    'P3634': ('The Met object ID', 'http://www.metmuseum.org/art/collection/search/$1'),
    'P3711': ('Vanderkrogt.net Statues ID', 'http://vanderkrogt.net/statues/object.php?record=$1'),
    'P3855': ('LombardiaBeniCulturali artwork ID', 'http://www.lombardiabeniculturali.it/opere-arte/schede/$1/'),
    'P3929': ('V&A item ID', 'http://collections.vam.ac.uk/item/$1'),
    'P4144': ('Athenaeum artwork ID', 'http://www.the-athenaeum.org/art/detail.php?id=$1'),
    'P4257': ('National Museums of Japan e-museum ID', 'http://www.emuseum.jp/detail/$1'),
    'P4373': ('National Trust Collections ID', 'http://www.nationaltrustcollections.org.uk/object/$1'),
    'P4380': ('Sandrart.net artwork ID', 'http://ta.sandrart.net/-artwork-$1'),
    'P4399': ('Enciclopédia Itaú Cultural ID', 'http://enciclopedia.itaucultural.org.br/$1'),
    'P4525': ('MuIS object ID', 'http://opendata.muis.ee/object/$1'),
    'P4564': ('Art Museum of Estonia artwork ID', 'https://digikogu.ekm.ee/oid-$1'),
    'P4582': ('Kulturelles Erbe Köln object ID', 'https://www.kulturelles-erbe-koeln.de/documents/obj/$1'),
    'P4610': ('ARTIC artwork ID', 'https://www.artic.edu/artworks/$1'),
    'P4611': ('LACMA ID', 'https://collections.lacma.org/node/$1'),
    'P4625': ('Museum of Fine Arts, Boston object ID', 'https://www.mfa.org/collections/object/$1'),
    'P4643': ('Philadelphia Museum of Art ID', 'http://www.philamuseum.org/collections/permanent/$1.html'),
    'P4659': ("Musée d'Orsay artwork ID", 'http://www.musee-orsay.fr/en/collections/index-of-works/notice.html?nnumid=$1'),
    'P4673': ('Museum of Fine Arts, Houston object ID', 'https://www.mfah.org/art/detail/$1'),
    'P4674': ('Indianapolis Museum of Art artwork ID', 'http://collection.imamuseum.org/artwork/$1/'),
    'P4683': ('National Gallery of Art artwork ID', 'https://www.nga.gov/content/ngaweb/Collection/art-object-page.$1.html'),
    'P4684': ('National Gallery of Victoria artwork ID', 'https://www.ngv.vic.gov.au/explore/collection/work/$1/'),
    'P4686': ('Carnegie Museum of Art ID', 'https://collection.cmoa.org/objects/$1'),
    'P4692': ('American Art Collaborative object ID', 'http://browse.americanartcollaborative.org/object/$1.html'),
    'P4701': ('Google Arts & Culture asset ID', 'https://artsandculture.google.com/asset/wd/$1'),
    'P4704': ('Smithsonian American Art Museum ID', 'https://americanart.si.edu/collections/search/artwork/?id=$1'),
    'P4709': ('Barnes Foundation ID', 'https://collection.barnesfoundation.org/objects/$1/details'),
    'P4712': ('Minneapolis Institute of Art artwork ID', 'https://collections.artsmia.org/art/$1'),
    'P4713': ('Walters Art Museum ID', 'http://art.thewalters.org/detail/$1'),
    'P4721': ('MuBE Virtual ID', 'http://mubevirtual.com.br/pt_br?Dados&area=ver&id=$1'),
    'P4737': ('Solomon R. Guggenheim Foundation artwork ID', 'https://www.guggenheim.org/artwork/$1'),
    'P4738': ('Yale Center for British Art artwork ID', 'http://collections.britishart.yale.edu/vufind/Record/$1'),
    'P4739': ('Musée des Augustins artwork ID', 'https://www.augustins.org/fr/oeuvre/-/oeuvre/$1'),
    'P4740': ('Brooklyn Museum artwork ID', 'https://www.brooklynmuseum.org/opencollection/objects/$1'),
    'P4761': ("Images d'Art artwork ID", 'http://art.rmngp.fr/en/library/artworks/$1'),
    'P4764': ('Arcade artwork ID', 'http://www.culture.gouv.fr/public/mistral/arcade_fr?ACTION=CHERCHER&FIELD_1=REF&VALUE_1=$1'),
    'P4814': ('Inventories of American Painting and Sculpture control number', 'https://siris-artinventories.si.edu/ipac20/ipac.jsp?&menu=search&index=.NW&term=$1'),
    'P4905': ('KMSKA work PID', 'http://kmska.be/collection/work/id/$1'),
    'P5210': ('National Gallery of Armenia work ID', 'http://www.gallery.am/en/database/item/$1/'),
    'P5223': ('Information Center for Israeli Art artwork ID', 'http://museum.imj.org.il/artcenter/includes/item.asp?id=$1'),
    'P5265': ('Dordrechts Museum artwork ID', 'https://www.dordrechtsmuseum.nl/objecten/id/$1'),
    'P5268': ('MNAV work ID', 'http://acervo.mnav.gub.uy/obras.php?q=ni:$1'),
    'P5269': ('Web umenia work ID', 'https://www.webumenia.sk/dielo/$1'),
    'P5407': ('MHK object ID', 'http://datenbank.museum-kassel.de/$1'),
    'P5499': ('Boijmans work ID', 'https://www.boijmans.nl/en/collection/artworks/$1'),
    'P5783': ('Cranach Digital Archive artwork ID', 'http://lucascranach.org/$1'),
    'P5823': ('Belvedere object ID', 'https://digital.belvedere.at/objects/$1/'),
    'P5891': ('Bpk-ID', 'http://www.bpk-images.de/id/$1'),
    'P6004': ('Brasiliana Iconográfica ID', 'https://www.brasilianaiconografica.art.br/obras/$1/wd'),
    'P6007': ('Salons ID', 'http://salons.musee-orsay.fr/index/notice/$1'),
    'P6020': ("d'Art d'Art ! ID", 'https://www.france.tv/france-2/d-art-d-art/$1.html'),
    'P6141': ('À nos grands hommes ID', 'https://anosgrandshommes.musee-orsay.fr/index.php/Detail/objects/$1'),
    'P6152': ('National Portrait Gallery (United States) object ID', 'http://npg.si.edu/object/npg_$1'),
    'P6238': ('Monument aux morts ID', 'https://monumentsmorts.univ-lille.fr/monument/$1/wd/'),
    'P6239': ('IEC commemorative monument of Catalonia ID', 'https://monuments.iec.cat/fitxa.asp?id=$1'),
    'P6246': ('Paris Musées work ID', 'http://parismuseescollections.paris.fr/en/node/$1'),
    'P6310': ('Muséosphère work ID', 'http://museosphere.paris.fr/oeuvres/$1'),
    'P6332': ("Panorama de l'art ID", 'https://www.panoramadelart.com/$1'),
    'P6355': ('MNAM artwork ID', 'https://collection.centrepompidou.fr/#/artwork/$1'),
    'P6356': ('IHOI work ID', 'http://www.ihoi.org/app/photopro.sk/ihoi_icono/detail?docid=$1&lang=eng'),
    'P6358': ('Musée Picasso artwork ID', 'https://www.navigart.fr/picassoparis/#/artwork/$1'),
    'P6372': ('Interpol WOA artwork ID (OBSOLETE)', 'https://www.interpol.int/notice/search/woa/$1'),
    'P6374': ('MAMVP artwork ID', 'http://www.mam.paris.fr/en/online-collections#/artwork/$1'),
    'P6489': ('Joan Miró Online Image Bank ID', 'https://www.successiomiro.com/catalogue/object/$1'),
    'P6506': ('Eliseu Visconti Project ID', 'https://eliseuvisconti.com.br/obra/$1'),
    'P6565': ('Musenor artwork ID', 'https://webmuseo.com/ws/musenor/app/collection/record/$1'),
    'P6576': ('Art Fund artwork ID', 'https://www.artfund.org/supporting-museums/art-weve-helped-buy/artwork/$1/wd'),
    'P6595': ('Paintings by Salvador Dalí ID', 'https://www.salvador-dali.org/en/artwork/catalogue-raisonne/obra/$1/'),
    'P6610': ('Ashmolean museum ID', 'http://collections.ashmolean.org/object/$1'),
    'P6625': ('Salvador Dali Museum ID', 'http://archive.thedali.org/mwebcgi/mweb.exe?request=record;id=$1;type=101'),
    'P6629': ('Artcurial lot ID', 'https://www.artcurial.com/en/$1'),
    'P6631': ('Tainacan MHN ID', 'http://mhn.acervos.museus.gov.br/reserva-tecnica/$1'),
    'P6633': ('Cini Foundation ID', 'http://arte.cini.it/Opere/$1'),
    'P6643': ('TV Spielfilm series ID', 'https://www.tvspielfilm.de/serien/$1'),
    'P6738': ('Whitney Museum of American Art artwork ID', 'https://whitney.org/collection/works/$1'),
    'P7229': ('Fundación Goya en Aragón ID', 'https://fundaciongoyaenaragon.es/obra/wd/$1'),
}

def lookup(property_id, value):
    label, formatter = table[property_id]
    url = formatter.replace('$1', value)

    return {
        'label': label,
        'url': url,
        'value': value,
    }

def find_catalog_id(entity):
    return table.keys() & entity['claims'].keys()

def check_catalog(entity, catalog):
    catalog_url = catalog['url']
    catalog_ids = catalog['ids']

    if 'P4704' in entity['claims']:
        saam_id = wikibase.first_datavalue(entity, 'P4704')
        cat = saam.get_catalog(saam_id)
        if cat:
            catalog.update(cat)
            return

    if 'P4709' in entity['claims']:
        catalog_id = wikibase.first_datavalue(entity, 'P4709')
        cat = barnesfoundation.get_catalog(catalog_id)
        if cat:
            catalog.update(cat)
            return

    institutions = [
        ('www.dia.org', dia),
        ('www.rijksmuseum.nl', rijksmuseum),
        ('www.npg.org.uk', npg),
        ('www.museodelprado.es', museodelprado),
    ]

    if catalog_url:
        for host, module in institutions:
            if host in catalog_url:
                cat = module.get_catalog(catalog_url)
                if not cat:
                    continue
                catalog.update(cat)
                return

        html = get_catalog_url(catalog_url)
        if html:
            description = get_description_from_page(html)
            if description:
                catalog['description'] = description
                return

    for property_id in sorted(catalog_ids):
        if property_id == 'P350':
            continue  # RKDimages ID
        value = wikibase.first_datavalue(entity, property_id)
        # identifier can be 'no value', example: Q26754456
        if value is None:
            continue
        detail = lookup(property_id, value)
        try:
            html = get_catalog_page(property_id, value)
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError):
            continue  # ignore this error
        if not html:
            continue
        description = get_description_from_page(html)
        if not description:
            continue
        catalog = {
            'institution': detail['label'],
            'description': description,
        }

def get_catalog_from_artwork(entity):
    catalog_ids = find_catalog_id(entity)
    catalog_detail = []
    for property_id in sorted(catalog_ids):
        value = wikibase.first_datavalue(entity, property_id)
        # identifier can be 'no value', example: Q26754456
        if value is None:
            continue
        detail = lookup(property_id, value)
        catalog_detail.append(detail)

    catalog = {
        'url': wikibase.first_datavalue(entity, 'P973'),
        'detail': catalog_detail,
        'ids': catalog_ids,
    }

    try:
        check_catalog(entity, catalog)
    except (requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError):
        pass

    return catalog

def get_description_from_page(html):
    if not html:
        return
    root = lxml.html.fromstring(html)
    div = root.find('.//div[@itemprop="description"]')
    if div is not None:
        return div.text

    div_list = root.find_class('item-description')
    if len(div_list):
        return div_list[0].text_content()

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
    detail = lookup(property_id, value)
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
