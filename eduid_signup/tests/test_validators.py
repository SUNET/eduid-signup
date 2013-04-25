from os import path

import unittest

from eduid_signup.validators import validate_email_format


class EmailValidatorTests(unittest.TestCase):

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
