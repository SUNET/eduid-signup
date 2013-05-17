Configuration
-------------
eduID Sign Up read its configuration options from two different sources:

- A configuration file with a INI syntax
- Environment variables. Not all configuration options support this.

If one option is defined both in the configuration file and the environment
variable, eduID Sign Up will use the environment variable.

In the source distribution there are two configuration templates, one
for development and other for production purposes. It is recommended that
you copy one of them and edit it instead of writing a configuration file
from scratch. Do not edit the templates themselves as that will make
upgrading more difficult.

The following is the list of available options.

Authentication
^^^^^^^^^^^^^^
eduID Sign Up uses a secret value to sign the authentication ticket
cookie, which is used to keep track of the authentication status of the
current user.

It is extremely important that **this value is kept secret**. This
is a required value with an empty default value. This means that
you need to set it before running the server. The
:file:`development.ini` template has a value of ``1234`` for this
option so you can get your server running as fast as possible
without worrying about these things.

.. code-block:: ini

   auth_tk_secret = 7qankk6hu55lxlacyiw70js6cxeaw9l6

In this example, the auth_tk_secret value has been generated
with the following command in a Unix shell:

.. code-block:: text

   $ tr -c -d '0123456789abcdefghijklmnopqrstuvwxyz' </dev/urandom | dd bs=32 count=1 2>/dev/null;echo

You can also set this option with an environment variable:

.. code-block:: bash

   $ export AUTH_TK_SECRET=7qankk6hu55lxlacyiw70js6cxeaw9l6

Available languages
^^^^^^^^^^^^^^^^^^^
This option defines the set of available languages that eduID Sign Up will
use for internationalization purposes. The value is a space separated list
of iso codes:

.. code-block:: ini

   available_languages = en es

The default value for this option is ``en es``, which means there is support
for English and Spanish.

As of this writing only English and Spanish translation of UI text messages
are available. With this configuration option you can restrict the set of
available languages but if you add new languages to it, their translation
catalogs will not be generated magically.

Broker
^^^^^^
eduID Sign Up uses Celery to send messages to the eduID Attribute Manager.
In order to accomplish this task it needs a message broker to deliver those
messages.

This option allows you to customize the broker location. The syntax is defined
in Celery reference documentation as the
`BROKER_URL format <http://docs.celeryproject.org/en/latest/configuration.html#broker-url>`_

.. code-block:: ini

   broker_url = amqp://

You can also set this option with an environment variable:

.. code-block:: bash

   $ export BROKER_URL=amqp://

The default value for this option is ``amqp://`` which is a good value
for connecting to a basic RabbitMQ server.

Database
^^^^^^^^
This option allows you to customize the database location and other settings.

The syntax is defined in MongoDB reference documentation as the
`Connection String URI Format <http://docs.mongodb.org/manual/reference/connection-string/>`_

.. code-block:: ini

   mongo_uri = mongodb://localhost:27017/eduid_signup

You can also set this option with an environment variable:

.. code-block:: bash

   $ export MONGO_URI=mongodb://localhost:27017/eduid_signup

The default value for this option is ``mongodb://localhost:27017/eduid_signup``

Email
^^^^^
The application uses an SMTP server to send verification emails when users
register in the system.

eduID Sign Up uses the library
`pyramid_mailer <https://pypi.python.org/pypi/pyramid_mailer>`_ so you can
check the available options at
`pyramid_mailer documentation <http://docs.pylonsproject.org/projects/pyramid_mailer/en/latest/#configuration>`_

Some of the most common used are:

.. code-block:: ini

   mail.host = localhost
   mail.port = 25
   mail_default_sender = no-reply@localhost.localdomain

Facebook authentication
^^^^^^^^^^^^^^^^^^^^^^^
eduID Sign Up allows the user to easily register clicking on a Facebook
button that will fetch their Facebook account information with their
consent.

This is implemented using the
library `pyramid_sna <https://pypi.python.org/pypi/pyramid_sna/>`_

At the very minimum you need to add the public and private Facebook
API keys but you can configure other things. To learn how to get
this information check the
`pyramid_sna documentation <https://pyramid_sna.readthedocs.org/en/latest/>`_

.. code-block:: ini

   facebook_app_id = 123
   facebook_app_secret = s3cr3t

You can also set these options with environment variables:

.. code-block:: bash

   $ export FACEBOOK_APP_ID=123
   $ export FACEBOOK_APP_SECRET=s3cr3t

These two options are required and there are no default values for them.

Google authentication
^^^^^^^^^^^^^^^^^^^^^
eduID Sign Up allows the user to easily register clicking on a Google
button that will fetch their Google account information with their
consent.

This is implemented using the
library `pyramid_sna <https://pypi.python.org/pypi/pyramid_sna/>`_

At the very minimum you need to add the public and private Google
API keys but you can configure other things. To learn how to get
this information check the
`pyramid_sna documentation <https://pyramid_sna.readthedocs.org/en/latest/>`_

.. code-block:: ini

   google_client_id = 123
   google_client_secret = s3cr3t

You can also set these options with environment variables:

.. code-block:: bash

   $ export GOOGLE_CLIENT_ID=123
   $ export GOOGLE_CLIENT_SECRET=s3cr3t

These two options are required and there are no default values for them.

Profile link
^^^^^^^^^^^^
When a user succesfully register in this application he gets a message
telling him to go to his profile and fill up other information about
him. This profile site is an external application and eduID Sign Up
needs to know the location for such application.

Using this option you can configure the URL for the profile application:

.. code-block:: ini

   profile_link = http://profiles.example.com/edit

You can also set this option with an environment variable:

.. code-block:: bash

   $ export PROFILE_LINK=http://profiles.example.com/edit

This option is required and does not have a default value.
