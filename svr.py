#! /usr/bin/python3

import os
import sys
import configparser
from urllib.parse import quote
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler

from socketserver import ThreadingMixIn
#from socketserver import ForkingMixIn

from bottle import WSGIRefServer
from bottle import get, post, request
from bottle import run, template, route, redirect
from bottle import static_file

from dwn import Manager
from db import init_db, set_flag
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
        function mid_act(mid, act) {
            var req = new XMLHttpRequest();
            req.open('GET', '/rest?mid=' + mid + "&act=" + act, true);
            req.send();
            reload_urls_list();
        }

        function reload_urls_list() {
            var listobj = document.getElementById('url_list');
            //alert(listobj);
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
                    request.send()
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


def html_foot():
    return "</body></html>"


def html_form():
    pcmd = cfg['server'].get('post_cmd')
    if pcmd:
        cpto = """
            <tr><td>CPTO:</td>
                <td><input name="copyto" type="text" size=60 /></td>
            </tr>"""
    else:
        cpto = ""

    return """
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
        <div id="url_list"></div>
        <script>reload_urls_list();</script>
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
            <tr>
                <td> <a title="{{url.updt}}"
                %if url._flag_name == "Done":
                    href="/rest?mid={{url.mid}}&act=play" target='_blank'
                %end
                >{{url.name}}</a> </td>
                <td> <a href="{{url.url}}" target='_blank'>{{url._short_url}}</a> </td>
                <td> <a href="#{{url.mid}}flag" onclick="mid_act({{url.mid}}, '{{url._flag_act}}');">{{url._flag_name}}</a> </td>
                <td>
                <!-- a href="/rest?mid={{url.mid}}&amp;act=del" -->
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


def start_one(mid):
    set_flag(mid, 'wait')
    s2m.put({"who": "svr", "mid": mid})


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
        #return html_head() + html_play(uobj) + html_foot()


@get('/rest')
def rest():
    mid = request.query.mid
    act = request.query.act
    print("rest: mid=%s, act=%s" % (mid, act))
    #print("rest: pid=%s, s2m=%s" % (os.getpid(), str(s2m)))
    if act in ("start",):
        start_one(mid)
    elif act == 'del':
        del_one_url(mid)
    elif act == 'play':
        return html_play(mid)
    #redirect("/")
    s2m.put({"who": "clt"})
    return ""


@get('/list')
def list():
    try:
        w2s.get(timeout=10)
        #print("got from w2s")
    except Exception as e:
        print(e)
    return html_list()


@get('/<:re:.*>')
def index():
    s2m.put({"who": "clt"})
    #return html_head() + html_form() + html_list() + html_foot()
    return html_head() + html_form() + html_foot()


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
    #copyto = request.forms.get('copyto', "").strip()
    
    if len(aviurl) > 4:
        opt = {'dest': destdn}
        if copyto:
            opt['cpto'] = copyto
        i = add_one_url(aviurl, avitil, opt)
        print("i =", i, "opts =", opt)
        #print("post pid=%s, s2m=%s" % (os.getpid(), str(s2m)))
        if sub == 'Start':
            start_one(i)
        body = template('Got:<br>Title: {{title}}<br>URL:{{url}}',
                        title=avitil, url=aviurl)
    else:
        body = "Miss URL"
    s2m.put({"who": "clt"})
    #return html_head() + body + html_form() + html_list() + html_foot()
    return html_head() + body + html_form() + html_foot()


#class FWSGISvr(ForkingMixIn, WSGIServer):
class FWSGISvr(ThreadingMixIn, WSGIServer):
    pass


class MyHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass
        #sys.stderr.write("%s - - [%s] %s\n" %
        #             (self.client_address[0],
        #              self.log_date_time_string(),
        #              format%args))


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
    w2s = mon.w2s
    mon.start()
    run(server=MySvr, host='', port=int(cfg['server']['port']))
    mon.stop()
