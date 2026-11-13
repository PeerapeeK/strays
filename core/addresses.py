"""Local, static Thai administrative-area data.

The JSON file is served to the browser for the cascading address selects and
is read here for server-side validation. No external API or dependency is
required.
"""

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

DATA_RELATIVE_PATH = Path('static') / 'data' / 'thai_addresses.json'


@lru_cache(maxsize=1)
def load_address_data():
    path = Path(settings.BASE_DIR) / DATA_RELATIVE_PATH
    with path.open(encoding='utf-8') as handle:
        raw = json.load(handle)
    provinces = {}
    for province in raw['provinces']:
        districts = {}
        for district in province['districts']:
            districts[district['name']] = {
                item['name']: set(
                    item.get('postal_codes')
                    or [item.get('postal_code')]
                )
                for item in district['subdistricts']
            }
        provinces[province['name']] = districts
    return provinces


def province_names():
    return list(load_address_data().keys())


def district_names(province):
    return list(load_address_data().get(province, {}).keys())


def subdistrict_names(province, district):
    return list(load_address_data().get(province, {}).get(district, {}).keys())


def postal_codes_for(province, district, subdistrict):
    return (
        load_address_data()
        .get(province, {})
        .get(district, {})
        .get(subdistrict, set())
    )


def address_is_valid(province, district, subdistrict, postal_code):
    return bool(
        province
        and district
        and subdistrict
        and postal_code
        and postal_code in postal_codes_for(province, district, subdistrict)
    )


def compose_address(detail, subdistrict, district, province, postal_code):
    parts = [
        (detail or '').strip(),
        f'ต.{subdistrict}' if subdistrict else '',
        f'อ.{district}' if district else '',
        f'จ.{province}' if province else '',
        (postal_code or '').strip(),
    ]
    return ' '.join(part for part in parts if part)
