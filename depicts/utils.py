from itertools import islice

def ordinal(n):
    return "%d%s" % (n, 'tsnrhtdd'[(n / 10 % 10 != 1) * (n % 10 < 4) * n % 10::4])

def chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())

def drop_start(s, start):
    assert s.startswith(start)
    return s[len(start):]
