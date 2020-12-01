"""Module to handle complexity of domain scoring and triggers"""
from ..models.questionnaire_response import first_last_like_qnr

# TODO extract from EMPRO Questionnaire - hardcoded for time being
EMPRO_DOMAINS = (
    'general_pain', 'joint_pain', 'insomnia', 'fatigue', 'anxious',
    'discouraged', 'sad', 'social_isolation')


class AnswerIdValue(object):
    """Simple container to hold identifier and value for an answer"""
    def __init__(self, id, value):
        self.id = id
        self.value = value


# TODO... for now, generate some bogus triggers
def faux_trigger():
    # randomly return one of the possible trigger states
    from random import randint

    v = randint(0, 2)
    if v == 2:
        return 'hard', 'soft'
    elif v == 1:
        return ('soft',)
    else:
        return ()


class DomainTriggers(object):
    """Handles only the trigger calc, from question ID and value internals

    To calculate triggers within a domain, we need question identifiers and
    values.  Given such, calculate the trigger state for any given domain.
    """

    def __init__(self, domain):
        self.domain = domain
        self._triggers = set()

        # Dictionaries (possibly empty) keyed by question ID, containing
        # answer value
        self.current_answers = dict()
        self.previous_answers = dict()
        self.initial_answers = dict()

    @property
    def triggers(self):
        self.eval()
        return list(self._triggers)

    def check_for_worsening(self, previous, current):
        """Helper to look for worsening conditions"""
        keyset = set(list(previous.keys()) + list(current.keys()))
        for k in keyset:
            if k not in previous or k not in current:
                # Without an answer in both, can't compare
                continue

            if previous[k] < current[k]:
                self._triggers.add('soft')
                if previous[k] + 1 < current[k]:
                    self._triggers.add('hard')

    def eval(self):
        """Use instance data to evaluate trigger state for domain"""
        # consider caching - for now, recalc when called
        self._triggers.clear()

        # check if current data includes hard trigger
        for value in self.current_answers.values():
            if value >= 4:
                self._triggers.add('hard')
                # Hard trigger implicitly includes soft
                self._triggers.add('soft')

        # if we have a previous or initial, see if anything worsened
        if self.previous_answers:
            self.check_for_worsening(
                self.previous_answers, self.current_answers)

        if self.initial_answers:
            self.check_for_worsening(
                self.initial_answers, self.current_answers)


class DomainManifold(object):
    """Bring together available responses and domains for trigger eval"""

    def __init__(self, qnr):
        self.first_qnr, self.last_qnr, self.cur_qnr = None, None, None
        self.first_obs, self.last_obs, self.cur_obs = None, None, None
        self.obtain_observations(qnr)

    def obtain_observations(self, qnr):
        self.cur_qnr = qnr
        self.first_qnr, self.last_qnr = first_last_like_qnr(qnr)

        for timepoint in 'cur', 'first', 'last':
            qnrs = getattr(self, f"{timepoint}_qnr")
            if qnrs:
                # TODO Obtain observations directly from QNR or Query
                setattr(self, f"{timepoint}_obs", [])

    def eval_triggers(self):
        triggers = dict()
        triggers['source_data'] = {
            'initial': 'QuestionnaireResponse/123',
            'last': 'QuestionnaireResponse/123',
            'current': 'QuestionnaireResponse/123'}

        # TODO walk actual observations by domain at a time, use
        #  and use DomainTriggers(domain).eval() to populate
        triggers['domain'] = [{d: faux_trigger()} for d in EMPRO_DOMAINS]
        return triggers

