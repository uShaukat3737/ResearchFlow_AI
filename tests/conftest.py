import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graph.builder import create_research_graph


@pytest.fixture
def graph():
    return create_research_graph()
