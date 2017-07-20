#! /usr/bin/python3

import os
import sys
import json
import sqlite3


STOP = 0
WAIT = 10
WORK = 20
FAIL = 30
DONE = 50


class SDB(object):
    dbfile = "url_info.db"

    def __enter__(self):
        self.conn = sqlite3.connect(self.dbfile)
        self.cur = self.conn.cursor()
        return self.cur

    def __exit__(self, exc_type, exc_value, traceback):
        self.conn.commit()
        self.cur.close()
        self.conn.close()


def init_db(cfg):
    with SDB() as c:
        c.execute('''
        create table if not exists aviurl (
            url text,           -- movie url
            name text,          -- movie name
            mime text,          -- mime from remote
            opts text,          -- options for download, json dict
            errs text,          -- errors during download, logexc
            size bigint,        -- movie file size
            path text,          -- movie local file path
            updt datetime,      -- when the url be submitted
            bgdt datetime,      -- when the url start download
            eddt datetime,      -- when the url finished download
            prog real,          -- progress, xx.x%
            prio tinyint,       -- downlaod priority
            flag tinyint        -- status, WAIT, WORKING, DONE
        )''')


class UOBJ(object):
    def __init__(self, dats=[]):
        for dat in dats:
            setattr(self, dat[0], dat[1])
        if hasattr(self, "opts"):
            if self.opts:
                self.opts = json.loads(self.opts)
            else:
                self.opts = {}

    def __str__(self):
        return str(self.__dict__)


def add_one_url(url, title="", opts={}):
    #opts = {}
    #if dest:
    #    opts["dest"] = dest
    opts = json.dumps(opts)
    with SDB() as c:
        c.execute("insert into aviurl (url, name, updt, opts, flag) "
                  "values (?, ?, datetime('now', 'localtime'), ?, ?)",
                  (url, title, opts, STOP))
        return c.lastrowid


def del_one_url(mid):
    with SDB() as c:
        c.execute("delete from aviurl where rowid=?", (mid,))


def query_select(q, p=()):
    with SDB() as c:
        urls = c.execute(q, p)
        desc = [x[0] for x in c.description]
        # have to finish this in "with" scope
        #ret = [dict(zip(desc, url)) for url in urls]
        ret = [UOBJ(zip(desc, url)) for url in urls]
    return ret


def short_it(src, size=30):
    if len(src) + 3 <= size:
        return src
    return src[:size - 3] + '...'


def query_urls():
    ww = 0
    urls = query_select("select rowid as mid, * from aviurl "
                        "order by updt desc")
    for uo in urls:
        setattr(uo, '_short_url', short_it(uo.url))
        fh = "FF"
        fl = uo.flag
        lnk = "/rest?mid=%d&act=start" % uo.mid
        if fl is None or fl == STOP:
            fh = 'start'
        elif fl == WAIT:
            fh = 'waiting'
            ww = 1
        elif fl == WORK:
            fh = 'working'
            ww = 1
        elif fl == FAIL:
            fh = 'retry'
        elif fl == DONE:
            lnk = '/rest?mid=%d&act=play' % uo.mid
            fh = 'Done'
        setattr(uo, '_flag_html', lnk)
        setattr(uo, '_flag_name', fh)
    return urls, ww


def pick_url(mid=0):
    if mid:
        ret = query_select("select rowid as mid, * from aviurl where rowid=?",
                           (mid,))
    else:
        ret = qieru_select("select rowid as mid, * from aviurl "
                           "where flag=? limit 1",
                           (WAIT,))
    return ret[0] if ret else None


def get_by_flag(f):
    return query_select("select rowid as mid, * from aviurl where flag=?",
                        (f,))


def set_flag(uobj, act):
    fm = {"wait": WAIT, "start": WORK, "fail": FAIL, "stop": DONE}
    uobj.flag = fm.get(act, act)
    with SDB() as c:
        c.execute("update aviurl set flag=? where rowid=?",
                  (uobj.flag, uobj.mid))


def update_filename(uobj, dn, fn):
    uobj.name = os.path.basename(fn)
    uobj.path = os.path.join(dn, fn)
    with SDB() as c:
        urls = c.execute("update aviurl set name=?, path=? where rowid=?",
                         (uobj.name, uobj.path, uobj.mid))


def dump_urls():
    for uobj in query_urls():
        print(uobj.name, "\n", uobj.url, "\n", uobj.path, "\n")


def usage():
    print('URL DB utility')
    print('Usage:', sys.argv[0], "-l [dbfile]")
    print('    -l  list all url in DB')
    sys.exit(1)


def main():
    if len(sys.argv) not in (2, 3):
        usage()

    if sys.argv[1] == '-l':
        if len(sys.argv) == 3:
            SDB.dbfile = sys.argv[2]
        dump_urls()
    else:
        usage()


if __name__ == '__main__':
    main()
