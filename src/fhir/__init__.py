"""FHIR module - FHIR API 客戶端與工具"""

from .client import fhir_get, fhir_post
from .tools import register_fhir_tools
from .composite import register_composite_tools

__all__ = ["fhir_get", "fhir_post", "register_fhir_tools", "register_composite_tools"]
