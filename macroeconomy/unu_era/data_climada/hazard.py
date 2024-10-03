# Data sources from CLIMADA

import functools
import pycountry
from climada.util.api_client import Client

@functools.cache
def get_climada_flood_hazard(country, climate_scenario):
    country_iso3alpha = pycountry.countries.get(name=country).alpha_3
    client = Client()

    if climate_scenario == 'historical':
        api_year_range = '1980_2000'
    elif climate_scenario == 'rcp26':
        api_year_range = '2050_2070'
    elif climate_scenario == 'rcp85':
        api_year_range = '2050_2070'
    else:
        raise ValueError('Unexpected flood climate_scenario name. Choose historical, rcp26 or rcp85')

    haz = client.get_hazard(
        'river_flood',
        properties={
            'country_iso3alpha': country_iso3alpha,
            'climate_scenario': climate_scenario,
            'year_range': api_year_range
        }
    )
    haz.haz_type = 'FL'   # River flood is FL in the UNU project
    return haz