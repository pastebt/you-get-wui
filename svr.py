#! /usr/bin/python3

import sys
import configparser
from wsgiref.simple_server import WSGIServer
from socketserver import ForkingMixIn, ThreadingMixIn

from bottle import WSGIRefServer
from bottle import get, post, request
from bottle import run, template, route, redirect
from bottle import static_file

from dwn import Manager
from db import init_db, set_flag
from db import pick_url, add_one_url, query_urls


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
            <tr><td> </td><td><input value="Submit" type="submit" /></td>
            </tr>
        </table>
        </form>
        """


def html_list():
    return template("""
        <% from db import STOP, WAIT, WORK, FAIL, DONE %>
        %if urls:
        <table border=1>
        <thead><tr>
            <td>Title</td>
            <td>add date</td>
            <td>url</td>
            <td>flag</td>
        <tr></thead>
        <tbody>
        %for url in urls:
            <tr>
                <td>{{url.name}}</td>
                <td>{{url.updt}}</td>
                <td>{{url.url}}</td>
                <td>\\\\
                    %if url.flag is None or url.flag == STOP:
"""                  """<a href=/rest?mid={{url.mid}}&act=start>start</a>\\\\
                    %elif url.flag == WAIT:
"""                  """<a href=/rest?mid={{url.mid}}&act=start>waiting</a>\\\\
                    %elif url.flag == WORK:
"""                  """<a href=/rest?mid={{url.mid}}&act=start>working</a>\\\\
                    %elif url.flag == FAIL:
"""                  """<a href=/rest?mid={{url.mid}}&act=start>retry</a>\\\\
                    %elif url.flag == DONE:
"""                  """<a href=/movies/{{url.mid}}>Done</a>\\\\
                    %else:
"""                  """FF\\\\
                    %end
"""          """</td>
            </tr>
        %end
        </tbody>
        </table>
        %end
        """, urls=query_urls())


def conv(src):
    return [ord(x) for x in src]


@route('/movies/<mid>')
def server_static(mid):
    uobj = pick_url(mid)
    if uobj:
        return static_file(uobj.path, root='../')


@get('/rest')
def rest():
    mid = request.query.mid
    act = request.query.act
    print("rest: mid=%s, act=%s" % (mid, act))
    if act in ("start",):
        set_flag(mid, "wait")
        s2m.put({"who": "svr", "mid": mid})
    redirect("/")


@get('/<:re:.*>')
def index():
    return html_head() + html_form() + html_list() + html_foot()


@post('/')  # or @route('/login', method='POST')
def do_post():
    aviurl = request.forms.get('aviurl')
    rtitle = request.forms.get('avitil')
    avitil = bytearray(conv(rtitle)).decode("utf8")

    add_one_url(aviurl, avitil)
    body = template('Got:<br>Title: {{title}}<br>URL:{{url}}',
                    title=avitil, url=aviurl)
    return html_head() + body + html_form() + html_list() + html_foot()


#class FWSGISvr(ForkingMixIn, WSGIServer):
class FWSGISvr(ThreadingMixIn, WSGIServer):
    pass


class MySvr(WSGIRefServer):
    def __init__(self, host='', port=8080, **options):
        options['server_class'] = FWSGISvr
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
    mon = Manager()
    s2m = mon.s2m
    mon.start()
    run(server=MySvr, host='', port=int(cfg['server']['port']))
    mon.stop()
