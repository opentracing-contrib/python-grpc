import os
import logging
import sys
import tempfile

from setuptools import setup, find_packages
from setuptools.command.install import install

VERSION='1.1.3'

def readme():
  """Use `pandoc` to convert `README.md` into a `README.rst` file."""
  if os.path.isfile('README.md') and any('dist' in x for x in sys.argv[1:]):
    if os.system('pandoc -s README.md -o %s/README.rst' %
                 tempfile.mkdtemp()) != 0:
      logging.warning('Unable to generate README.rst')
  if os.path.isfile('README.rst'):
    with open('README.rst') as fd:
      return fd.read()
  return ''


class VerifyVersionCommand(install):
    """Custom command to verify that the git tag matches our version"""
    description = 'verify that the git tag matches our version'

    def run(self):
        tag = os.getenv('CIRCLE_TAG')

        if tag[1:] != VERSION:
            info = "Git tag: {0} does not match the version of this app: {1}".format(
                tag, VERSION
            )
            sys.exit(info)


setup(
    name='grpcio-opentracing',
    version=VERSION,
    description='Python OpenTracing Extensions for gRPC',
    long_description=readme(),
    author='LightStep',
    license='Apache',
    install_requires=['opentracing>=1.2.2', 'grpcio>=1.1.3,<2.0', 'six>=1.10'],
    setup_requires=['pytest-runner'],
    tests_require=['pytest', 'future'],
    keywords=['opentracing'],
    classifiers=[
        'Operating System :: OS Independent',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6"
    ],
    packages=find_packages(exclude=['docs*', 'tests*', 'examples*']),
    cmdclass={
        'verify': VerifyVersionCommand,
    }
)
