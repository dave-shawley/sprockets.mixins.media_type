from importlib import metadata

needs_sphinx = '7.0'
extensions = ['sphinx.ext.viewcode', 'sphinxcontrib.httpdomain']
master_doc = 'index'
project = 'sprockets.mixins.mediatype'
copyright = '2015-2021, AWeber Communications'  # noqa: A001 -- builtin?
release = metadata.version('sprockets-mixins-mediatype')
version = '.'.join(release.split('.')[0:1])
html_theme = 'sphinx_rtd_theme'
html_sidebars = {
    '**': ['about.html', 'navigation.html'],
}

# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html
extensions.append('sphinx.ext.intersphinx')
intersphinx_mapping = {
    'ietfparse': ('https://ietfparse.readthedocs.io/en/latest', None),
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.org/en/latest/', None),
    'sprockets': ('https://sprockets.readthedocs.org/en/latest/', None),
    'tornado': ('https://www.tornadoweb.org/en/stable/', None),
}

# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html
# We need to define type aliases for both the simple name (e.g., Deserialized)
# and the prefixed name (e.g., type_info.Deserialized) since both forms
# appear in the typing annotations.
extensions.append('sphinx.ext.autodoc')
autodoc_type_aliases = {
    alias: f'sprockets.mixins.mediatype.type_info.{alias}'
    for alias in ('DefinesIsoFormat', 'Deserialized', 'DumpSFunction',
                  'HasSettings', 'LoadSFunction', 'MsgPackable',
                  'PackBFunction', 'Serializable', 'Transcoder',
                  'UnpackBFunction')
}
autodoc_type_aliases.update({
    f'type_info.{alias}': f'sprockets.mixins.mediatype.type_info.{alias}'
    for alias in ('DefinesIsoFormat', 'Deserialized', 'DumpSFunction',
                  'HasSettings', 'LoadSFunction', 'MsgPackable',
                  'PackBFunction', 'Serializable', 'Transcoder',
                  'UnpackBFunction')
})

# https://www.sphinx-doc.org/en/master/usage/extensions/extlinks.html
extensions.append('sphinx.ext.extlinks')
extlinks = {
    'compare': ('https://github.com/sprockets/sprockets.mixins.mediatype'
                '/compare/%s', '%s')
}
