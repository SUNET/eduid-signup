from os import path

import unittest

from eduid_signup.validators import validate_email_format
from eduid_signup.validators import validate_email_is_unique
from eduid_signup.validators import validate_email, ValidationError
from eduid_signup.testing import DBTests


class EmailFormatTests(unittest.TestCase):

    def read_emails(self, filename):
        basepath = path.abspath(path.dirname(__file__))
        emails = []
        with open(path.join(basepath, filename), "r") as emailsfile:
            emaillines = emailsfile.readlines()
            for emailline in emaillines:
                emails.append(emailline.strip())
        return emails

    def test_verified_emails(self):
        for email in self.read_emails("verified_emails.txt"):
            self.assertTrue(validate_email_format(email))

    def test_wrong_emails(self):
        for email in self.read_emails("wrong_emails.txt"):
            self.assertFalse(validate_email_format(email))


class EmailUniqueTests(DBTests):

    clean_collections = ('registered', )

    def test_email_unique(self):
        if not self.db:
            raise unittest.SkipTest("requires accessible MongoDB server")
        self.assertTrue(validate_email_is_unique(self.db, 'foo@example.com'))

    def test_email_duplicate(self):
        if not self.db:
            raise unittest.SkipTest("requires accessible MongoDB server")
        self.db.registered.insert({'email': 'foo@example.com'}, safe=True)

        self.assertFalse(validate_email_is_unique(self.db, 'foo@example.com'))


class ValidateEmailTests(DBTests):

    clean_collections = ('registered', )

    def test_no_email(self):
        self.assertRaises(ValidationError, validate_email,
                          self.db, {})

    def test_bad_format(self):
        self.assertRaises(ValidationError, validate_email,
                          self.db, {'email': 'a@com'})

    def test_already_exist(self):
        if not self.db:
            raise unittest.SkipTest("requires accessible MongoDB server")
        self.db.registered.insert({'email': 'foo@example.com'}, safe=True)
        self.assertRaises(ValidationError, validate_email,
                          self.db, {'email': 'foo@example.com'})

    def test_good_email(self):
        if not self.db:
            raise unittest.SkipTest("requires accessible MongoDB server")
        self.assertEqual('bar@example.com',
                         validate_email(self.db, {'email': 'bar@example.com'}))
