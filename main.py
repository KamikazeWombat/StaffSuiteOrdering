
import cherrypy

from config import cfg, c
from shared_functions import load_departments, first_older_than_second, do_upgrade
from slack_app_new import SlackApp
import webcode

# force_tls and load_http_server both copied from this guy's blog post.  thanks much for showing me how to do this!
# http://www.fcollyer.com/posts/cherrypy-only-http-and-https-app-serving/


def force_tls():
    if cherrypy.request.scheme == "http":
        # see https://support.google.com/webmasters/answer/6073543?hl=en
        raise cherrypy.HTTPRedirect(cherrypy.url().replace("http:", "https:"), status=301)


def load_http_server():
    # extra server instance to redirect HTTP requests to HTTPS
    cherrypy.tools.force_tls = cherrypy.Tool("before_handler", force_tls)

    server = cherrypy._cpserver.Server()
    server.socket_host = cfg.cherrypy_global['server.socket_host']
    server.socket_port = 80
    server.subscribe()


def main():
    load_departments()
    load_http_server()

    older = first_older_than_second(cfg.last_version_loaded, cfg.version)
    if older:
        do_upgrade()

    cherrypy.config.update(cfg.cherrypy_global)
    cherrypy.tree.mount(SlackApp(), '/slack', cfg.slackapp)

    cherrypy.tree.mount(webcode.Root(), '/', cfg.cherrypy)

    cherrypy.engine.start()
    cherrypy.engine.block()


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
