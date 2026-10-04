"""The pure pricing engine.

It imports neither Django nor any app of this project. It takes immutable
inputs and an explicit ``now``, never reads the clock, the database or the
network, and returns the same result for the same inputs and version.
"""
