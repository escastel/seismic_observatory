"""Accelerated replay of a historical selection (spec 005).

The replay reads events already downloaded under data/usgs/catalog/, registers
the selection in core.extraction and publishes it to the replay topic. The
consumer writes it to the replay schema; core is never touched.
"""
