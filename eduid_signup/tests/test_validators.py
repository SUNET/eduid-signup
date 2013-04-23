from os import path

import unittest

from eduid_signup.validators import email_format_validator


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
        verified_emails = self.read_emails("verified_emails.txt")

        for email in verified_emails:
            self.assertEqual(None, email_format_validator(email))

    def test_wrong_emails(self):
        wrong_emails = self.read_emails("wrong_emails.txt")

        for email in wrong_emails:
            self.assertEqual({
                "email_error": "Email is not valid",
                "email": email
            }, email_format_validator(email))
