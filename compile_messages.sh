#!/bin/bash

pybabel extract -o oarepo_records_draft/translations/messages.pot oarepo_records_draft
pybabel update -d oarepo_records_draft/translations -i oarepo_records_draft/translations/messages.pot -l cs
pybabel update -d oarepo_records_draft/translations -i oarepo_records_draft/translations/messages.pot -l en
pybabel compile -d oarepo_records_draft/translations

