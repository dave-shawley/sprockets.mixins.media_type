"""sprockets.mixins.mediatype"""
try:
    from .content import (  # noqa: F401
        ContentMixin, ContentSettings, add_binary_content_type,
        add_text_content_type, set_default_content_type)
except ImportError:  # pragma: no cover
    import warnings
    warnings.warn(
        'Missing runtime requirements for sprockets.mixins.mediatype',
        UserWarning)

version_info = (3, 0, 4)
version = '.'.join(str(x) for x in version_info)
__version__ = version  # compatibility
