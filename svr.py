#! /usr/bin/python3

import os
import sys
import json
import configparser
from queue import Queue
from urllib.parse import quote
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler

from socketserver import ThreadingMixIn

from bottle import WSGIRefServer
from bottle import get, post, request
from bottle import run, template, route, redirect
from bottle import static_file

from dwn import Manager
from db import init_db #, set_flag
from db import pick_url, query_urls
from db import add_one_url, del_one_url


def html_head():
    return """
        <html>
        <head><title>You_Get</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf8">
        <style>
        div#url_list tbody tr:hover  {
            background-color:yellow;
        }
        </style>
        <script>

        var seq = 0;
        function talk() {
            alert("start talk");
            var req = new XMLHttpRequest();
            req.open('GET', '/rest?mid=' + seq + "&act=talk", true);
            req.onload = function() {
            //alert(req.status);
            if (req.status >= 200 && req.status < 400) {
                // Success!
                var datas = JSON.parse(req.responseText);
                //alert(datas);
                for (i in datas) {
                    proc_one(datas[i]);
                }
                alert("after seq =" + seq);
                req.open('GET', '/rest?mid=' + seq + "&act=talk", true);
                alert("callback send");
                req.send();
                //talk();
            } else {
                // We reached our target server, but it returned an error
                //if (myObj.nam == undefined) 
                alert("talk failed");
            }
            };
            alert("send");
            req.send();
        }

        function proc_one(msg) {
            if (msg.seq == undefined) { return; }
            seq = msg.seq;
            alert("seq =" + seq);
            switch (msg.act) {
            case "del":
                var elm = document.getElementById(msg.elm);
                elm.parentNode.removeChild(elm);
                break;
            case "set":
                var elm = document.getElementById(msg.elm);
                elm.innerHTML = msg.data;
                break;
            case undefined:
                break;
            default:
                alert("Unknown act: " + msg.act);
            }
        }

        function mid_act(mid, act) {
            var req = new XMLHttpRequest();
            req.open('GET', '/rest?mid=' + mid + "&act=" + act, true);
            req.send();
            //reload_urls_list();
        }

        function reload_urls_list() {
            var listobj = document.getElementById('url_list');
            //alert(listobj);
            // leftSection.parentNode.removeChild(leftSection);
            var request = new XMLHttpRequest();
            request.open('GET', '/list', true);
            request.onload = function() {
            //alert(request.status);
            if (request.status >= 200 && request.status < 400) {
                // Success!
                //var data = JSON.parse(request.responseText);
                //alert(request.responseText);
                listobj.innerHTML = request.responseText;
                var ww = document.getElementById('urls_tb').getAttribute("ww");
                if (ww == 1) {
                    //alert(ww)
                    request.open('GET', '/list', true);
                    request.send();
                }
            } else {
            // We reached our target server, but it returned an error
            }
            };

            request.onerror = function() {
                // There was a connection error of some sort
            };

            request.send();
        }
        </script>
        </head>
        <body>
        """


def html_form(msg):
    pcmd = cfg['server'].get('post_cmd')
    if pcmd:
        cpto = """
            <tr><td>CPTO:</td>
                <td><input name="copyto" type="text" size=60 /></td>
            </tr>"""
    else:
        cpto = ""

    return msg + """
        <form action="/" method="post">
        <table>
            <tr><td>URL:</td>
                <td><input name="aviurl" type="text" size=60 /></td>
            </tr>
            <tr><td>TITLE:</td>
                <td><input name="avitil" type="text" size=60 /></td>
            </tr>
            <tr><td>PATH:</td>
                <td><input name="destdn" type="text" size=60 /></td>
            </tr>""" + cpto + """
            <tr><td> </td>
                <td><input value="Submit" type="submit" name="sub"/>
                    <input value="Start" type="submit" name="sub"/></td>
            </tr>
        </table>
        </form>
        <div id="url_list">""" + html_list() + """</div>
        <script>talk();</script>
    </body></html>
        """


def html_list():
    urls, ww = query_urls()
    #print("ww =", ww)
    return template("""
        %if urls:
        <table border=1 width="95%" id="urls_tb" ww={{ww}}>
        <thead><tr align="center">
            <td>Title</td>
            <td>url</td>
            <td>flag</td>
            <td>del</td>
        <tr></thead>
        <tbody>
        %for url in urls:
            <tr id="tr_{{url.mid}}">
                <td id="td_name_{{url.mid}}"> <a title="{{url.updt}}"
                %if url._flag_name == "Done":
                    href="/rest?mid={{url.mid}}&act=play" target='_blank'
                %end
                >{{url.name}}</a> </td>
                <td> <a href="{{url.url}}" target='_blank'>{{url._short_url}}</a> </td>
                <td id="td_flag_{{url.mid}}"> <a href="#{{url.mid}}flag" onclick="mid_act({{url.mid}}, '{{url._flag_act}}');">{{url._flag_name}}</a> </td>
                <td id="td_func_{{url.mid}}">
                <a href="#{{url.mid}}del" onclick="mid_act({{url.mid}}, 'del');">
                del</a> </td>
            </tr>
        %end
        </tbody>
        </table>
        %end
        """, urls=urls, ww=ww)


def html_play(mid):
    uobj = pick_url(mid)
    name = os.path.basename(uobj.path)
    #controls autoplay style="display: block; margin: auto;"
    return template("""
        <html>
        <head><title>{{name}}</title>
        <style>
        .center {
            margin: 0;
            position: absolute;
            top: 50%;
            left: 50%;
            -ms-transform: translate(-50%, -50%);
            transform: translate(-50%, -50%);
        }
        </style>
        </head>
        <body style="background-color: rgb(0,0,0);">
        <video src="/play/{{mid}}" controls autoplay class="center">
        <p>Your browser doesn't support HTML5 video.
           Here is a <a href="/play/{{mid}}">link to the video</a> instead.</p> 
        </video>
        </body>
        </html>""", name=name, mid=mid)


def conv(src):
    return [ord(x) for x in src]


#def start_one(mid):
#    set_flag(mid, 'wait')
#    s2m.put({"who": "clt", "mid": mid})


@route('/play/<mid>')
def server_static(mid):
    uobj = pick_url(mid)
    if uobj and uobj.path:
        return static_file(os.path.basename(uobj.path),
                           root=os.path.dirname(uobj.path))


@route('/movies/<mid>')
def server_static(mid):
    uobj = pick_url(mid)
    if uobj and uobj.path:
        #return static_file(uobj.path, root='../')
        return static_file(os.path.basename(uobj.path),
                           root=os.path.dirname(uobj.path),
                           download=quote(os.path.basename(uobj.path)))
                           #download=True)


@get('/rest')
def rest():
    mid = request.query.mid
    act = request.query.act
    print("rest: mid=%s, act=%s" % (mid, act))
    #print("rest: pid=%s, s2m=%s" % (os.getpid(), str(s2m)))
    msg = {"who": "clt", "mid": mid, "act": act}
    if act in ("start",):
        #start_one(mid)
        msg["who"] = "svr"
    elif act == 'del':
        del_one_url(mid)
    elif act == 'play':
        return html_play(mid)
    elif act == 'talk':
        q = Queue()
        try:
            mid = int(mid)
        except ValueError:
            mid = 0
        s2m.put({"who": "clt", "seq": mid, "req": q})
        r = q.get()
        return json.dumps(r)
    #redirect("/")
    s2m.put(msg)
    return ""


@get('/list')
def list():
    q = Queue()
    try:
        q.get(timeout=1)
    except Exception as e:
        print(e)
    return html_list()


@get('/<:re:.*>')
def index():
    s2m.put({"who": "clt"})
    return html_head() + html_form("")


def req_str(name):
    return bytearray(conv(request.forms.get(name, ""))).decode("utf8")


@post('/')  # or @route('/login', method='POST')
def do_post():
    sub = request.forms.get('sub')
    print("sub =", sub)
    aviurl = request.forms.get('aviurl', "").strip()
    avitil = req_str('avitil')
    destdn = req_str('destdn')
    copyto = req_str('copyto')
    
    if len(aviurl) > 4:
        opt = {'dest': destdn}
        if copyto:
            opt['cpto'] = copyto
        i = add_one_url(aviurl, avitil, opt)
        print("i =", i, "opts =", opt)
        if sub == 'Start':
            #start_one(i)
            s2m.put({"who": "svr", "mid": i, "act": 'start'})
        body = template('Got:<br>Title: {{title}}<br>URL:{{url}}',
                        title=avitil, url=aviurl)
    else:
        body = "Miss URL"
    s2m.put({"who": "clt"})
    return html_head() + html_form(body)


class FWSGISvr(ThreadingMixIn, WSGIServer):
    pass


class MyHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        #pass
        sys.stderr.write("%s - - [%s] %s\n" %
                     (self.client_address[0],
                      self.log_date_time_string(),
                      format%args))


class MySvr(WSGIRefServer):
    def __init__(self, host='', port=8080, **options):
        options['server_class'] = FWSGISvr
        options['handler_class'] = MyHandler
        WSGIRefServer.__init__(self, host, port, **options)


def usage():
    print('you-get-wui server')
    print('Usage:', sys.argv[0], '-c [wui.cfg]')
    print('')
    sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3) or sys.argv[1] != '-c':
        usage()
    cfgfn = "wui.cfg"
    if len(sys.argv) == 3:
        cfgfn = sys.argv[2]
    cfg = configparser.ConfigParser()
    cfg.read(cfgfn)

    init_db(cfg)
    mon = Manager(cfg)
    s2m = mon.s2m
    mon.start()
    run(server=MySvr, host='', port=int(cfg['server']['port']))
    mon.stop()
