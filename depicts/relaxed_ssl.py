import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context

CIPHERS = 'DEFAULT@SECLEVEL=1'

class HTTPSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=CIPHERS)
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

def get(*args, **kwargs):
    s = requests.Session()
    s.mount('https://', HTTPSAdapter())
    return s.get(*args, **kwargs, verify=False)
