Installation
------------

Minimum requirements
^^^^^^^^^^^^^^^^^^^^
eduID Sign Up is a Python web application so you will need a Python
interpreter for running it. It has been tested with Python 2.7 and
Python 3.3 so either one should work fine. However we recommend
sticking with Python 2.7 since not all the Python dependencies for
eduID Sign Up works with Python 3.

This guide will document the process of installing eduID Sign Up
in a Linux distribution, either a Debian or Redhat based one. The
authors do not have a Windows box available to test and document its
installation.

In all Linux modern distributions Python 2.7 is installed by default
so you will not need to do anything special at this point.

Installing virtualenv
^^^^^^^^^^^^^^^^^^^^^
In Python it is considered best practice to install your applications
inside virtual environments. To do so you will need to install the
virtualenv package for your Linux distribution:

Deb based example:

.. code-block:: text

   $ sudo apt-get install python-setuptools

Rpm based example:

.. code-block:: text

   $ sudo yum install python-setuptools

Once the virtualenv package has been installed a new virtual environment
can be created with a very simple command:

.. code-block:: text

   $ sudo virtualenv /opt/eduid-signup
   New python executable in /opt/eduid-signup/bin/python
   Installing setuptools............done.
   Installing pip...............done.

In order to be useful the virtual environment needs to be activated:

.. code-block:: text

   $ source /opt/eduid-signup/bin/activate
   (eduid-signup)$


Installing eduID Sign Up
^^^^^^^^^^^^^^^^^^^^^^^^
After the virtualenv is activated it is time to install eduID Sign Up itself.
You can choose between installing a development version or a stable version.

Stable version
""""""""""""""
Installing a stable version is really easy, all you have to do is execute the
following command and have a coffee while it downloads the application and all
its dependencies:

.. code-block:: text

   (eduid-signup)$ easy_install eduid_signup

Development version
"""""""""""""""""""
To install a development version first the code needs to be checked out from
the Git repository at Github.com:

.. code-block:: text

   (eduid-signup)$ cd /opt/eduid-signup
   (eduid-signup)$ git clone git://github.com/SUNET/eduid-signup.git
   Cloning into 'eduid-signup'...
   remote: Counting objects: 424, done.
   remote: Compressing objects: 100% (259/259), done.
   remote: Total 424 (delta 235), reused 315 (delta 126)
   Receiving objects: 100% (424/424), 245.39 KiB | 70 KiB/s, done.
   Resolving deltas: 100% (235/235), done.

Then it can be installed in development mode, which will install it and all
its dependencies in the virtualenv:

.. code-block:: text

   (eduid-signup)$ cd /opt/eduid-signup/eduid-signup
   (eduid-signup)$ python setup.py develop

Database setup
^^^^^^^^^^^^^^
eduID Sign Up stores the information about registered users in a MongoDB
database so you need it installed in the same machine or in other box that
is accessible from the one you installed eduID Sign Up in.

Deb based example:

.. code-block:: text

   $ sudo apt-get install mongodb mongodb-server

Rpm based example:

.. code-block:: text

   $ sudo yum install mongodb mongodb-server

Now it is time to start the database server and configure it to start at boot
time.

Deb based example:

.. code-block:: text

   $ sudo service mongodb start
   $ sudo update-rc.d mongodb defaults

Rpm based example:

.. code-block:: text

   $ sudo systemctl start mongod.service
   $ sudo systemctl enable mongod.service


Testing the application
^^^^^^^^^^^^^^^^^^^^^^^
Once everything is installed, the application can be started but first
you need to write a configuration file. Luckily, there are several
example configuration files in the `config-templates` directory ready
to be used. For example, the `development.ini` is a good starting point
if you want to test or develop the application:

.. code-block:: text

   $ cp config-templates/development.ini myconfig.ini

It is important to activate the virtualenv before running the server:

.. code-block:: text

   $ source /opt/eduid-signup/bin/activate
   (eduid-signup)$ pserver myconfig.ini
   Starting server in PID 16756.
   serving on http://0.0.0.0:6543

Now you can open the link http://0.0.0.0:6543 in your browser and test
the application.

The `pserve` command will use the `Waitress` WSGI server which is a very
capable server and also very handy for development.

The next thing you should do is learn about all the configuration options
and other WSGI server choices for production.
