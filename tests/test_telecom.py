"""Unit test module for telecom model"""
from portal.models.telecom import ContactPoint, Telecom
from tests import TestCase


class TestTelecom(TestCase):
    """Telecom model tests"""

    def test_telecom_from_fhir(self):
        data = [
            {
                "system": "phone",
                "value": "(+1) 734-677-7777"
            },
            {
                "system": "fax",
                "value": "(+1) 734-677-6622"
            },
            {
                "system": "email",
                "value": "hq@HL7.org"
            },
            {
                "system": "email",
                "value": "second_email@HL7.org"
            }
        ]
        tc = Telecom.from_fhir(data)
        self.assertEqual(len(tc.contact_points), 3)
        self.assertEqual(tc.email, "hq@HL7.org")

    def test_telecom_as_fhir(self):
        cp = ContactPoint(system='phone', use='work', value='123-4567')
        tc = Telecom(email='hq@HL7.org', contact_points=[cp])
        data = tc.as_fhir()
        self.assertEqual(len(data), 2)

    def test_telecom_cp_dict(self):
        cp = ContactPoint(system='phone', use='work', value='123-4567')
        tc = Telecom(email='hq@HL7.org', contact_points=[cp])
        data = tc.cp_dict()
        self.assertEqual(len(data), 1)
        self.assertEqual(data.get(('phone', 'work')), '123-4567')

    def test_contactpoint_from_fhir(self):
        data = {
            "system": "phone",
            "use": "work",
            "rank": 1,
            "value": "867-5309"
        }
        cp = ContactPoint.from_fhir(data)
        self.assertEqual(cp.system, "phone")
        self.assertEqual(cp.value, "867-5309")

    def test_contactpoint_as_fhir(self):
        cp = ContactPoint(system='phone', use='work', value='867-5309')
        data = cp.as_fhir()
        self.assertEqual(len(data), 3)
        self.assertEqual(data['value'], '867-5309')
