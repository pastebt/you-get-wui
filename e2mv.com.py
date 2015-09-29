#! /usr/bin/python3

import re
import sys
from urllib.parse import unquote

from db import add_one_url


if len(sys.argv) != 4:
    print('Usage: ' + sys.argv[0] + " name min_sect file")
    sys,exit(1)

name = sys.argv[1]
msec = int(sys.argv[2])
html = open(sys.argv[3]).read()

m = re.search('''url_list="([^;]+)"''', html)
dat = m.group(1)
ss = unquote(dat).split("$$$")
sect = 0
for s in ss:
    sect += 1
    part = 0
    ps = s.split("+++")
    for p in ps:
        part += 1
        title = "%s_s%02dp%02d" % (name, sect, part)
        url = p.split("++")[1]
        if sect < msec:
            continue
        print("%s %s" % (title, url))
        add_one_url(url, title)
