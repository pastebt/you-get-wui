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
from db import init_db
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
            var req = new XMLHttpRequest();
            req.open('GET', '/rest?mid=' + seq + "&act=talk");
            req.onload = function() {
            if (req.status >= 200 && req.status < 400) {
                // Success!
                var datas = JSON.parse(req.responseText);
                for (i in datas) {
                    proc_one(datas[i]);
                }
                req.open('GET', '/rest?mid=' + seq + "&act=talk");
                req.send();
            } else {
                // We reached our target server, but it returned an error
                alert("talk failed");
            }
            };
            req.send();
        }

        function proc_one(msg) {
            //alert("msg.seq =" + msg.seq);
            //if (msg.seq == undefined) { return; }
            seq = msg.seq;
            //alert("seq =" + seq);
            switch (msg.act) {
            case "add":
                var bas = document.getElementById("urls_tbody");
                var itm = document.createElement("tr");
                itm.setAttribute("id", msg.elm);
                itm.innerHTML = msg.data;
                bas.insertBefore(itm, bas.childNodes[0]);
                break;
            case "del":
                var elm = document.getElementById(msg.elm);
                elm.parentNode.removeChild(elm);
                break;
            case "set":
                var elm = document.getElementById(msg.elm);
                elm.innerHTML = msg.data;
                break;
            case "edit":
                document.getElementById(msg.elm).value = msg.data;
                break;
            case undefined:
                break;
            default:
                alert("Unknown act: " + msg.act);
            }
        }

        function mid_act(mid, act) {
            var req = new XMLHttpRequest();
            req.open('GET', '/rest?mid=' + mid + "&act=" + act);
            if (act == "edit") {
                req.onload = function() {
                if (req.status >= 200 && req.status < 400) {
                    // Success!
                    var datas = JSON.parse(req.responseText);
                    for (i in datas) {
                        proc_one_local(datas[i]);
                    }
                } else {
                    // We reached our target server, but it returned an error
                    alert("talk failed");
                }};
            }
            req.send();
            return false;
        }

        function proc_one_local(msg) {
            switch (msg.act) {
            case "edit":
                document.getElementById(msg.elm).value = msg.data;
                break;
            case undefined:
                break;
            default:
                alert("Local Unknown act: " + msg.act);
            }
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
                <td><input name="copyto" id="copyto" type="text" size=60 /></td>
            </tr>"""
    else:
        cpto = ""

    return msg + """
        <script>
        function add_new(sub) {
            var fm = document.querySelector("form");
            var fd = new FormData(fm);
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "/");
            xhr.onloadend = function() {
            if (xhr.status >= 200 && xhr.status < 400) {
                // Success!
                var m = document.getElementById("post_msg");
                m.innerHTML = xhr.responseText;
                document.getElementById("aviurl").value = "";
                document.getElementById("avitil").value = "";
            }};
            fd.append("sub", sub);
            xhr.send(fd);
            return false;
        }

        </script>
        <div id="post_msg"></div>
        <form action="/" method="post">
        <table>
            <tr><td>URL:</td>
                <td><input name="aviurl" id="aviurl" type="text" size=60 /></td>
            </tr>
            <tr><td>TITLE:</td>
                <td><input name="avitil" id="avitil" type="text" size=60 /></td>
            </tr>
            <tr><td>PATH:</td>
                <td><input name="destdn" id="destdn" type="text" size=60 /></td>
            </tr>""" + cpto + """
            <tr><td> </td>
                <td><input value="Submit" type="submit" name="sub" onclick="return add_new('Submit');"/>
                    <input value="Start" type="submit" name="sub" onclick="return add_new('Start');"/></td>
            </tr>
        </table>
        </form>
        <div id="url_list">""" + html_list() + """</div>
        <script>talk();</script>
    </body></html>
        """


def html_list():
    urls, ww = query_urls()
    return template("""
        %if urls:
        <table border=1 width="95%" id="urls_tb" ww={{ww}}>
        <thead><tr align="center">
            <td>Title</td>
            <td>url</td>
            <td>flag</td>
            <td>func</td>
        <tr></thead>
        <tbody id="urls_tbody">
        %for url in urls:
            <tr id="tr_{{url.mid}}">
                <td id="td_name_{{url.mid}}"> <a title="{{url.updt}}"
                %if url._flag_name == "Done":
                    href="/rest?mid={{url.mid}}&amp;act=play" target='_blank'
                %end
                >{{url._short_name}}</a> </td>
                <td> <a href="{{url.url}}" target='_blank'>{{url._short_url}}</a> </td>
                <td id="td_flag_{{url.mid}}"> <a href="#{{url.mid}}flag" onclick="return mid_act({{url.mid}}, '{{url._flag_act}}');">{{url._flag_name}}</a> </td>
                <td id="td_func_{{url.mid}}">
                <a href="#{{url.mid}}del" onclick="return mid_act({{url.mid}}, 'del');">
                del</a>
                <a href="#{{url.mid}}edit" onclick="return mid_act({{url.mid}}, 'edit');">
                edit</a>
                </td>
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
    mid = int(request.query.mid)
    act = request.query.act
    #print("rest: mid=%s, act=%s" % (mid, act))
    msg = {"who": "svr", "mid": mid, "act": act}
    if act == "start":
        pass
    elif act == 'del':
        del_one_url(mid)
    elif act == 'play':
        return html_play(mid)
    elif act == 'talk':
        q = Queue()
        s2m.put({"who": "clt", "seq": mid, "req": q})
        r = q.get()
        return json.dumps(r)
    elif act == 'edit':
        uobj = pick_url(mid)
        ret = [{"elm": "aviurl", "act": "edit", "data": uobj.url},
               {"elm": "avitil", "act": "edit", "data": uobj.name},
               {"elm": "destdn", "act": "edit", "data": uobj.opts.get("dest")},
               {"elm": "copyto", "act": "edit", "data": uobj.opts.get("cpto")},
               ]
        return json.dumps(ret)
    #redirect("/")
    s2m.put(msg)
    return ""


@get('/<:re:.*>')
def index():
    return html_head() + html_form("")


def req_str(name):
    print(name, "=", repr(request.forms.get(name, "")))
    return request.forms.get(name, "")


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
        s2m.put({"who": "svr", "mid": i, "act": 'add'})
        if sub == 'Start':
            s2m.put({"who": "svr", "mid": i, "act": 'start'})

        body = template('Got:<br>Title: {{title}}<br>URL:{{url}}',
                        title=avitil, url=aviurl)
    else:
        body = "Miss URL"
    return body


class FWSGISvr(ThreadingMixIn, WSGIServer):
    pass


class MyHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        return
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
