"""Reload coherent beneficiary profiles on Streamlit hot deployment."""
import importlib
from . import business_memory
_memory = importlib.reload(business_memory)
build_business_memory = _memory.build_business_memory
recall = _memory.recall
