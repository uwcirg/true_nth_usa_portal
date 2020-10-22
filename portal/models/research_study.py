from sqlalchemy.dialects.postgresql import ENUM
from ..database import db
from .questionnaire_bank import QuestionnaireBank, qbs_by_intervention
from .research_protocol import ResearchProtocol
from .user_consent import latest_consent

status_types = (
    "active", "administratively-completed", "approved", "closed-to-accrual",
    "closed-to-accrual-and-intervention", "completed", "disapproved",
    "in-review", "temporarily-closed-to-accrual",
    "temporarily-closed-to-accrual-and-intervention", "withdrawn")
status_types_enum = ENUM(
    *status_types, name='research_study_status_enum', create_type=False)


class ResearchStudy(db.Model):
    """Model class for a FHIR ResearchStudy

    Used to mark independent Research Studies
    """
    __tablename__ = 'research_studies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True, nullable=False)
    status = db.Column(
        'status', status_types_enum, server_default='active', nullable=False)

    def as_fhir(self, include_empties=True):
        d = {}
        d['resourceType'] = 'ResearchStudy'
        d['id'] = self.id
        d['title'] = self.title
        d['status'] = self.status
        return d

    @classmethod
    def from_fhir(cls, data):
        rs = cls()
        return rs.update_from_fhir(data)

    def update_from_fhir(self, data):
        if 'id' in data:
            self.id = int(data.get('id'))
        if 'title' in data:
            self.title = data.get('title')
        if 'status' in data:
            self.status = data.get('status')
        return self

    @staticmethod
    def assigned_to(user):
        """Returns set of all ResearchStudy IDs assigned to given user"""
        base_study = 0
        results = []
        iqbs = qbs_by_intervention(user, classification=None)
        if iqbs:
            results.append(base_study)  # Use dummy till system need arises

        for rp, _ in ResearchProtocol.assigned_to(
                user, research_study_id='all'):
            rs_id = rp.research_study_id
            if rs_id is None:
                continue

            if latest_consent(user, rs_id) and rs_id not in results:
                results.append(rs_id)
        results.sort()
        if len(results):
            assert None not in results
        return results


def research_study_id_from_questionnaire(questionnaire_name):
    """Reverse lookup research_study_id from a questionnaire_name"""
    # TODO cache map and results
    # expensive mapping - store cacheable value once determined
    map = {}
    for qb in QuestionnaireBank.query.all():
        rp_id = qb.research_protocol_id
        if rp_id is None:
            continue

        rs_id = qb.research_protocol.research_study_id
        for q in qb.questionnaires:
            if q.name in map:
                if (map[q.name] != rs_id):
                    raise ValueError(
                        f"Configuration error, {q.name} belongs to multiple "
                        "research studies")
            map[q.name] = rs_id
    return map.get(questionnaire_name)


def add_static_research_studies():
    """Seed database with default static research studies

    Idempotent - run anytime to pick up any new relationships in existing dbs

    """
    base = {
      "id": 0,
      "title": "Base Study",
      "status": "active",
      "resourceType": "ResearchStudy"
    }

    rs = ResearchStudy.from_fhir(base)
    if ResearchStudy.query.get(rs.id) is None:
        db.session.add(rs)
