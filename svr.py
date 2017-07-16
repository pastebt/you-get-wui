#! /usr/bin/python3

import os
import sys
import configparser
from urllib.parse import quote
from wsgiref.simple_server import WSGIServer

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
        </head>
        <body>
        """


def html_foot():
    return "</body></html>"


def html_form():
    return """
        <form action="/" method="post">
        <table>
            <tr><td>URL:</td>
                <td><input name="aviurl" type="text" size=60 /></td>
            </tr>
            <tr><td>TITLE:</td>
                <td><input name="avitil" type="text" size=60 /></td>
            </tr>
            <tr><td>DEST:</td>
                <td><input name="destdn" type="text" size=60 /></td>
            </tr>
            <tr><td> </td>
                <td><input value="Submit" type="submit" name="sub"/>
                    <input value="Start" type="submit" name="sub"/></td>
            </tr>
        </table>
        </form>
        <div id="url_list"></div>

        <script>
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
            request.open('GET', '/list', true);
            request.send()
        } else {
            // We reached our target server, but it returned an error
        }
        };

        request.onerror = function() {
            // There was a connection error of some sort
        };

        request.send();
        </script>

        """


def html_list():
    return template("""
        %if urls:
        <table border=1 width="95%">
        <thead><tr align="center">
            <td>Title</td>
            <td>add date</td>
            <td>url</td>
            <td>flag</td>
            <td>del</td>
        <tr></thead>
        <tbody>
        %for url in urls:
            <tr>
                <td> {{url.name}} </td>
                <td> {{url.updt}} </td>
                <td> <a href="{{url.url}}">{{url._short_url}}</a> </td>
                <td> <a href="{{url._flag_html}}">{{url._flag_name}}</a> </td>
                <td> <a href="/rest?mid={{url.mid}}&amp;act=del">del</a> </td>
            </tr>
        %end
        </tbody>
        </table>
        %end
        """, urls=query_urls())


def html_play_head():
    return """
        <html>
        <head><title>You_Get</title>
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
        """


def html_play(mid):
    return template("""
        <!-- video src="/play/{{mid}}" controls autoplay name="media" style="display: block; margin: auto;" -->
        <video src="/play/{{mid}}" controls autoplay class="center">
        <p>Your browser doesn't support HTML5 video.
           Here is a <a href="/play/{{mid}}">link to the video</a> instead.</p> 
        </video>
        """, mid=mid)



def conv(src):
    return [ord(x) for x in src]


def start_one(mid):
    set_flag(mid, "wait")
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
        return html_play_head() + html_play(mid) + html_foot()
    redirect("/")


@get('/list')
def list():
    try:
        w2s.get(timeout=10)
        print("got from w2s")
    except Exception as e:
        print(e)
    return html_list()


@get('/<:re:.*>')
def index():
    s2m.put({"who": "clt"})
    #return html_head() + html_form() + html_list() + html_foot()
    return html_head() + html_form() + html_foot()


def req_str(name):
    return bytearray(conv(request.forms.get(name))).decode("utf8")


@post('/')  # or @route('/login', method='POST')
def do_post():
    sub = request.forms.get('sub')
    print("sub =", sub)
    aviurl = request.forms.get('aviurl')
    #rtitle = request.forms.get('avitil')
    #print("rtitle =", rtitle.decode("utf8"))
    #destdn = request.forms.get('destdn')
    #avitil = bytearray(conv(rtitle)).decode("utf8")
    destdn = req_str('destdn')
    avitil = req_str('avitil')
    
    i = add_one_url(aviurl, avitil, destdn)
    print("i =", i, "destdn =", destdn)
    #print("post pid=%s, s2m=%s" % (os.getpid(), str(s2m)))
    if sub == 'Start':
        start_one(i)
    body = template('Got:<br>Title: {{title}}<br>URL:{{url}}',
                    title=avitil, url=aviurl)
    s2m.put({"who": "clt"})
    #return html_head() + body + html_form() + html_list() + html_foot()
    return html_head() + body + html_form() + html_foot()


#class FWSGISvr(ForkingMixIn, WSGIServer):
class FWSGISvr(ThreadingMixIn, WSGIServer):
    pass


class MySvr(WSGIRefServer):
    def __init__(self, host='', port=8080, **options):
        options['server_class'] = FWSGISvr
        WSGIRefServer.__init__(self, host, port, **options)


#def notice_all():
#    while True:
#        try:
#            w2s.get(timeout=10)
#        except Exception as e:
#            print(e)
#        print("send notice to all")
#        cdn.notify_all()


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
