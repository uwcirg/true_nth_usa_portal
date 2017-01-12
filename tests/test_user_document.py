"""Unit test module for user document logic"""
from tempfile import NamedTemporaryFile
from StringIO import StringIO
from datetime import datetime
from flask import current_app
from flask_webtest import SessionScope
import os

from tests import TestCase, TEST_USER_ID
from portal.extensions import db
from portal.models.user_document import UserDocument


class TestUserDocument(TestCase):
    """User Document tests"""

    def test_get_user_documents(self):
        #tests whether we can successfully get the list of user documents for a user
        ud1 = UserDocument(document_type="TestFile", uploaded_at=datetime.utcnow(),
                          filename="test_file_1.txt", filetype="txt", uuid="012345")
        ud2 = UserDocument(document_type="TestFile", uploaded_at=datetime.utcnow(),
                          filename="test_file_2.txt", filetype="txt", uuid="098765")
        self.test_user.documents.append(ud1)
        self.test_user.documents.append(ud2)
        with SessionScope(db):
            db.session.commit()
        self.test_user = db.session.merge(self.test_user)
        self.login()
        rv = self.client.get('/api/user/{}/user_documents'.format(TEST_USER_ID))
        self.assert200(rv)
        self.assertEquals(len(rv.json['user_documents']), 2)


    def test_post_patient_report(self):
        #tests whether we can successfully post a patient report -type user doc file
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        test_contents = "This is a test."
        with NamedTemporaryFile(
            prefix='udoc_test_',
            suffix='.pdf',
            delete=True,
        ) as temp_pdf:
            temp_pdf.write(test_contents)
            temp_pdf.seek(0)
            tempfileIO = StringIO(temp_pdf.read())
            rv = self.client.post('/api/user/{}/patient_report'.format(service_user.id),
                                content_type='multipart/form-data', 
                                data=dict({'file': (tempfileIO, temp_pdf.name)}))
            self.assert200(rv)
        udoc = db.session.query(UserDocument).order_by(UserDocument.id.desc()).first()
        fpath = os.path.join(current_app.root_path,
                            current_app.config.get("FILE_UPLOAD_DIR"),
                            str(udoc.uuid))
        with open(fpath, 'r') as udoc_file:
            self.assertEqual(udoc_file.read(),test_contents)
        os.remove(fpath)


    def test_download_user_document(self):
        service_user = self.add_service_user()
        self.login(user_id=service_user.id)
        test_contents = "This is a test."
        with NamedTemporaryFile(
            prefix='udoc_test_',
            suffix='.pdf',
            delete=True,
        ) as temp_pdf:
            temp_pdf.write(test_contents)
            temp_pdf.seek(0)
            tempfileIO = StringIO(temp_pdf.read())
            rv = self.client.post('/api/user/{}/patient_report'.format(service_user.id),
                                content_type='multipart/form-data', 
                                data=dict({'file': (tempfileIO, temp_pdf.name)}))
            self.assert200(rv)
        udoc = db.session.query(UserDocument).order_by(UserDocument.id.desc()).first()
        rv = self.client.get('/api/user/{}/user_documents/{}/download'.format(
                            service_user.id,udoc.id))
        self.assert200(rv)
        self.assertEqual(rv.data,test_contents)

