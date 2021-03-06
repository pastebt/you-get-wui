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
from threading import Thread #as Process
from queue import Queue, Full, Empty
from urllib.parse import quote, unquote, urlparse

from bottle import template

from db import UOBJ
from db import WORK, WAIT, STOP, DONE, FAIL
from db import pick_url, update_filename,  short_it
from db import get_act_fln, set_db_flag, get_by_flag


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


def set_flag(s2m, uobj, flag):
    i = uobj
    if isinstance(uobj, UOBJ):
        i = uobj.mid
        uobj.flag = flag
    set_db_flag(i, flag)
    act, fln = get_act_fln(flag)
    s2m.put({"who": "worker", "mid": i, "act": "flag", #"data": fln})
             "data":  template("""<a href="#{{mid}}flag" onclick="return mid_act({{mid}}, '{{act}}');">{{name}}</a>""", mid=i, act=act, name=fln)})


def show_title(uobj):
    return template("""<a title="{{url.updt}}"
                %if url.flag == done:
                    href="/rest?mid={{url.mid}}&amp;act=play" target='_blank'
                %end
                >{{url._short_name}}</a>""", url=uobj, done=DONE)


def show_tr_inner(uobj):
    #print("uobj=", uobj)
    t = show_title(uobj)
    return template("""<td id="td_name_{{url.mid}}"> {{!til}} </td>
                       <td> <a href="{{url.url}}" target='_blank'>{{url._short_url}}</a> </td>
                       <td id="td_flag_{{url.mid}}"> <a href="#{{url.mid}}flag" onclick="return mid_act({{url.mid}}, '{{url._flag_act}}');">{{url._flag_name}}</a> </td>
                       <td id="td_func_{{url.mid}}">
                       <a href="#{{url.mid}}del" onclick="return mid_act({{url.mid}}, 'del');">
                       del</a>
                       <a href="#{{url.mid}}edit" onclick="return mid_act({{url.mid}}, 'edit');">
                       edit</a>
                       </td>""", url=uobj, til=t)


def try_one_downloader(sect, uobj, s2m):
    got_til = ""
    out = uobj.opts.get("dest")
    if not out:
        out = './'
    pls = {"true": "-p", "none": "-P"}.get(uobj.opts.get("plst"), "")
    cpt = uobj.opts.get("cpto", "")
    dn  = sect['dir']
    til = sect['til']
    per = sect['per']
    upd = "^uploaded ([.0-9]+).*$"
    cmd = sect['cmd'].format(URL=uobj.url, OUTDIR=out, PLAYLIST=pls,
                             TITLE=uobj.name.strip(), POSTURI=cpt)
    cmd = "cd %s && %s" % (dn, cmd)
    if sect == 'download_dwm' and len(uobj.name) > 2:
        cmd = cmd + " --title '%s'" % uobj.name
    print("cmd =", cmd)
    p = Popen(cmd, shell=True, bufsize=1,
              universal_newlines=True, stdout=PIPE, stderr=STDOUT)
    c = ""
    for l in p.stdout:
        e = "\n"
        t = find_til(til, l)
        if t:
            got_til = t
            print("got title:", got_til)
            update_filename(uobj, os.path.join(dn, out),
                            os.path.basename(got_til))
            s2m.put({"who": "worker", "mid": uobj.mid,
                     "act": "title", "data": show_title(uobj)})
        else:
            for pat, nam in ((per, "dn"), (upd, "up")):
                f = find_til(pat, l)
                if f:
                    e = "\r"
                    if f != c:
                        c = f
                        s2m.put({"who": "worker", "mid": uobj.mid,
                                 "act": "per", "data": "%s %s%%" % (nam, f)})
            
        print(l.rstrip(), end=e)

    p.wait()
    return p.returncode, got_til


def upload_to(cmd, s2m, uobj):
    p = Popen(cmd, shell=True, bufsize=1,
              universal_newlines=True, stdout=PIPE, stderr=STDOUT)
    s = ""
    for l in p.stdout:
        m = l.strip()
        if m != s:
            s = m
            s2m.put({"who": "worker", "mid": uobj.mid,
                     "act": "per", "data": "up %s%%" % m})
    p.wait()
    if p.returncode ==0:
        set_flag(s2m, uobj, DONE)
    else:
        set_flag(s2m, uobj, FAIL)


def work(cfg, uobj, s2m):
    set_flag(s2m, uobj, WORK)
    for sect in cfg.sections():
        if not sect.startswith('download_'):
            continue
        retcode, got_til = try_one_downloader(cfg[sect], uobj, s2m)
        print(sect, retcode, got_til)
        if retcode == 0 and got_til:
            print("mid %d done" % uobj.mid)
            set_flag(s2m, uobj, DONE)
            s2m.put({"who": "worker", "mid": uobj.mid,
                     "act": "title", "data": show_title(uobj)})
            break
    #if not got_til or retcode != 0:
    else:
        #print("mid %d failed, retcode=%d, til=%s" % (
        #       uobj.mid, retcode, got_til))
        print("mid %d failed" % uobj.mid)
        set_flag(s2m, uobj, FAIL)

    if "POSTURI" in cfg[sect]['cmd']:
        return

    cpto = uobj.opts.get("cpto")
    pcmd = cfg['server'].get('post_cmd')
    if uobj.flag == DONE and cpto and pcmd:
        cmd = '%s "%s" "%s"' % (pcmd, cpto, uobj.path)
        print(cmd)
        #Popen(cmd, shell=True).wait()
        upload_to(cmd, s2m, uobj)


class Worker(Thread):
    def __init__(self, cfg, s2m, m2w):
        Thread.__init__(self)
        self.cfg, self.s2m, self.m2w = cfg, s2m, m2w

    def run(self):
        while True:
            uobj = self.m2w.get()
            if uobj is None:
                break
            #print("Process mid=%d bg" % uobj.mid)
            work(self.cfg, uobj, self.s2m)
            #print("Process mid=%d ed" % uobj.mid)


class Manager(Thread):
    def __init__(self, cfg):
        Thread.__init__(self)
        self.s2m = Queue()      # message Manager receive from worker and svr
        self.m2w = Queue()      # message send to workers
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
        self.notice_all([{"seq": self.seq}])

    def run(self):
        # reset DB flags
        kuos = get_by_flag(WORK)
        for uo in kuos:
            set_db_flag(uo.mid, STOP)
        tuos = get_by_flag(WAIT)
        for uo in tuos:
            set_db_flag(uo.mid, STOP)

        # web page change logging, sequence id, element id and content html
        # {"seq": seq_id, "act": "action", "elm": "elm_id", "data": "data"}
        # seq                   # only update seq id, not act
        # seq, act              #
        # seq, act, elm         # act: del, remove elm
        # seq, act, elm, data   # act: set, data is inner_html for elm
        #                       # act: new
        self.logs = []
        # web page reqest queue list
        self.reqs = []
        # sequence id
        self.seq = 1
        while True:
            self.seq += 1
            try:
                msg = self.s2m.get(timeout=10)
            except Empty:
                self.update_logs({})
                continue
            if msg is None:
                break
            #print("self.s2m.get = ", msg)
            # who: svr
            #   act:start
            #       del
            #       new
            # who: clt
            #      ask
            # who: worker
            #      flag
            #      title
            #      per
            who = msg.get('who')
            if who == 'worker':
                self.update_logs(msg)
            elif who == 'svr':
                mid, act = msg.get('mid'), msg.get('act')
                if act == 'start':
                    set_flag(self.s2m, mid, WAIT)
                    self.m2w.put(pick_url(mid))
                elif act in ('del', 'add'):
                    self.update_logs(msg)
            elif who == 'clt':  # http client send request
                self.query_logs(msg)
            else:
                print("Unknow msg:", file=sys.stderr)
                print(msg, file=sys.stderr)
                print("", file=sys.stderr)

    def notice_all(self, res):
        #print("notice_all self.reqs =", self.reqs)
        for r in self.reqs:
            q = r.get("req")
            if q:
                q.put(res)
        self.reqs = []

    def query_logs(self, msg):
        #print("query_logs, msg =", msg)
        seq = msg['seq']
        if not self.logs or seq == self.logs[-1]['seq']:
            self.reqs.append(msg)
            return
        ret = []
        if seq == 0:
            ret.append({"seq": self.logs[-1]['seq']})
        else:
            for l in self.logs:
                if l['seq'] > seq:
                    ret.append(l)
        #print("ret =", ret)
        q = msg.get("req")
        if q:
            q.put(ret)

    def update_logs(self, msg):
        l = {"seq": self.seq}
        ls = [l]
        act = msg.get('act')
        if act == 'add':
            uo = pick_url(msg['mid'])
            #l['act'] = 'set'
            #l['elm'] = 'post_msg'
            #l['data'] = 'posted %d' %  msg['mid']   # TODO
            #self.seq += 1
            l = {"seq": self.seq, 'act': 'add',
                 'elm':'tr_%s' % msg['mid'],
                 'data': show_tr_inner(uo)}
            ls.append(l)
        elif act == 'del':
            l['act'] = 'del'
            l['elm'] = "tr_%s" % msg['mid']
        elif act in ('flag', 'per'):
            l['act'] = "set"
            l['elm'] = "td_flag_%s" % msg['mid']
            l['data'] = msg['data']
        elif act == 'title':
            l['act'] = "set"
            l['elm'] = "td_name_%s" % msg['mid']
            l['data'] = msg['data']

        self.logs += ls
        self.notice_all(ls)
