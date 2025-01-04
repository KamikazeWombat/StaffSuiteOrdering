import logging
import cherrypy

from slack_bolt import App
from slack_bolt.adapter.cherrypy import SlackRequestHandler
import sqlalchemy.orm.exc

from config import cfg
import models
from models.slack_user import Slack_User


logging.basicConfig(level=logging.INFO)

app = App(token=cfg.slack_authkey,
          signing_secret=cfg.slack_signing_secret)

@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@app.event("user_change")
def user_change(body, say, logger):
    session = models.new_sesh()
    try:
        user = session.query(Slack_User).filter_by(id=body['event']['user']['id']).one()
        user.display_name = body['event']['user']['profile']['display_name']
        user.real_name = body['event']['user']['real_name']
    except sqlalchemy.orm.exc.NoResultFound:
        user = Slack_User()
        user.id = user.display_name = body['event']['user']['id']
        user.name = user.display_name = body['event']['user']['name']
        user.real_name = body['event']['user']['real_name']
        user.display_name = body['event']['user']['profile']['display_name']
        session.add(user)

    session.commit()
    session.close()


@app.event("team_join")
def team_join(body, say, logger):
    session = models.new_sesh()

    user = Slack_User()
    user.id = user.display_name = body['event']['user']['id']
    user.name = user.display_name = body['event']['user']['name']
    user.real_name = body['event']['user']['real_name']
    user.display_name = body['event']['user']['profile']['display_name']
    session.add(user)

    session.commit()
    session.close()


slackhandler = SlackRequestHandler(app)


class SlackApp:
    @cherrypy.expose
    @cherrypy.tools.slack_in()
    def events(self, **kwargs):
        return slackhandler.handle()
