import os
from release_tool import __version__
from setuptools import setup, find_packages

requires = [
    "GitPython",
    "pygithub",
]

console_scripts = [
    'release-tool = release_tool.release_tool:main'
]

package_name = "release_tool"
base_dir = os.path.abspath(os.path.dirname(__file__))
# Get the long description from the README file
with open(os.path.join(base_dir, 'README.md')) as f:
    long_description = f.read().decode('utf-8')

setup(
    name=package_name,
    version=__version__,
    author="Jack Robison",
    author_email="jackrobison@lbry.io",
    description="Multi-repo release and bump tool for lbry repositories",
    long_description=long_description,
    license='MIT',
    packages=find_packages(base_dir, exclude=['tests']),
    install_requires=requires,
    entry_points={'console_scripts': console_scripts},
)
