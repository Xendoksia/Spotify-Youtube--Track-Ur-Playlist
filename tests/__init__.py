"""
Tests: python -m unittest   (from the project folder)

They never touch the real databases, config.json or any service: each test works in a temporary folder,
and the clock and the recorder's database calls are replaced where needed.
"""
