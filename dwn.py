#! /usr/bin/python3

import os
import re
import sys
import select
import traceback
import queue
from http.client import HTTPConnection
from subprocess import Popen, STDOUT, PIPE
from multiprocessing import Pipe, Queue, Process
from urllib.parse import quote, unquote, urlparse

from db import WORK, WAIT, STOP, DONE, FAIL
from db import pick_url, update_filename, set_flag, get_by_flag


class UpFile(object):
    def __init__(self, filename, name, bun=""):
        self.s = 0
        self.f = open(filename, "r+b")
        #fn = '_'.join(os.path.basename(filename).split('"'))
        fn = os.path.basename(filename)
        fn = "_".join(re.split('''\?|\:|\|''', fn))
        fn = "'".join(re.split('"', fn))
        pre = "--%s\r\n" % bun
        pre = '%sContent-Disposition: form-data; name="%s"' % (pre, name)
        pre = '%s; filename="%s"\r\n' % (pre, fn)
        pre = '%sContent-Type: text/plain\r\n\r\n' % pre
        self.pre = pre.encode("utf8")
        self.end = ("\r\n--%s--" % bun).encode("ascii")
        self.tal = 0
        self.cnt = 0

    def size(self):
        self.tal = os.fstat(self.f.fileno()).st_size
        return len(self.pre) + self.tal + len(self.end)

    def read(self, bufsize):
        #FIXME, if bufsize < len(self.pre) or bufsize < len(self.end)
        if self.s == 0:
            self.s = 1
            #print '#',
            return self.pre
        if self.s == 1:
            buf = self.f.read(bufsize)
            if buf:
                #print '#',
                self.cnt += len(buf)
                sys.stdout.write("\r%0.1f" % (self.cnt * 100.0 / self.tal))
                return buf
            self.s = 2
            print("")
            return self.end
        return ""


class WFP(object):
    def __init__(self, who, out, mid=0):
        self.out = out
        self.mid = mid
        self.left = ""
        self.who = who

    def write(self, dat):
        self.left = self.left + dat
        if self.left[-1] in '\r\n' or len(self.left) > 200:
            self.out.put({"who": self.who, "mid": self.mid, "dat": self.left})
            self.left = ""

    def flush(self):
        pass


def find_til(til, line):
    for t in til.strip().split("\n"):
        m = re.match(t.strip(), line)
        if m:
            return m.group(1)
    return None


def nb_put(q, dat):
    try:
        q.put_nowait(dat)
    except queue.Full:
        pass


def work(cfg, uobj, w2s):
    set_flag(uobj, WORK)
    for sect in cfg.sections():
        if not sect.startswith('download_'):
            continue
        out = uobj.opts.get("dest")
        if not out:
            out = './'
        dn  = cfg[sect]['dir']
        til = cfg[sect]['til']
        per = cfg[sect]['per']
        cmd = cfg[sect]['cmd'].format(URL=uobj.url, OUTDIR=out)
        cmd = "cd %s && %s" % (dn, cmd)
        print("cmd =", cmd)
        #print("til =", til)

        p = Popen(cmd, shell=True, bufsize=1,
                  universal_newlines=True, stdout=PIPE, stderr=STDOUT)

        for l in p.stdout:
            e = "\n"
            t = find_til(til, l)
            if t:
                print("got title:", t)
                update_filename(uobj, os.path.join(dn, out),
                                os.path.basename(t))
                #w2s.put({"who": "worker", "mid": uobj.mid, "dat": "got title"})
                nb_put(w2s, {"who": "worker", "mid": uobj.mid, "dat": "got title"})
            else:
                f = find_til(per, l)
                if f:
                    e = "\r"
                    #w2s.put({"who": "worker", "mid": uobj.mid, "dat": "per %s" % f})
                    nb_put(w2s, {"who": "worker", "mid": uobj.mid, "dat": "per %s" % f})
            print(l.rstrip(), end=e)

        p.wait()
        print(sect, p.returncode)
        if p.returncode == 0:
            print("mid %d done" % uobj.mid)
            set_flag(uobj, DONE)
            break
    else:
        print("mid %d failed" % uobj.mid)
        set_flag(uobj, FAIL)
    #w2s.put({"who": "worker", "mid": uobj.mid, "dat": "exit"})
    nb_put(w2s, {"who": "worker", "mid": uobj.mid, "dat": "exit"})
    cpto = uobj.opts.get("cpto")
    pcmd = cfg['server'].get('post_cmd')
    if uobj.flag == DONE and cpto and pcmd:
        cmd = '%s "%s" "%s"' % (pcmd, cpto, uobj.path)
        print(cmd)
        Popen(cmd, shell=True).wait()


class Worker(Process):
    def __init__(self, cfg, s2m, m2w, w2s):
        Process.__init__(self)
        self.cfg, self.s2m, self.m2w, self.w2s = cfg, s2m, m2w, w2s

    def run(self):
        while True:
            uobj = self.m2w.get()
            if uobj is None:
                break
            #sys.stdout = WFP("worker", self.s2m, uobj.mid)
            #sys.stderr = WFP("error", self.s2m, uobj.mid)
            print("Process mid=%d bg" % uobj.mid)
            work(self.cfg, uobj, self.w2s)
            print("Process mid=%d ed" % uobj.mid)
            #try:
            #    work(self.cfg, uobj)
            #except:
            #    t, l, tb = sys.exc_info()
            #    msg = "".join(traceback.format_exception(t, l, tb))
            #    print("Process mid=%d Fail\n%s" % (uobj.mid, msg))
            #else:
            #    print("Process mid=%d Stop" % uobj.mid)


class Manager(Process):
    def __init__(self, cfg):
        Process.__init__(self)
        self.s2m = Queue()      # message Manager receive from worker and svr
        self.m2w = Queue()      # message send to workers
        self.w2s = Queue(10)    # message send to svr from worker or manager (notice update web page)
        #self.t2m = Queue()      # svr thread send to manager, client queue
        self.cfg = cfg
        wnum = 1    # 3
        self.works = [0] * wnum
        for i in range(wnum):
            self.works[i] = Worker(self.cfg, self.s2m, self.m2w, self.w2s)
            self.works[i].start()

    def stop(self):
        for w in self.works:
            self.m2w.put(None)      # FIXME should call worker.Terminal?

    """
Video Site: bilibili.com
Title:      【BD‧1080P】【高分剧情】鸟人-飞鸟侠 2014【中文字幕】
Type:       Flash video (video/x-flv)
Size:       3410.85 MiB (3576536465 Bytes)

Downloading 【BD‧1080P】【高分剧情】鸟人-飞鸟侠 2014【中文字幕】.flv ...
  0.7% ( 22.2/3410.9MB) [#
    """
    def run(self):
        # reset DB flags
        kuos = get_by_flag(WORK)
        for uo in kuos:
            set_flag(uo, STOP)
        tuos = get_by_flag(WAIT)
        for uo in tuos:
            set_flag(uo, STOP)

        while True:
            msg = self.s2m.get()
            print("pid=%s, self.s2m.get=%s" % (os.getpid(), repr(msg)))
            who = msg.get('who')
            if who == 'worker':
                self.handle_mid(msg['mid'], msg['dat'])
            elif who == 'svr':
                #self.m2w.put(msg['mid'])
                self.m2w.put(pick_url(msg['mid']))
            elif who == 'clt':
                #self.w2s.put(msg)
                nb_put(self.w2s, msg)
            elif who == 'error':
                sys.stderr.write(msg['dat'])   # FIXME
                sys.stderr.write("\n")
            else:
                sys.stderr.write("Unknow msg:\n")
                sys.stderr.write(msg)
                sys.stderr.write("\n")

    def handle_mid(self, mid, dat):
        print("handle_mid", dat)
        #if dat.startswith("Process "):
        #    dd = dat.split()
        #    act = dd[2].lower()
        #    print("mid=%s, act=%s" % (mid, act))
        #    set_flag(mid, act)
        #elif dat.startswith("Downloading "):
        #    print("mid=[%s]" % mid)
        #    update_filename(mid, dat[12:-5])
