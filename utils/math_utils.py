"""Math utility functions for the project."""


def test_simple_addition(a: int, b: int) -> int:
    """Add two integers and return their sum.

    Args:
        a: The first integer to add.
        b: The second integer to add.

    Returns:
        The sum of a and b.

    Examples:
        >>> test_simple_addition(2, 3)
        5
        >>> test_simple_addition(-1, 1)
        0
        >>> test_simple_addition(100, 200)
        300
    """
    return a + b