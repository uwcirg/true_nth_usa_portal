from datetime import datetime, timedelta

import pytz
import shelve

from flask import Blueprint, current_app
import redis
from sqlalchemy import text

from ..database import db
from ..factories.celery import create_celery

HEALTHCHECK_FAILURE_STATUS_CODE = 200

healthcheck_blueprint = Blueprint('healthcheck', __name__)


@healthcheck_blueprint.route('/celery_beat_ping')
def celery_beat_ping():
    """Periodically called by a celery beat task

    Updates the last time we recieved a call to this API.
    This allows us to monitor whether celery beat tasks are running
    """
    rs = redis.StrictRedis.from_url(current_app.config['REDIS_URL'])
    rs.setex(
        name='last_celery_beat_ping',
        time=current_app.config['LAST_CELERY_BEAT_PING_EXPIRATION_TIME'],
        value=str(datetime.now())
    )
    return 'PONG'


##############################
# Healthcheck functions below
##############################

def celery_available():
    """Determines whether celery is available"""
    celery = create_celery(current_app)
    result = celery.control.inspect().ping()
    if result:
        return True, 'Celery is available.'
    else:
        return False, 'Celery is not available.'


def celery_beat_available():
    """Determines whether celery beat is available"""
    # https://github.com/celery/celery/issues/3694
    # HealthCheck from https://steemit.com/code/@qrul/celery-beat-and-workers-healthchecks

    now = datetime.now(tz=pytz.utc)

    # Name of the file used by PersistentScheduler to store the last run times of periodic tasks.
    file_data = shelve.open('celerybeat-schedule')

    for task_name, task in file_data['entries'].items():
        try:
            assert now  < task.last_run_at + task.schedule.run_every
        except AttributeError:
            assert timedelta() < task.schedule.remaining_estimate(task.last_run_at)
            return False, 'Celery beat is not available.'

    return True, 'Celery beat is available.'


def postgresql_available():
    """Determines whether postgresql is available"""
    # Execute a simple SQL Alchemy query.
    # If it succeeds we assume postgresql is available.
    # If it fails we assume psotgresql is not available.
    try:
        db.engine.execute(text('SELECT 1'))
        return True, 'PostgreSQL is available.'
    except Exception as e:
        current_app.logger.error(
            'sql alchemy not connected to postgreSQL. Error: {}'.format(e)
        )
        return False, 'PostgreSQL is not available.'


def redis_available():
    """Determines whether Redis is available"""
    # Ping redis. If it succeeds we assume redis
    # is available. Otherwise we assume
    # it's not available
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available.'
    except Exception as e:
        current_app.logger.error(
            'Unable to connect to redis. Error {}'.format(e)
        )
        return False, 'Redis is not available.'


# The checks that determine the health
# of this service's dependencies
HEALTH_CHECKS = [
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
]
