ZA-Hansard
==========

A parser for South African Hansards, as published at
http://www.parliament.gov.za/live/content.php?Category_ID=119

Also has management commands for parsing committee minutes
and parliamentary Questions/Answers.

[![Build Status](https://travis-ci.org/mysociety/za-hansard.png)](https://travis-ci.org/mysociety/za-hansard)

Documentation
-------------
Documentation (a work in progress) can be found at: http://mysociety.github.com/za-hansard/

See also https://github.com/mysociety/pombola/blob/master/docs/south_africa.md

Installation
------------

Something like the following, customised to your particular environment or set up:

``` bash
# Clone the repo
mkdir za-hansard
cd za-hansard
git clone https://github.com/mysociety/za-hansard.git

cd za-hansard

# Install the required software packages
# Assuming you're on a debian/ubuntu server:
grep -v '#' conf/packages | sudo xargs apt-get install -y

# Set up a python virtual environment, activate it
# this assumes that you will set up the virtualenv in ..
# (e.g. outside the repo.
#  You can use ~/.virtualenvs/ etc. if you prefer)
virtualenv --no-site-packages ../virtualenv-za_hansard
source ../virtualenv-za_hansard/bin/activate

# Install required python packages
pip install --requirement requirements.txt

# create the database
createdb za-hansard

# Fill in needed configuration
cp conf/general.yml-example conf/general.yml
$EDITOR conf/general.yml

# Set up databases
./manage.py syncdb
./manage.py migrate
```

## Run the tests

```bash
./manage.py test
```
