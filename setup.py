from setuptools import setup, find_packages
import os

file_dir = os.path.abspath(os.path.dirname(__file__))

def read_file(filename):
    filepath = os.path.join(file_dir, filename)
    return open(filepath).read()

def install_requires():
    reqs = read_file('requirements.txt')
    reqs = reqs.splitlines()
    reqs = [ x for x in reqs if x and x[0] != '#' and x[0:2] != '-e' ]
    return reqs

setup(
    name="za-hansard",
    version='0.2',
    description='A scraper and parser for South African parliamentary transcripts.',
    long_description=read_file('README.md'),
    author='mySociety',
    author_email='hakim@mysociety.org',
    url='https://github.com/mysociety/za-hansard',
    packages=find_packages(exclude=["example_project"]),
    package_data={'za_hansard': ['tests/test_inputs/*/*/*/*']},
    include_package_data=True,
    install_requires=install_requires(),
    classifiers=[
        'Framework :: Django',
    ],
)
