from datetime import datetime, timedelta
from flask import Blueprint, current_app
import redis
from redis import ConnectionError
from sqlalchemy import text
from subprocess import call

from ..database import db


healthcheck_blueprint = Blueprint('healthcheck', __name__)
last_celery_beat_health_check = datetime.now()

@healthcheck_blueprint.route('/celery_beat_ping')
def celery_beat_ping():
    """Periodically called by a celery beat task
    
    Updates the last time we recieved a call to this API.
    This allows us to monitor whether celery beat tasks are running
    """
    global last_celery_beat_health_check
    last_celery_beat_health_check = datetime.now()
    return 'PONG'


##############################
# Healthcheck functions below
##############################

def celery_available():
    code = call([
        'celery',
        '-A', 'portal.celery_worker.celery',
        'inspect', 'ping'
    ])
    if code == 0:
        return True, 'Celery is available.'
    else:
        current_app.logger.error('Unable to connect to celery.')
        return False, 'Celery is not available'

def celery_beat_available():
    if last_celery_beat_health_check:
        threshold = timedelta(
            seconds=current_app.config['CELERY_BEAT_HEALTH_CHECK_INTERVAL_SECONDS'] * 2
        )
        time_since_last_beat = \
            datetime.now() - last_celery_beat_health_check

        if time_since_last_beat <= threshold:
            return True, 'Celery beat is available. Last check: {}'.format(last_celery_beat_health_check)
    
    return False, "Celery beat is not running jobs. Last check: {}".format(last_celery_beat_health_check)

def postgresql_available():
    try:
        db.engine.execute(text('SELECT 1'))
        return True, 'PostgreSQL is available'
    except Exception as e:
        current_app.logger.error('sql alchemy not connected to postgreSQL. Error: {}'.format(e))
        return False, 'PostgreSQL is not available'

def redis_available():
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available'
    except ConnectionError as e:
        current_app.logger.error('Unable to connect to redis. Error {}'.format(e))
        return False, 'Redis is not available'

HEALTH_CHECKS = [
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
]
