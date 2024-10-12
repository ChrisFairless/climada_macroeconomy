import pycountry
import pandas as pd
from climada.entity import ImpactFuncSet
from climada_petals.entity.impact_funcs.river_flood import RIVER_FLOOD_REGIONS_CSV, flood_imp_func_set

# Warning: this is not calibrated for the data that we're using at the UN
# TODO update to calibrated impact function
def get_climada_flood_impact_function(country, haz_type='FL'):
    country_iso3alpha = pycountry.countries.get(name=country).alpha_3
    country_info = pd.read_csv(RIVER_FLOOD_REGIONS_CSV)
    impf_id = country_info.loc[country_info['ISO'] == country_iso3alpha, 'impf_RF'].values[0]
    impf_set = flood_imp_func_set()
    impf = impf_set.get_func(haz_type='RF', fun_id=impf_id)
    impf.id = 1
    impf.haz_type = haz_type   # In the UNU project flood has hazard ID 'FL'
    return impf

def get_climada_flood_impact_function_set(country, haz_type='FL'):
    return ImpactFuncSet([get_climada_flood_impact_function(country, haz_type)])
