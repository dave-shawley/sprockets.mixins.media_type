"""sprockets.mixins.mediatype"""

from importlib import metadata

try:
    from .content import (  # noqa: F401 -- exported
        ContentMixin,
        ContentSettings,
        add_binary_content_type,
        add_text_content_type,
        set_default_content_type,
    )
except ImportError:  # pragma: no cover
    import warnings

    warnings.warn(
        'Missing runtime requirements for sprockets.mixins.mediatype',
        UserWarning,
        stacklevel=2,
    )

version = metadata.version('sprockets-mixins-mediatype')
version_info = [int(c) for c in version.split('.')]
__version__ = version  # compatibility
