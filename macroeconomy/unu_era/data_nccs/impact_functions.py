import pycountry
from climada.entity import ImpactFuncSet, ImpactFunc
from nccs.pipeline.direct.direct import apply_sector_impf_set

# Borrowing impact functions from NCCS
# (Sept 2024) these are undergoing calibration so it's worth coming back again soon

def get_nccs_impact_function_set(country, hazard_name, sector, business_interruption):
    return ImpactFuncSet([get_nccs_impact_function(country, hazard_name, sector, business_interruption)])


def get_nccs_impact_function(country, hazard_name, sector, business_interruption):
    sector = 'service' if sector == 'services' else sector
    country_iso3alpha = pycountry.countries.get(name=country).alpha_3
    if hazard_name != 'flood':
        raise ValueError('Not ready for non-flood hazards')
    impf_set = apply_sector_impf_set('river_flood', sector, country_iso3alpha, business_interruption=business_interruption, calibrated=True)
    impf = impf_set.get_func(haz_type='RF')[0]
    impf.haz_type = 'FL'   # In the UNU project flood has hazard ID 'FL'
    return impf


