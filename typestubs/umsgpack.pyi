import typing

def packb(
    obj: typing.Union[
        None,
        bytes,
        typing.Dict[typing.Any, typing.Any],
        float,
        int,
        typing.Sequence[typing.Any],
        str,
    ],
    ext_handlers: typing.Optional[typing.Dict[str, typing.Any]] = None,
    force_flat_precision: typing.Optional[str] = None,
) -> bytes: ...
def unpackb(
    val: bytes,
) -> typing.Union[
    None,
    bytes,
    typing.Dict[typing.Any, typing.Any],
    float,
    int,
    typing.List[typing.Any],
    str,
]: ...
