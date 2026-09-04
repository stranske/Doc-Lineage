"""Document lineage: identity, extraction with page pointers, and version and family comparison for recurring investment documents

The two helpers below are the Template's scaffold and are exercised by tests/test_main.py.
They stay until real modules replace them, so the package always has a tested public surface.
"""

__version__ = "0.1.0"
__all__ = ["greet", "add"]


def greet(name: str) -> str:
    """Return a greeting message.

    Args:
        name: The name to greet.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b
