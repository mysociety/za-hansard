ZA-Hansard
==========

A parser for South African Hansards, as published at 
http://www.parliament.gov.za/live/content.php?Category_ID=119

Documentation
-------------
Documentation (a work in progress) can be found at: http://mysociety.github.com/za-hansard/

Installation
------------

Something like the following, customised to your particular environment or set up:

    # Clone the repo
    mkdir za-hansard
    cd za-hansard
    git clone https://github.com/mysociety/z-hansard.git

    cd za-hansard

    # Install the required software packages
    # Assuming you're on a debian/ubuntu server:
    # grep -v '#' conf/packages | sudo xargs apt-get install -y

    # Set up a python virtual environment, activate it
    # this assumes that you will set up the virtualenv in .. 
    # (e.g. outside the repo.  
    #  You can use ~/.virtualenvs/ etc. if you prefer)
    virtualenv --no-site-packages ../virtualenv-zah
    source ../virtualenv-zah/bin/activate

    # Install required python packages
    pip install --requirement requirements.txt

Testing
-------

    nosetests zah
