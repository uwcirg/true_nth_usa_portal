from sqlalchemy.dialects.postgresql import ENUM
from ..database import db

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
