#!/bin/bash
#
# Install all requirements
#

set -e
set -x

#apt-get -y install \

PYPI="https://pypi.nordu.net/simple/"
ping -c 1 -q pypiserver.docker && PYPI="http://pypiserver.docker:8080/simple/"

echo "#############################################################"
echo "$0: Using PyPi URL ${PYPI}"
echo "#############################################################"

/opt/eduid/bin/pip install       -i ${PYPI} raven

/opt/eduid/bin/pip freeze
