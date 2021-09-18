import os

import pkg_resources

needs_sphinx = '4.0'
extensions = [
    'sphinx.ext.autodoc', 'sphinx.ext.viewcode', 'sphinx.ext.intersphinx',
    'sphinx.ext.extlinks', 'sphinxcontrib.httpdomain'
]
master_doc = 'index'
project = 'sprockets.mixins.mediatype'
copyright = '2015-2021, AWeber Communications'
release = pkg_resources.get_distribution('sprockets.mixins.mediatype').version
version = '.'.join(release.split('.')[0:1])

# Only install the ReadTheDocs theme when we are not running
# in the RTD build system.
if not os.environ.get('READTHEDOCS', None):
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_sidebars = {
    '**': ['about.html', 'navigation.html'],
}

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.org/en/latest/', None),
    'sprockets': ('https://sprockets.readthedocs.org/en/latest/', None),
    'tornado': ('https://www.tornadoweb.org/en/stable/', None),
}

# https://www.sphinx-doc.org/en/master/usage/extensions/extlinks.html
extlinks = {
    'compare': ('https://github.com/sprockets/sprockets.mixins.mediatype'
                '/compare/%s', '%s')
}
