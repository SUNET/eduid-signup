'''
Usage
-----

To execute these tests, we need to have two servers serving the eduid-signup
app, both configured to use the same MongoDB databases. The URLs at which
these server listen for HTTP requests must be set below as ``SIGNUP_SERVER_1``
and ``SIGNUP_SERVER_1``.
We must also configure ``SMTP_SERVER`` with an address (in the local machine
were the tests are going to run) that can be reached from both signup servers,
and we must configure the signup servers' ``mail.host`` and ``mail.port`` with
the corresponding values from ``SMTP_SERVER``.

Then we need a python environment were we have installed selenium and nose::

    $ virtualenv selenium
    $ cd selenium
    $ source bin/activate
    $ easy_install selenium
    $ easy_install nose

This environment doesn't need to have any of the eduID packages installed.
With this environment activated, we change to the ``test-redundancy``
directory (were this file is located) and run ``nosetests``::

    $ cd /path/to/eduid-signup/test-redundancy
    $ nosetests

'''
_author__ = 'eperez'

import unittest
import asyncore
import re
from multiprocessing import Process, Queue
from smtpd import SMTPServer
from selenium import webdriver


SMTP_SERVER = ('192.168.122.1', 2525)
SIGNUP_SERVER_1 = 'http://profile.eduid.example.com:6543'
SIGNUP_SERVER_2 = 'http://profile.eduid.example2.com:6543'


class TestingSMTPServer(SMTPServer):

    def __init__(self, localaddr, remoteaddr, queue):
        SMTPServer.__init__(self, localaddr, remoteaddr)
        self.queue = queue

    def process_message(self, peer, mailfrom, rcpttos, data):
        self.queue.put(data)

def start_smtp_server(queue):
    TestingSMTPServer(SMTP_SERVER, None, queue)
    asyncore.loop()


class RedundancyTests(unittest.TestCase):

    queue = None
    smtp_process = None

    @classmethod
    def setUpClass(cls):
        cls.queue = Queue()
        cls.smtp_process = Process(target=start_smtp_server, args=(cls.queue,))
        cls.smtp_process.start()

    @classmethod
    def tearDownClass(cls):
        cls.smtp_process.terminate()
        cls.smtp_process.join()
        cls.queue.close()

    def setUp(self):
        self.browser1 = webdriver.Firefox()
        self.browser2 = webdriver.Firefox()
        self.browser1.implicitly_wait(5)
        self.browser2.implicitly_wait(5)

    def tearDown(self):
        self.browser1.quit()
        self.browser2.quit()

    def test_basic(self):
        self.browser1.get('http://profile.eduid.example.com:6543/')
        self.browser2.get('http://profile.eduid.example2.com:6543/')
        self.assertIn('Sign up', self.browser1.title)
        self.assertIn('Sign up', self.browser2.title)

    def _signup_twice(self, email):
        self.browser1.get(SIGNUP_SERVER_1)
        self.browser2.get(SIGNUP_SERVER_2)
        i = self.browser1.find_element_by_css_selector(
                '.input-append > input:nth-child(1)')
        i.send_keys(email)
        self.browser1.find_element_by_css_selector(
                'button.btn').click()
        self.browser1.find_element_by_css_selector(
                'a.btn:nth-child(2)').click()
        data1 = self.queue.get()
        i = self.browser2.find_element_by_css_selector(
                '.input-append > input:nth-child(1)')
        i.send_keys(email)
        self.browser2.find_element_by_css_selector(
                'button.btn').click()
        self.browser2.find_element_by_css_selector(
                'a.btn:nth-child(2)').click()
        data2 = self.queue.get()
        pattern = re.compile(r'href=".*/email_verification/([^/]+)/"')
        match1 = pattern.search(data1)
        match2 = pattern.search(data2)
        return match1.group(1), match2.group(1)

    def test_signup_same_email(self):
        code1, code2 = self._signup_twice('johnsmith@example.com')
        url1 = '{0}/email_verification/{1}/'.format(SIGNUP_SERVER_1, code1)
        url2 = '{0}/email_verification/{1}/'.format(SIGNUP_SERVER_1, code2)
        self.browser1.get(url1)
        self.assertIn('The provided code does not exist '
                      'or your link is broken', self.browser1.page_source)
        self.browser2.get(url2)
        self.assertIn('Write this password down and '
                      'store it in a safe place.', self.browser2.page_source)
