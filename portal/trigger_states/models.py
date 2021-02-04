from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import make_transient

from ..database import db
from ..date_tools import FHIR_datetime


trigger_state_enum = ENUM(
    'unstarted',
    'due',
    'inprocess',
    'processed',
    'triggered',
    'resolved',
    name='trigger_state_type',
    create_type=False)


class TriggerState(db.Model):
    """ORM class for trigger state

    Model patient's trigger state, retaining historical record for reporting.

    """
    __tablename__ = 'trigger_states'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.id'), nullable=False, index=True)
    state = db.Column('state', trigger_state_enum, nullable=False, index=True)
    timestamp = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    questionnaire_response_id = db.Column(
        db.ForeignKey('questionnaire_responses.id'), index=True)
    visit_month = db.Column(db.Integer, nullable=False, index=True, default=0)
    triggers = db.Column(JSONB)

    def as_json(self):
        results = {
            'state': self.state,
            'user_id': self.user_id,
            'visit_month': self.visit_month}
        if self.timestamp:
            results['timestamp'] = FHIR_datetime.as_fhir(self.timestamp)
        if self.triggers:
            results['triggers'] = self.triggers
        return results

    def __repr__(self):
        return (
            "TriggerState on user {0.user_id}: {0.state}".format(self))

    def insert(self, from_copy=False):
        """Shorthand to create/persist a new row as defined

        :param from_copy: set when an existing row was copied/used to
         force generation of new row.

        """
        if self.id and not from_copy:
            raise RuntimeError(f"'{self}' already persisted - can't continue")
        if from_copy:
            # Force new row with db defaults for id and timestamp
            make_transient(self)
            self.id = None
            self.timestamp = None
        db.session.add(self)
        db.session.commit()

    def hard_trigger_list(self):
        """Convenience function to return list of hard trigger domains

        Save clients from internal structure of self.triggers - returns
        a simple list of hard trigger domains if any exist for instance.

        """
        if not self.triggers:
            return

        results = []
        for domain, link_triggers in self.triggers['domain'].items():
            if 'hard' in link_triggers.values():
                results.append(domain)
        return results

    def reminder_due(self):
        """Determine if reminder is due from internal state"""
        # locate first and most recent *staff* email
        first_sent, last_sent = None, None
        for email in self.triggers['actions']['email']:
            if 'staff' in email['context']:
                if not first_sent:
                    first_sent = FHIR_datetime.parse(email['timestamp'])
                last_sent = FHIR_datetime.parse(email['timestamp'])

        if not first_sent:
            return

        now = datetime.utcnow()

        # To be sent daily after the initial 48 hours
        needed_delta = timedelta(days=1)
        if first_sent + timedelta(hours=1) > last_sent:
            # only initial has been sent.  need 48 hours to have passed
            needed_delta = timedelta(days=2)

        return now > last_sent + needed_delta

    def soft_trigger_list(self):
        """Convenience function to return list of soft trigger domains

        Save clients from internal structure of self.triggers - returns
        a simple list of soft trigger domains if any exist for instance.
        NB, all hard triggers imply a matching soft trigger.

        """
        if not self.triggers:
            return

        results = set(self.hard_trigger_list())
        for domain, link_triggers in self.triggers['domain'].items():
            if 'soft' in link_triggers.values():
                results.add(domain)
        return list(results)

    @staticmethod
    def latest_action_state(user_id, visit_month):
        """Query method to return row matching params

        :param user_id: User/patient in question
        :param visit_month: integer, zero indexed visit month
        :return: latest action state or empty string if not found

        """
        found = TriggerState.query.filter(
            TriggerState.user_id == user_id).filter(
            TriggerState.visit_month == visit_month).order_by(
            TriggerState.id.desc()).first()
        if not found or found.triggers is None:
            return ''

        return found.triggers['action_state']
