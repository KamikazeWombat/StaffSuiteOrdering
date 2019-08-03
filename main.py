
import cherrypy

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import cfg, c
import webcode


#cfg = config.Config()
#c = config.Uberconfig()

def main():

    Base = declarative_base()
    engine = create_engine(cfg.database_location)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    cherrypy.quickstart(webcode.Root(), '/', cfg.cherrypy)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()

