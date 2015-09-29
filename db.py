#! /usr/bin/python3

import sys
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


def init_db():
    with SDB() as c:
        c.execute('''
        create table if not exists aviurl (
            url text,           -- movie url
            name text,          -- movie name
            mime text,          -- mime from remote
            opts text,          -- options for download, json
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

    def __str__(self):
        return str(self.__dict__)


def add_one_url(url, title=""):
    with SDB() as c:
        c.execute("insert into aviurl (url, name, updt, flag) "
                  "values (?, ?, datetime('now', 'localtime'), ?)",
                  (url, title, STOP))


def query_select(q, p=()):
    with SDB() as c:
        urls = c.execute(q, p)
        desc = [x[0] for x in c.description]
        # have to finish this in "with" scope
        #ret = [dict(zip(desc, url)) for url in urls]
        ret = [UOBJ(zip(desc, url)) for url in urls]
    return ret


def query_urls():
    return query_select("select rowid as mid, * from aviurl")


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


def set_flag(mid, act):
    fm = {"wait": WAIT, "start": WORK, "fail": FAIL, "stop": DONE}
    with SDB() as c:
        c.execute("update aviurl set flag=? where rowid=?",
                  (fm.get(act, act), mid))


def update_filename(mid, fn):
    with SDB() as c:
        urls = c.execute("update aviurl set path=? where rowid=?",
                         (fn, mid))


def dump_urls():
    for uobj in query_urls():
        print(uobj)


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
