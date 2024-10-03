import pycountry
from climada.util.api_client import Client

def get_climada_economic_assets(country):
    country_iso3alpha = pycountry.countries.get(name=country).alpha_3
    client = Client()
    return client.get_litpop(country = country_iso3alpha, exponents = (1, 1))

def get_climada_population(country):
    country_iso3alpha = pycountry.countries.get(name=country).alpha_3
    client = Client()
    return client.get_litpop(country = country_iso3alpha, exponents = (0, 1))