
import cherrypy

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import cfg, c
import webcode


#cfg = config.Config()
#c = config.Uberconfig()

def main():



    cherrypy.quickstart(webcode.Root(), '/', cfg.cherrypy)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()

