from __future__ import print_function

import glob
import os
import pkg_resources
import subprocess
import sys
import re
from distutils.version import StrictVersion

from setuptools import setup, Extension, find_packages, Command
from setuptools.dist import Distribution
from Cython.Distutils.build_ext import build_ext as _build_ext

CMDCLASS = {}

# prevent setup.py from crashing by calling import numpy before
# numpy is installed
class build_ext(_build_ext):
    def build_extensions(self):
        numpy_incl = pkg_resources.resource_filename('numpy', 'core/include')

        for ext in self.extensions:
            if (hasattr(ext, 'include_dirs') and
                    not numpy_incl in ext.include_dirs):
                ext.include_dirs.append(numpy_incl)
        _build_ext.build_extensions(self)

CMDCLASS['build_ext'] = build_ext

SETUP_REQUIREMENTS = {'numpy': '1.8'}
REQUIREMENTS = {'Cython': '0.22',
                'matplotlib': '1.3',
                'scipy': '0.14',
                'pandas': '0.14',
                'statsmodels': '0.6',
                'patsy': '0.2'}

ALL_REQUIREMENTS = SETUP_REQUIREMENTS.copy()
ALL_REQUIREMENTS.update(REQUIREMENTS)

ext_modules = []
if not '--no-binary' in sys.argv:
    ext_modules.append(Extension("arch.univariate.recursions",
                                 ["./arch/univariate/recursions.pyx"]))
    ext_modules.append(Extension("arch.bootstrap._samplers",
                                 ["./arch/bootstrap/_samplers.pyx"]))
else:
    del REQUIREMENTS['Cython']
    sys.argv.remove('--no-binary')

class BinaryDistribution(Distribution):
    def is_pure(self):
        return False

class CleanCommand(Command):
    """Custom distutils command to clean the .so and .pyc files."""

    user_options = [("all", "a", "")]

    def initialize_options(self):
        self.all = True
        self._clean_files = []
        self._clean_trees = []
        for root, dirs, files in list(os.walk('arch')):
            for f in files:
                if os.path.splitext(f)[-1] == '.pyx':
                    search = os.path.join(root, os.path.splitext(f)[0] + '.*')
                    candidates = glob.glob(search)
                    for c in candidates:
                        if os.path.splitext(c)[-1] in ('.pyc', '.c', '.so',
                                                       '.pyd', '.dll'):
                            self._clean_files.append(c)

        for d in ('build',):
            if os.path.exists(d):
                self._clean_trees.append(d)

    def finalize_options(self):
        pass

    def run(self):
        for f in self._clean_files:
            try:
                os.unlink(f)
            except Exception:
                pass
        for clean_tree in self._clean_trees:
            try:
                import shutil
                shutil.rmtree(clean_tree)
            except Exception:
                pass

CMDCLASS['clean'] = CleanCommand

def strip_rc(version):
    return re.sub(r"rc\d+$", "", version)

# Polite checks for numpy, scipy and pandas.  These should not be upgraded,
# and if found and below the required version, refuse to install
missing_package = '{package} is installed, but the version installed' \
                  ', {existing_ver}, is less than the required version ' \
                  'of {required_version}. This package must be manually ' \
                  'updated.  If this isn\'t possible, consider installing in ' \
                  'an empty virtual environment.'

PACKAGE_CHECKS = ['numpy', 'scipy', 'pandas']
for key in PACKAGE_CHECKS:
    version = None
    satisfies_req = True
    existing_version = 'Too Old to Detect'
    if key == 'numpy':
        try:
            import numpy

            try:
                from numpy.version import short_version as version
            except ImportError:
                satisfies_req = False
        except ImportError:
            pass

    elif key == 'scipy':
        try:
            import scipy

            try:
                from scipy.version import short_version as version
            except ImportError:
                satisfies_req = False
        except ImportError:
            pass

    elif key == 'pandas':
        try:
            from pandas.version import short_version as version
        except ImportError:
            pass
        except:  # very old version
            satisfies_req = False
    else:
        raise NotImplementedError('Unknown package')

    if version:
        existing_version = StrictVersion(strip_rc(version))
        satisfies_req = existing_version >= ALL_REQUIREMENTS[key]
    if not satisfies_req:
        message = missing_package.format(package=key,
                                         existing_ver=existing_version,
                                         required_version=ALL_REQUIREMENTS[key])
        raise EnvironmentError(message)

cwd = os.getcwd()

# Convert markdown to rst for submission
long_description = ''
try:
    cmd = 'pandoc --from=markdown --to=rst --output=README.rst README.md'
    proc = subprocess.Popen(cmd, shell=True)
    proc.wait()
    long_description = open(os.path.join(cwd, "README.rst")).read()
except IOError as e:
    import warnings

    warnings.warn('Unable to convert README.md.  Most likely because pandoc is '
                  'not installed')

# Convert examples notebook to rst for docs
try:
    from IPython.nbconvert.utils.exceptions import ConversionException
    from IPython.nbconvert.utils.pandoc import PandocMissing
except ImportError as e:
    ConversionException = PandocMissing = ValueError

try:
    import IPython.nbformat as nbformat
    from IPython.nbconvert import RSTExporter

    notebooks = glob.glob(os.path.join(cwd, 'examples', '*.ipynb'))
    for notebook in notebooks:
        try:
            f = open(notebook, 'rt')
            example_nb = f.read()
            f.close()

            rst_path = os.path.join(cwd, 'doc', 'source')
            path_parts = os.path.split(notebook)
            nb_filename = path_parts[-1]
            nb_filename = nb_filename.split('.')[0]
            source_dir = nb_filename.split('_')[0]
            rst_filename = os.path.join(cwd, 'doc', 'source',
                                        source_dir, nb_filename + '.rst')

            example_nb = nbformat.reader.reads(example_nb)
            rst_export = RSTExporter()
            (body, resources) = rst_export.from_notebook_node(example_nb)
            with open(rst_filename, 'wt') as rst:
                rst.write(body)

            for key in resources['outputs'].keys():
                if key.endswith('.png'):
                    resource_filename = os.path.join(cwd, 'doc', 'source',
                                                     source_dir, key)
                    with open(resource_filename, 'wb') as resource:
                        resource.write(resources['outputs'][key])

        except:
            import warnings

            warnings.warn('Unable to convert {original} to {target}.  This '
                          'only affects documentation generation and not the '
                          'operation of the '
                          'module.'.format(original=notebook,
                                           target=rst_filename))
            print('The last error was:')
            import sys

            print(sys.exc_info()[0])
            print(sys.exc_info()[1])

except:
    import warnings

    warnings.warn('Unable to import required modules from IPython. This only '
                  'affects documentation generation and not the operation of '
                  'the module.')
    print('The last error was:')
    import sys

    print(sys.exc_info()[0])
    print(sys.exc_info()[1])

# Read version information from plain VERSION file
version = None
try:
    version_file = open(os.path.join(cwd, 'VERSION'), 'rt')
    version = version_file.read().strip()
    version_file.close()
    version_py_file = open(os.path.join(cwd, 'arch', '_version.py'), mode='wt')
    version_py_file.write('__version__="' + version + '"')
    version_py_file.close()
except:
    raise EnvironmentError('Cannot locate VERSION')

setup(name='arch',
      license='NCSA',
      version=version,
      description='ARCH for Python',
      long_description=long_description,
      author='Kevin Sheppard',
      author_email='kevin.sheppard@economics.ox.ac.uk',
      url='http://github.com/bashtage/arch',
      packages=find_packages(),
      ext_modules=ext_modules,
      package_dir={'arch': './arch'},
      cmdclass={'build_ext': build_ext, 'clean': CleanCommand},
      keywords=['arch', 'ARCH', 'variance', 'econometrics', 'volatility',
                'finance', 'GARCH', 'bootstrap', 'random walk', 'unit root',
                'Dickey Fuller', 'time series', 'confidence intervals',
                'multiple comparisons', 'Reality Check', 'SPA', 'StepM'],
      zip_safe=False,
      include_package_data=True,
      distclass=BinaryDistribution,
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Financial and Insurance Industry',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'License :: OSI Approved',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Programming Language :: Cython',
          'Topic :: Scientific/Engineering',
      ],
      install_requires=[key + '>=' + REQUIREMENTS[key] for key in REQUIREMENTS],
      setup_requires=[key + '>=' + SETUP_REQUIREMENTS[key] for key in SETUP_REQUIREMENTS],
      )
