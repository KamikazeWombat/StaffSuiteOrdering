
import cherrypy

from config import cfg, c
from shared_functions import load_departments
import webcode


def main():
    load_departments()
    cherrypy.quickstart(webcode.Root(), '/', cfg.cherrypy)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
