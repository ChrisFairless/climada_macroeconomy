import pandas as pd
import numpy as np

from climada.engine import Impact, ImpactCalc
from climada.entity import Exposures, ImpactFuncSet
from nccs.pipeline.direct.calc_yearset import yearset_from_imp
from nccs.pipeline.direct.business_interruption import convert_impf_to_sectoral_bi_wet

from macroeconomy.unu_era.data_climada.hazard import get_climada_flood_hazard
from macroeconomy.unu_era.data_climada.exposure import get_climada_economic_assets
from macroeconomy.unu_era.data_climada.impact_functions import get_climada_flood_impact_function_set
from macroeconomy.unu_era.data_nccs.exposure import get_nccs_sector_exposure
from macroeconomy.unu_era.data_nccs.impact_functions import get_nccs_impact_function_set
from macroeconomy.unu_era.data_unu.entity import ENTITY_CODES, get_unu_entity, get_unu_exposure, get_unu_impf, get_unu_impf_set


# This is your one-stop shop for all impact data used in the UNU ERA calculations

HAZARD_TYPES = [
    'flood'
    ]

CLIMATE_SCENARIOS = [
    'historical',
    'rcp26',
    'rcp85'
]


EXPOSURE_IMPACT_TYPES = {
    'thailand': [
        # Modelled by the UNU ERA team
        ('people', 'diarrhea'),
        ('people - students', ''),
        ('people - monks', ''),
        ('people - tree farmers', ''),
        ('people - grass farmers', ''),
        # ('people - water', ''),
        ('roads', 'mobility'),
        ('tree crops', 'asset loss'),
        ('grass crops', 'asset loss'),
        ('markets', 'asset loss'),
        # Additionally modelled by CRED
        ('housing', 'asset loss'),
        ('agriculture', 'asset loss'),
        ('agriculture', 'labour productivity'),
        ('agriculture', 'capital productivity'),
        ('services', 'asset loss'),
        ('services', 'labour productivity'),
        ('services', 'capital productivity'),
        ('tourism', 'asset loss'),
        ('tourism', 'labour productivity'),
        ('tourism', 'capital productivity'),
        ('energy', 'asset loss'),
        ('energy', 'labour productivity'),
        ('energy', 'capital productivity'),
        ('manufacturing', 'asset loss'),
        ('manufacturing', 'labour productivity'),
        ('manufacturing', 'capital productivity')
    ],
    'egypt': [
        # Modelled by the UNU ERA team
        ('crops', 'asset loss'),
        ('livestock', 'asset loss'),
        ('hotels', 'asset loss'),
        ('power plant', 'asset loss'),
        ('roads', 'mobility'),
        ('people', 'health'),
        ('people - students', ''),
        # Additionally modelled by CLIMADA/CRED
        ('housing', 'asset loss'),
        ('agriculture', 'asset loss'),
        ('agriculture', 'labour productivity'),
        ('agriculture', 'capital productivity'),
        ('services', 'asset loss'),
        ('services', 'labour productivity'),
        ('services', 'capital productivity'),
        ('tourism', 'asset loss'),
        ('tourism', 'labour productivity'),
        ('tourism', 'capital productivity'),
        ('energy', 'asset loss'),
        ('energy', 'labour productivity'),
        ('energy', 'capital productivity'),
        ('manufacturing', 'asset loss'),
        ('manufacturing', 'labour productivity'),
        ('manufacturing', 'capital productivity')        
    ]
}



def get_impact_yearset(hazard_type, exposure_type, impact_type, country, climate_scenario, n_sim_years, normalise, seed=161):
    imp = get_impact(hazard_type, exposure_type, impact_type, country, climate_scenario, normalise)
    return create_yearset(imp, n_sim_years, seed)
    


def get_impact(hazard_type, exposure_type, impact_type, country, climate_scenario, normalise):
    haz = get_hazard(hazard_type, country, climate_scenario)
    exp = get_exposure(exposure_type, country)
    if normalise:
        exp.gdf['value'] = exp.gdf['value'] / sum(exp.gdf['value'])
    impf_set = get_impact_funcset(hazard_type, exposure_type, impact_type, country)
    return ImpactCalc(exp, impf_set, haz).impact(save_mat=True)



def create_yearset(imp, n_sim_years, seed):
    return yearset_from_imp(imp, n_sim_years, cap_exposure=1, seed=seed)


def get_hazard(hazard_type, country, climate_scenario):
    if hazard_type == 'flood':
        return get_climada_flood_hazard(country, climate_scenario)
    else:
        raise ValueError(f"Can't currently get {hazard_type} data")


def scale_impact(imp, scaling):
    assert(scaling <= 1)
    return Impact(
        event_id=imp.event_id,
        event_name=imp.event_name,
        date=imp.date,
        frequency=imp.frequency,
        frequency_unit=imp.frequency_unit,
        coord_exp=imp.coord_exp,
        crs=imp.crs,
        eai_exp=imp.eai_exp * scaling,
        at_event=imp.at_event * scaling,
        tot_value=imp.tot_value,
        aai_agg=imp.aai_agg * scaling,
        unit=imp.unit,
        imp_mat=None if not imp.imp_mat else imp.imp_mat * scaling,
        haz_type=imp.haz_type
    )


def get_exposure(exposure_type, country):
    if country == 'thailand':
        # If we're requesting something from the ERA study, get it
        if exposure_type in ENTITY_CODES['thailand'].keys():
            return get_unu_exposure(country, exposure_type)
    
        # Housing is CLIMADA's LitPop
        if exposure_type == 'housing':
            return get_climada_economic_assets(country)

        # Agriculture is the sum of the two crop types in ERA
        # This misses livestock. Another option would be the NCCS agriculture but it's not calibrated well. We'll assume livestock are affected similarly
        if exposure_type == 'agriculture':
            trees = get_unu_exposure(country, 'tree crops')
            grasses = get_unu_exposure(country, 'grass crops')
            return Exposures.concat([trees, grasses])

        # Some sectors we borrow from NCCS
        if exposure_type in ['services', 'energy', 'manufacturing']:
            return get_nccs_sector_exposure(country, exposure_type)
        
        # Tourism we pretend is the same as services
        # (which in turn is just LitPop: we have to remember not to look at the absolute values here...)
        if exposure_type == 'tourism':
            return get_nccs_sector_exposure(country, 'services')
    
        raise ValueError(f'We were note prepared for an exposure type of {exposure_type} in Thailand')

    if country == 'egypt':
        # If we're requesting something from the ERA study, get it
        if exposure_type in ENTITY_CODES['egypt'].keys():
            return get_unu_exposure(country, exposure_type)

        # Housing is  CLIMADA's LitPop
        if exposure_type == 'housing':
            return get_climada_economic_assets(country)

        # Agriculture is the sum of crops and livestock in ERA
        if exposure_type == 'agriculture':
            crops = get_unu_exposure(country, 'crops')
            livestock = get_unu_exposure(country, 'livestock')
            return Exposures.concat([crops, livestock])

        # Some sectors we borrow from NCCS
        if exposure_type in ['services', 'manufacturing']:
            return get_nccs_sector_exposure(country, exposure_type)

        # Energy we'll assume is the same as power plants
        if exposure_type == 'energy':
            return get_unu_exposure(country, 'power plant')

        # Tourism we assume is the same as hotels
        if exposure_type == 'tourism':
            return get_unu_exposure(country, 'hotels')

        raise ValueError(f'We were note prepared for an exposure type of {exposure_type} in Egypt')

    raise ValueError(f'We were note prepared to get exposures from {country}. Please use either "thailand" or "egypt"')


def get_impact_funcset(hazard_type, exposure_type, impact_type, country):
    impact_tuple = (exposure_type, impact_type)
    if hazard_type != 'flood':
        raise ValueError('Sorry I am not ready for non-flood hazards')
    
    if country == 'thailand':
        # If we're requesting something from the ERA study, get it
        if exposure_type in ENTITY_CODES['thailand'].keys():
            return get_unu_impf_set(country, hazard_type, exposure_type)
        
        # Housing damage from CLIMADA
        if exposure_type == 'housing':
            return get_climada_flood_impact_function_set(country)

        # Agriculture is the sum of the two crop types in ERA
        # This misses livestock. Another option would be the NCCS agriculture but it's not calibrated well. We'll assume livestock are affected similarly
        if exposure_type == 'agriculture':
            trees = get_unu_impf(country, 'flood', 'tree crops')
            grasses = get_unu_impf(country, 'flood', 'grass crops')
            if impact_type in ['labour productivity', 'capital_productivity']:
                trees = convert_impf_to_sectoral_bi_wet(trees, 'agriculture', trees.id)
                grasses = convert_impf_to_sectoral_bi_wet(trees, 'agriculture', grasses.id)
            return ImpactFuncSet([trees, grasses])

        # Some sectors we borrow from NCCS
        if exposure_type in ['services', 'energy', 'manufacturing']:
            if impact_type == 'asset loss':
                return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=False)
            return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=True)
        
        # Tourism we pretend is the same as services
        # (which in turn is just LitPop: we have to remember not to look at the absolute values here...)
        if exposure_type == 'tourism':
            if impact_type == 'asset loss':
                return get_nccs_impact_function_set(country, hazard_type, 'services', business_interruption=False)
            return get_nccs_impact_function_set(country, hazard_type, 'services', business_interruption=True)

        raise ValueError(f'We were note prepared for an exposure type of {exposure_type} in Thailand')

    if country == 'egypt':
        # If we're requesting something from the ERA study, get it
        if exposure_type in ENTITY_CODES['egypt'].keys():
            return get_unu_impf_set(country, hazard_type, exposure_type)

        # Housing damage from CLIMADA
        if exposure_type == 'housing':
            return get_climada_flood_impact_function_set(country)

        # Agriculture is the sum of crops and livestock in ERA
        if exposure_type == 'agriculture':
            crops = get_unu_impf(country, 'flood', 'crops')
            livestock = get_unu_impf(country, 'flood', 'livestock')
            if impact_type in ['labour productivity', 'capital_productivity']:
                crops = convert_impf_to_sectoral_bi_wet(crops, 'agriculture', crops.id)
                livestock = convert_impf_to_sectoral_bi_wet(livestock, 'agriculture', livestock.id)
            return ImpactFuncSet([crops, livestock])

        # Some sectors we borrow from NCCS
        if exposure_type in ['services', 'manufacturing']:
            if impact_type == 'asset loss':
                return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=False)
            return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=True)

        # Energy we'll assume is the same as power plants, with business interruption as in the NCCS energy sector
        if exposure_type == 'energy':
            power = get_unu_impf(country, 'flood', 'power plant')
            if impact_type in ['labour productivity', 'capital_productivity']:
                power = convert_impf_to_sectoral_bi_wet(power, 'energy', power.id)
            return ImpactFuncSet([power])

        # Tourism we assume is the same asset loss as hotels, and buiness interuption as in the NCCS services sector 
        if exposure_type == 'tourism':
            hotels = get_unu_impf(country, 'flood', 'hotels')
            if impact_type in ['labour productivity', 'capital_productivity']:
                hotels = convert_impf_to_sectoral_bi_wet(hotels, 'service', hotels.id)
            return ImpactFuncSet([hotels])

        raise ValueError(f'We were note prepared for an exposure type of {exposure_type} in Egypt')

    raise ValueError(f'We were note prepared to get exposures from {country}. Please use either "thailand" or "egypt"')
