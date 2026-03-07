from langchain_core.tools import tool

@tool
def add_numbers(a: int, b: int) -> int:
    """
    Adds two integers.
    """
    return a + b

@tool
def multiply_numbers(a: int, b: int) -> int:
    """
    Multiplies two integers.
    """
    return a * b
