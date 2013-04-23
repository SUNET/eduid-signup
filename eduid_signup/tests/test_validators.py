# -*- coding: utf-8 -*-


import unittest

from eduid_signup.validators import email_format_validator


class EmailValidatorTests(unittest.TestCase):

    def test_emailvalidator(self):
        verified_emails = [
            "user@example.com",
            "user@example.co.uk",
            "user@subdomain.example.co.uk",
            "user.name@example.com",
            "user+filter@example.com",
            "user.name+filter@example.co.uk",
            "averylongerlongerlongerlongerlongeremailaddress@example.com",
            "user@example.com",
            "user6@example.com",
            "66user@example.com",
            "user-test@example.com",
            "user_test@example.com",
            "user@example-test.com",
            "User@example.com",
            "USER6@example.com",
            "#user@example.com",
            "?user@example.com",
            "us#er@more.domains.example.com",
            "user@localhost.localdomain",
            "root@localhost.localdomain",
        ]

        for email in verified_emails:
            self.assertEqual(None, email_format_validator(email))

        wrong_emails = [
            "#user@exañple.com",
            "usé@more.domains.example.com",
            "userâ@more.domains.example.com",
            "user'more@.domains.example.com",
            "us·er@more.domains.example.com",
            "a@com",
            "com",
            "userlocalhost",
            "user@localhost",
        ]

        for email in wrong_emails:
            self.assertEqual({
                "email_error": "Email is not valid",
                "email": email
            }, email_format_validator(email))
