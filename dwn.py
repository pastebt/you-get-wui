#! /usr/bin/python3

import os
import sys
import select
import traceback
from multiprocessing import Pipe, Queue, Process
from subprocess import Popen, STDOUT, PIPE


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


def work(cfg, uobj):
    for sect in cfg.sections():
        if not sect.startswith('download_'):
            continue
        dn = cfg[sect]['dir']
        cmd = cfg[sect]['cmd'].format(URL=uobj.url, OUTDIR='./')
        p = Popen("cd %s && %s" % (dn, cmd), shell=True) #, stderr=STDOUT, stdout=PIPE)
        #for l in p.read():
        #    print(l, end="")
        p.wait()
        if p.returncode == 0:
            set_flag(uobj.mid, DONE)
            break
    else:
        set_flag(uobj.mid, FAIL)


class Worker(Process):
    def __init__(self, cfg, s2m, m2w):
        Process.__init__(self)
        self.cfg, self.s2m, self.m2w = cfg, s2m, m2w

    def run(self):
        while True:
            uobj = self.m2w.get()
            if uobj is None:
                break
            sys.stdout = WFP("worker", self.s2m, uobj.mid)
            sys.stderr = WFP("error", self.s2m, uobj.mid)
            print("Process mid=%d Start" % uobj.mid)
            try:
                work(self.cfg, uobj)
            except:
                t, l, tb = sys.exc_info()
                msg = "".join(traceback.format_exception(t, l, tb))
                print("Process mid=%d Fail\n%s" % (uobj.mid, msg))
            else:
                print("Process mid=%d Stop" % uobj.mid)


class Manager(Process):
    def __init__(self, cfg):
        Process.__init__(self)
        self.s2m = Queue()  # message Manager receive from worker and svr
        self.m2w = Queue()  # message send to works
        self.cfg = cfg
        wnum = 1    # 3
        self.works = [0] * wnum
        for i in range(wnum):
            self.works[i] = Worker(self.cfg, self.s2m, self.m2w)
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
            set_flag(uo.mid, STOP)
        tuos = get_by_flag(WAIT)
        for uo in tuos:
            set_flag(uo.mid, STOP)

        while True:
            msg = self.s2m.get()
            #print("pid=%s, self.s2m.get=%s" % (os.getpid(), repr(msg)))
            who = msg.get('who')
            if who == 'worker':
                self.handle_mid(msg['mid'], msg['dat'])
            elif who == 'svr':
                #self.m2w.put(msg['mid'])
                self.m2w.put(pick_url(msg['mid']))
            elif who == 'error':
                sys.stderr.write(msg['dat'])   # FIXME
                sys.stderr.write("\n")
            else:
                sys.stderr.write("Unknow msg:\n")
                sys.stderr.write(msg)
                sys.stderr.write("\n")

    def handle_mid(self, mid, dat):
        print(dat)
        if dat.startswith("Process "):
            dd = dat.split()
            act = dd[2].lower()
            print("mid=%s, act=%s" % (mid, act))
            set_flag(mid, act)
        elif dat.startswith("Downloading "):
            print("mid=[%s]" % mid)
            update_filename(mid, dat[12:-5])
