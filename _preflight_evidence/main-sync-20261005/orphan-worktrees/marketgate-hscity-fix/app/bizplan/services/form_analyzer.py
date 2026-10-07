# form_analyzer.py -- bizplan domain wrapper
# Canonical: bizplan.services.form_analyzer (implementation in auto_write.services)
from auto_write.services.form_analyzer import analyze_form, classify_field_kind, FormReport  # TODO: migrate impl

__all__ = ['analyze_form', 'classify_field_kind', 'FormReport']
