from datetime import datetime
from dateutil.relativedelta import relativedelta

import pytest

from portal.database import db
from portal.models.audit import Audit
from portal.models.clinical_constants import CC
from portal.models.qb_timeline import (
    AtOrderedList,
    QB_StatusCacheKey,
    QBT,
    ordered_qbs,
    second_null_safe_datetime,
    update_users_QBT,
)
from portal.models.questionnaire_bank import QuestionnaireBank, visit_name
from portal.views.user import withdraw_consent
from portal.models.overall_status import OverallStatus
from tests import TEST_USER_ID, associative_backdate, TestCase
from tests.test_assessment_status import mock_qr
from tests.test_questionnaire_bank import TestQuestionnaireBank


def test_sort():
    yesterday = datetime.utcnow() - relativedelta(days=1)
    items = set([('b', None), ('a', yesterday),  ('c', datetime.utcnow())])
    results = sorted(list(items), key=second_null_safe_datetime, reverse=True)
    # Assert expected order
    x, y = results.pop()
    assert x == 'a'
    x, y = results.pop()
    assert x == 'c'
    x, y = results.pop()
    assert x == 'b'


class TestQbTimeline(TestQuestionnaireBank):

    def test_empty(self):
        # Basic case, without org, empty list
        self.setup_org_qbs()
        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user=user)
        with pytest.raises(StopIteration):
            next(gen)

    def test_full_list(self):
        crv = self.setup_org_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        gen = ordered_qbs(user=self.test_user)

        # expect each in order despite overlapping nature
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        for n in (3, 6, 9, 15, 18, 21, 30):
            assert visit_name(next(gen)) == 'Month {}'.format(n)

        with pytest.raises(StopIteration):
            next(gen)

    def test_intervention_list(self):
        self.setup_intervention_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        # user with biopsy should return biopsy date
        self.login()
        user = db.session.merge(self.test_user)
        user.save_observation(
            codeable_concept=CC.BIOPSY, value_quantity=CC.TRUE_VALUE,
            audit=Audit(user_id=TEST_USER_ID, subject_id=TEST_USER_ID),
            status='', issued=None)
        user = db.session.merge(self.test_user)

        gen = ordered_qbs(user=user)

        # expect all intervention QBs - baseline then every 3mos
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        for n in (3, 9, 15, 21, 27):
            assert visit_name(next(gen)) == 'Month {}'.format(n)

        with pytest.raises(StopIteration):
            next(gen)

    def test_zero_input(self):
        # Basic w/o any QNR submission should generate all default QBTs
        crv = self.setup_org_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)
        update_users_QBT(TEST_USER_ID)
        # expect (due, overdue, expired) for each QB (8)
        assert QBT.query.filter(QBT.status == OverallStatus.due).count() == 8
        assert QBT.query.filter(
            QBT.status == OverallStatus.overdue).count() == 8
        assert QBT.query.filter(
            QBT.status == OverallStatus.expired).count() == 8

    def test_partial_input(self):
        crv = self.setup_org_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        # submit a mock response for 3 month QB
        # which should result in status change
        qb_name = "CRV_recurring_3mo_period v2"
        threeMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic26_v2', qb=threeMo, iteration=0)

        self.test_user = db.session.merge(self.test_user)
        update_users_QBT(TEST_USER_ID)

        # for the 8 QBs and verify counts
        # given the partial results, we find one in progress and one
        # partially completed, matching expectations
        assert QBT.query.filter(QBT.status == OverallStatus.due).count() == 8
        # should be one less overdue as it became in_progress
        assert QBT.query.filter(
            QBT.status == OverallStatus.overdue).count() == 7
        # should be one less expired as it became partially_completed
        assert QBT.query.filter(
            QBT.status == OverallStatus.expired).count() == 7
        assert QBT.query.filter(QBT.status == OverallStatus.in_progress).one()
        assert QBT.query.filter(
            QBT.status == OverallStatus.partially_completed).one()

    def test_partial_post_overdue_input(self):
        crv = self.setup_org_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        # submit a mock response for 3 month QB after overdue
        # before expired
        post_overdue = datetime.now() + relativedelta(months=4, weeks=1)
        qb_name = "CRV_recurring_3mo_period v2"
        threeMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic26_v2', qb=threeMo, iteration=0, timestamp=post_overdue)

        self.test_user = db.session.merge(self.test_user)
        update_users_QBT(TEST_USER_ID)
        # for the 8 QBs and verify counts
        # given the partial results, we find one in progress and one
        # partially completed, matching expectations
        assert QBT.query.filter(QBT.status == OverallStatus.due).count() == 8
        assert QBT.query.filter(
            QBT.status == OverallStatus.overdue).count() == 8
        # should be one less expired as it became partially_completed
        assert QBT.query.filter(
            QBT.status == OverallStatus.expired).count() == 7
        assert QBT.query.filter(QBT.status == OverallStatus.in_progress).one()
        assert QBT.query.filter(
            QBT.status == OverallStatus.partially_completed).one()

    def test_completed_input(self):
        # Basic w/ one complete QB
        crv = self.setup_org_qbs()
        self.bless_with_basics()  # pick up a consent, etc.
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)

        # submit a mock response for all q's in 3 mo qb
        # which should result in completed status
        qb_name = "CRV_recurring_3mo_period v2"
        threeMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()

        for q in threeMo.questionnaires:
            q = db.session.merge(q)
            mock_qr(q.name, qb=threeMo, iteration=0)

        self.test_user = db.session.merge(self.test_user)
        update_users_QBT(TEST_USER_ID)
        # for the 8 QBs and verify counts
        # given the partial results, we find one in progress and one
        # partially completed, matching expectations
        assert QBT.query.filter(QBT.status == OverallStatus.due).count() == 8
        # should be one less overdue as it became in_progress
        assert QBT.query.filter(
            QBT.status == OverallStatus.overdue).count() == 7
        # should be one less expired as it became partially_completed
        assert QBT.query.filter(
            QBT.status == OverallStatus.expired).count() == 7
        assert QBT.query.filter(QBT.status == OverallStatus.in_progress).one()
        assert QBT.query.filter(QBT.status == OverallStatus.completed).one()

    def test_withdrawn(self):
        # qbs should halt beyond withdrawal
        crv = self.setup_org_qbs()
        crv_id = crv.id
        # consent 17 months in past
        backdate = datetime.utcnow() - relativedelta(months=17)
        self.test_user = db.session.merge(self.test_user)
        self.test_user.organizations.append(crv)
        self.consent_with_org(org_id=crv_id, setdate=backdate)

        # withdraw user now, which should provide result
        # in QBs prior to 17 months.

        user = db.session.merge(self.test_user)
        withdraw_consent(
            user=user, org_id=crv_id, acting_user=user,
            acceptance_date=datetime.utcnow())
        gen = ordered_qbs(user=user)

        # expect each in order despite overlapping nature
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        for n in (3, 6, 9, 15):
            assert visit_name(next(gen)) == 'Month {}'.format(n)

        with pytest.raises(StopIteration):
            next(gen)

    def test_change_midstream_rp(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_org_qbs(rp_name='v2', retired_as_of=back7)
        org_id = org.id
        self.setup_org_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back14)
        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect baseline and 3 month in v2, rest in v3
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v2')
        for n in (3,):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v2'
        for n in (6, 9, 15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)

    def test_change_before_start_rp(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_org_qbs(rp_name='v2', retired_as_of=back14)
        org_id = org.id
        self.setup_org_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back7)
        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect everything in v3
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v3')
        for n in (3, 6, 9, 15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)

    def test_change_midstream_results_rp(self):
        now = datetime.utcnow()
        back1, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=1))
        back10, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=10))
        org = self.setup_org_qbs(rp_name='v2', retired_as_of=back1)
        org_id = org.id
        self.setup_org_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back10)

        # submit a mock response for 9 month QB on old RP
        # which should result in v2 for up to 9 month and v3 thereafter
        qb_name = "CRV_recurring_3mo_period v2"
        nineMo = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic_26_v2', qb=nineMo, iteration=1)

        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect baseline and 3 month in v2, rest in v3
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v2')
        for n in (3, 6, 9):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v2'
        for n in (15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)

    def test_change_before_start_rp_w_result(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_org_qbs(rp_name='v2', retired_as_of=back14)
        org_id = org.id
        self.setup_org_qbs(org=org, rp_name='v3')
        self.consent_with_org(org_id=org_id, setdate=back7)

        # submit a mock response for baseline QB on old RP
        # which should result in v2 for baseline and v3 thereafter
        qb_name = "CRV Baseline v2"
        baseline = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr('epic_26_v2', qb=baseline, iteration=None)

        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user)

        # expect everything in v3 post baseline
        expect_baseline = next(gen)
        assert visit_name(expect_baseline) == 'Baseline'
        assert (
            expect_baseline.questionnaire_bank.research_protocol.name == 'v2')
        for n in (3, 6, 9, 15, 18, 21, 30):
            qbd = next(gen)
            assert visit_name(qbd) == 'Month {}'.format(n)
            assert qbd.questionnaire_bank.research_protocol.name == 'v3'

        with pytest.raises(StopIteration):
            next(gen)

    def test_indef_change_before_start_rp(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_org_qbs(
            rp_name='v2', retired_as_of=back14, include_indef=True)
        org_id = org.id
        self.setup_org_qbs(
            org=org, rp_name='v3', include_indef=True)
        self.consent_with_org(org_id=org_id, setdate=back7)

        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user, classification='indefinite')

        # expect only v3
        expect_v3 = next(gen)
        assert (
            expect_v3.questionnaire_bank.research_protocol.name == 'v3')

        with pytest.raises(StopIteration):
            next(gen)

    def test_indef_change_before_start_rp_w_result(self):
        now = datetime.utcnow()
        back7, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=7))
        back14, nowish = associative_backdate(
            now=now, backdate=relativedelta(months=14))
        org = self.setup_org_qbs(
            rp_name='v2', retired_as_of=back14, include_indef=True)
        org_id = org.id
        self.setup_org_qbs(
            org=org, rp_name='v3', include_indef=True)
        self.consent_with_org(org_id=org_id, setdate=back7)

        # submit a mock response for indef QB on old RP
        # which should result in v2
        qb_name = "indef_v2"
        i_v2 = QuestionnaireBank.query.filter(
            QuestionnaireBank.name == qb_name).one()
        mock_qr("irondemog_v2", qb=i_v2, iteration=None)

        user = db.session.merge(self.test_user)
        gen = ordered_qbs(user, classification='indefinite')

        # expect only v2 given submission
        expect_v2 = next(gen)
        assert (
            expect_v2.questionnaire_bank.research_protocol.name == 'v2')

        with pytest.raises(StopIteration):
            next(gen)


class Test_QB_StatusCacheKey(TestCase):

    def test_current(self):
        cache_key = QB_StatusCacheKey()
        cur_val = cache_key.current()
        assert cur_val
        assert relativedelta(datetime.utcnow() - cur_val).seconds < 5

    def test_update(self):
        hourback = datetime.utcnow() - relativedelta(hours=1)
        cache_key = QB_StatusCacheKey()
        cache_key.update(hourback)
        assert hourback.replace(microsecond=0) == cache_key.current()

    def test_age(self):
        hourback = datetime.utcnow() - relativedelta(hours=1)
        cache_key = QB_StatusCacheKey()
        cache_key.update(hourback)
        assert cache_key.minutes_old() == 60


class HasAt(object):
    """Mock the sorted portion of QBT for testing AtOrderedList"""
    def __init__(self, at, label):
        self.at = at
        self.label = label


n = HasAt(datetime.utcnow(), 'now')
y = HasAt(n.at - relativedelta(days=1), 'yesterday')
y2 = HasAt(y.at, 'yesterday again')
wa = HasAt(n.at - relativedelta(weeks=1), 'week ago')


def test_at_ordered_empty():
    ao = AtOrderedList()
    assert len(ao) == 0
    ao.append(n)
    assert len(ao) == 1
    assert ao.pop() == n


def test_at_ordered_end():
    ao = AtOrderedList()
    ao.append(wa)

    # now append one (y)esterday, then a second
    # expecting order based on 'at' and insertion
    # which should map to append order in this case

    ao.append(y)
    ao.append(y2)

    assert len(ao) == 3
    assert ao.pop().label == y2.label
    assert ao.pop() == y
    assert ao.pop() == wa


def test_at_ordered_insertion():
    ao = AtOrderedList()
    ao.append(wa)
    ao.append(n)

    # now insert one (y)esterday, then a second
    # expecting order based on 'at' and insertion
    # as (n)ow is already inserted and has a greater
    # 'at' value, it should remain at the end.
    ao.append(y)
    ao.append(y2)

    assert len(ao) == 4
    assert ao.pop() == n
    assert ao.pop().label == y2.label
    assert ao.pop() == y
    assert ao.pop() == wa


def test_at_ordered_first():
    ao = AtOrderedList()
    ao.append(y)
    ao.append(n)

    # now insert element (wa - week ago) that should land at front of list
    ao.append(wa)

    assert len(ao) == 3
    assert ao.pop() == n
    assert ao.pop() == y
    assert ao.pop() == wa


def test_at_ordered_first_match():
    ao = AtOrderedList()
    ao.append(y)
    ao.append(n)

    # now insert element with same 'at' as first, expecting the original
    # first will remain first, and new, second
    ao.append(y2)

    assert len(ao) == 3
    assert ao.pop() == n
    assert ao.pop() == y2
    assert ao.pop() == y
