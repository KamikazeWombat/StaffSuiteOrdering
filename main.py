
import cherrypy

from config import cfg, c
import webcode


def main():

    cherrypy.quickstart(webcode.Root(), '/', cfg.cherrypy)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()

