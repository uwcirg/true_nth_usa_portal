from datetime import datetime, timedelta
from flask import Blueprint, current_app
import os
import redis
import requests
from sqlalchemy import text

from ..database import db


healthcheck_blueprint = Blueprint('healthcheck', __name__)


@healthcheck_blueprint.route('/celery_beat_ping')
def celery_beat_ping():
    """Periodically called by a celery beat task

    Updates the last time we recieved a call to this API.
    This allows us to monitor whether celery beat tasks are running
    """
    redis.from_url(app.config['REDIS_URL']).setex(
        'celery_beat_available',
        get_celery_beat_ping_expiration_time(), 
        str(datetime.now()),
    )
    return 'PONG'


def get_celery_beat_ping_expiration_time():
    """The max time we can go without a ping in seconds"""
    # The interval celery beat pings the /celery_beat_ping API
    ping_interval = current_app.config['CELERY_BEAT_PING_INTERVAL']

    # The number of times we can miss a ping before we fail
    missed_beats_before_fail = \
        current_app.config['CELERY_BEAT_MISSED_PINGS_BEFORE_FAIL']

    # The maximum amount of time we can go
    # without a ping and still succeed
    threshold = ping_interval * missed_beats_before_fail

    return threshold


##############################
# Healthcheck functions below
##############################

def celery_available():
    """Determines whether celery is available"""
    url = url_for('celery_test', redirect-to-result=True)
    response = requests.get(url)
    if response.ok:
        return True, 'Celery is available.'
    else:
        current_app.logger.error(
            'Unable to connect to celery. '
            '/celery-test status code {}'.format(response.status_code)
        )
        return False, 'Celery is not available'


def celery_beat_available():
    """Determines whether celery beat is available"""
    rs = redis.from_url(app.config['REDIS_URL'])

    # When celery beat is running it pings
    # our service periodically which sets
    # 'celery_beat_available' in redis. If
    # that variable expires it means
    # we have not received a ping from celery beat
    # within the allowed window and we must assume
    # celery beat is not available
    last_celery_beat_ping = rs.get('celery_beat_available')
    if last_celery_beat_ping:
        return (
            True,
            'Celery beat is available. Last check: {}'.format(
                last_celery_beat_ping
            )
        )

    return False, 'Celery beat is not running jobs'


def postgresql_available():
    """Determines whether postgresql is available"""
    # Execute a simple SQL Alchemy query.
    # If it succeeds we assume postgresql is available.
    # If it fails we assume psotgresql is not available.
    try:
        db.engine.execute(text('SELECT 1'))
        return True, 'PostgreSQL is available'
    except Exception as e:
        current_app.logger.error(
            'sql alchemy not connected to postgreSQL. Error: {}'.format(e)
        )
        return False, 'PostgreSQL is not available'


def redis_available():
    """Determines whether Redis is available"""
    # Ping redis. If it succeeds we assume redis
    # is available. Otherwise we assume
    # it's not available
    rs = redis.from_url(current_app.config["REDIS_URL"])
    try:
        rs.ping()
        return True, 'Redis is available'
    except redis.ConnectionError as e:
        current_app.logger.error(
            'Unable to connect to redis. Error {}'.format(e)
        )
        return False, 'Redis is not available'


# The checks that determine the health
# of this service's dependencies
HEALTH_CHECKS = [
    celery_available,
    celery_beat_available,
    postgresql_available,
    redis_available,
]
