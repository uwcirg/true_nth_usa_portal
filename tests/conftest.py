# test plugin
# https://docs.pytest.org/en/latest/writing_plugins.html#conftest-py-plugins
import pytest
from portal.factories.app import create_app
from portal.factories.celery import create_celery


def pytest_addoption(parser):
    parser.addoption(
        "--include-ui-testing",
        action="store_true",
        default=False,
        help="run selenium ui tests",
    )


@pytest.fixture(scope="session")
def app(request):
    app_ = create_app()
    ctx = app_.app_context()
    ctx.push()

    def teardown():
        ctx.pop()

    request.addfinalizer(teardown)
    return app_


@pytest.fixture(scope='session')
def celery_worker_parameters():
    # type: () -> Mapping[str, Any]
    """Redefined like fixture from celery.contrib.pytest.py as instructed

    Specifically, we need to extend the default queues so the celery worker
    will process tasks given to either queue.

    The dict returned by your fixture will then be used
    as parameters when instantiating :class:`~celery.worker.WorkController`.
    """
    return {
        'queues': ('celery', 'low_priority'),
        'perform_ping_check': False}


@pytest.fixture(scope='session')
def celery_app(app):
    # change default queue to low
    #app.config['CELERY_TASK_DEFAULT_QUEUE'] = 'low_priority'
    celery = create_celery(app)
    # for use celery_worker fixture
    from celery.contrib.testing import tasks  # NOQA
    return celery
