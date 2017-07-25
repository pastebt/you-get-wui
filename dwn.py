#! /usr/bin/python3

import os
import re
import sys
import select
import traceback
import queue
from http.client import HTTPConnection
from subprocess import Popen, STDOUT, PIPE
#from multiprocessing import Queue, Process
from threading import Thread as Process
from queue import Queue
from urllib.parse import quote, unquote, urlparse

from db import WORK, WAIT, STOP, DONE, FAIL
from db import pick_url, update_filename, set_flag, get_by_flag


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
            return m.group(1).strip()
    return None


def nb_put(q, dat):
    try:
        q.put_nowait(dat)
    except queue.Full:
        pass


def work(cfg, uobj, s2m):
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
        if sect == 'download_dwm' and len(uobj.name) > 2:
            cmd = cmd + " --title '%s'" % uobj.name
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
                s2m.put({"who": "worker", "mid": uobj.mid, "dat": "got title"})
            else:
                f = find_til(per, l)
                if f:
                    e = "\r"
                    s2m.put({"who": "worker", "mid": uobj.mid, "dat": "per %s" % f})
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
    s2m.put({"who": "worker", "mid": uobj.mid, "dat": "exit"})
    cpto = uobj.opts.get("cpto")
    pcmd = cfg['server'].get('post_cmd')
    if uobj.flag == DONE and cpto and pcmd:
        cmd = '%s "%s" "%s"' % (pcmd, cpto, uobj.path)
        print(cmd)
        Popen(cmd, shell=True).wait()


class Worker(Process):
    def __init__(self, cfg, s2m, m2w):
        Process.__init__(self)
        self.cfg, self.s2m, self.m2w = cfg, s2m, m2w

    def run(self):
        while True:
            uobj = self.m2w.get()
            if uobj is None:
                break
            #sys.stdout = WFP("worker", self.s2m, uobj.mid)
            #sys.stderr = WFP("error", self.s2m, uobj.mid)
            print("Process mid=%d bg" % uobj.mid)
            work(self.cfg, uobj, self.s2m)
            print("Process mid=%d ed" % uobj.mid)


class Manager(Process):
    def __init__(self, cfg):
        Process.__init__(self)
        self.s2m = Queue()      # message Manager receive from worker and svr
        self.m2w = Queue()      # message send to workers
        #self.t2m = Queue()      # svr thread send to manager, client queue
        self.cfg = cfg
        wnum = 1    # 3
        self.works = [0] * wnum
        for i in range(wnum):
            self.works[i] = Worker(self.cfg, self.s2m, self.m2w)
            self.works[i].start()

    def stop(self):
        for w in self.works:
            self.m2w.put(None)      # FIXME should call worker.Terminal?
        self.s2m.put(None)

    def run(self):
        # reset DB flags
        kuos = get_by_flag(WORK)
        for uo in kuos:
            set_flag(uo, STOP)
        tuos = get_by_flag(WAIT)
        for uo in tuos:
            set_flag(uo, STOP)

        self.logs = []   # web page change logging, sequence id, element id and content html

        while True:
            msg = self.s2m.get()
            if msg is None:
                break
            print("pid=%s, self.s2m.get=%s" % (os.getpid(), repr(msg)))
            who = msg.get('who')
            if who == 'worker':
                self.update_logs(msg)
            elif who == 'svr':
                mid, act = msg.get('mid'), msg.get('act')
                if act == 'start':
                    set_flag(mid, 'wait')
                    self.m2w.put(pick_url(mid))
            elif who == 'clt':  # http client send request
                self.query_logs(msg)
            elif who == 'error':
                print(msg, file=sys.stderr)
                print("", file=sys.stderr)
            else:
                print("Unknow msg:", file=sys.stderr)
                print(msg, file=sys.stderr)
                print("", file=sys.stderr)

    def query_logs(self, msg):
        pass

    def update_logs(self, msg):
        pass

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
