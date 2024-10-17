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
from macroeconomy.unu_era.data_nccs.impact_functions import get_nccs_impact_function, get_nccs_impact_function_set
from macroeconomy.unu_era.data_unu.entity import ENTITY_CODES, get_unu_entity, get_unu_exposure, get_unu_impf, get_unu_impf_set
from macroeconomy.unu_era.data_unu.hazard import get_unu_heatwave_hazard, get_unu_flood_hazard
from macroeconomy.unu_era.interpolation import interpolate_ev


# This is your one-stop shop for all impact data used in the UNU ERA calculations

HAZARD_TYPES = [
    'flood',
    'heatwave'
    ]

CLIMATE_SCENARIOS = [
    'historical',
    'rcp26',
    'rcp85'
]

HAZ_EXPOSURE_IMPACTS = {
    'thailand': { 
        'flood': [
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
        'heatwave': [],
        'drought': []
    },
    'egypt': {
        'flood': [
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
        ],
        'heatwave': [
            ('housing', 'asset loss')
        ]
    }
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


def create_yearset(imp, n_sim_years, seed=None):
    if len(np.unique(imp.frequency) == 1):   # Annual-ish event data
        return yearset_from_imp(imp, n_sim_years, seed=seed)
    if len(imp.at_event) < 15:       # Return period data
        return yearset_from_rp(imp, n_sim_years, seed=seed)
    else:                            # Uhh ... tropical cyclone data?
        raise ValueError('Unrecognised form of impact object. Please add code to handle this')


def yearset_from_rp(imp, n_sim_years, seed=None):
    # Handle an impact object containing  return period impacts
    sample_rps = np.array([1/f for f in np.random.random(n_sim_years)])  # Sample return periods
    rp_list = np.array([1/f for f in imp.frequency])
    rp_impacts = imp.at_event
    annual_impacts = interpolate_ev(
        x_test = sample_rps,
        x_train = rp_list,
        y_train = rp_impacts,
        logx = True,
        logy = True,
        x_threshold = None,
        y_threshold = None,
        extrapolation = False,
        y_asymptotic = np.nan
    )
    ys = Impact(
        event_id = np.arange(n_sim_years),
        event_name = [str(i) for i in np.arange(n_sim_years)],
        frequency = np.ones_like(np.arange(n_sim_years)),
        coord_exp=None, # [(0,0)],
        aai_agg=np.mean(annual_impacts),
        at_event=annual_impacts,
        haz_type=imp.haz_type
    )



def get_hazard(hazard_type, country, climate_scenario):
    if hazard_type == 'flood':
        if True:
            return get_climada_flood_hazard(country, climate_scenario)
        return get_unu_flood_hazard(country, climate_scenario)
    elif hazard_type == 'heatwave':
        return get_unu_heatwave_hazard(country, climate_scenario)
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
    
        raise ValueError(f'We were not prepared for an exposure type of {exposure_type} in Thailand')

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
            if False:
                return get_unu_exposure(country, 'power plant')
            return get_nccs_sector_exposure(country, 'energy')

        # Tourism we assume is the same as hotels
        if exposure_type == 'tourism':
            if False:
                return get_unu_exposure(country, 'hotels')
            return get_nccs_sector_exposure(country, 'service')
    
        raise ValueError(f'We were not prepared for an exposure type of {exposure_type} in Egypt')

    raise ValueError(f'We were not prepared to get exposures from {country}. Please use either "thailand" or "egypt"')


def get_impact_funcset(hazard_type, exposure_type, impact_type, country):
    impact_tuple = (exposure_type, impact_type)
    if country == 'thailand':
        if hazard_type == 'flood':
            # Housing damage from CLIMADA
            if exposure_type == 'housing':
                return get_climada_flood_impact_function_set(country)

            # Agriculture is the sum of the two crop types in ERA
            # This misses livestock. Another option would be the NCCS agriculture but it's not calibrated well. We'll assume livestock are affected similarly
            if exposure_type == 'agriculture':
                trees = get_unu_impf(country, 'flood', 'tree crops', clip=(0, 100))
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

            # If we're requesting something from the ERA study, get it
            if exposure_type in ENTITY_CODES['thailand'].keys():
                return get_unu_impf_set(country, hazard_type, exposure_type)

            raise ValueError(f'We were not prepared for an exposure type of {exposure_type} in Thailand')
        raise ValueError(f'We were not prepared for an hazard type of {hazard_type} in Thailand')

    if country == 'egypt':
        if hazard_type == 'flood':
            # Housing damage from CLIMADA
            if exposure_type == 'housing':
                return get_climada_flood_impact_function_set(country)

            # Agriculture is the sum of crops and livestock in ERA
            if exposure_type == 'agriculture':
                if False:
                    crops = get_unu_impf(country, 'flood', 'crops', clip=(0, 100))
                    livestock = get_unu_impf(country, 'flood', 'livestock')
                    if impact_type in ['labour productivity', 'capital_productivity']:
                        crops = convert_impf_to_sectoral_bi_wet(crops, 'agriculture', crops.id)
                        livestock = convert_impf_to_sectoral_bi_wet(livestock, 'agriculture', livestock.id)
                    return ImpactFuncSet([crops, livestock])
                else:
                    if impact_type in ['labour productivity', 'capital_productivity']:
                        crops = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=True)
                        livestock = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=True)
                    else:
                        crops = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=False)
                        livestock = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=False)
                    crops.id = 501
                    livestock.id = 502
                    return ImpactFuncSet([crops, livestock])

            # Some sectors we borrow from NCCS
            if exposure_type in ['services', 'manufacturing']:
                if impact_type == 'asset loss':
                    return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=False)
                return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=True)

            # Energy we'll assume is the same as power plants, with business interruption as in the NCCS energy sector
            if exposure_type == 'energy':
                if False:
                    power = get_unu_impf(country, 'flood', 'power plant')
                    if impact_type in ['labour productivity', 'capital_productivity']:
                        power = convert_impf_to_sectoral_bi_wet(power, 'energy', power.id)
                    return ImpactFuncSet([power])

                if impact_type in ['labour productivity', 'capital_productivity']:
                    return get_nccs_impact_function_set(country, 'flood', 'energy', business_interruption=False)
                return get_nccs_impact_function_set(country, 'flood', 'energy', business_interruption=False)


            # Tourism we assume is the same asset loss as hotels, and buiness interuption as in the NCCS services sector 
            if exposure_type == 'tourism':
                if False:
                    hotels = get_unu_impf(country, 'flood', 'hotels')
                    if impact_type in ['labour productivity', 'capital_productivity']:
                        hotels = convert_impf_to_sectoral_bi_wet(hotels, 'service', hotels.id)
                    return ImpactFuncSet([hotels])
                
                if impact_type in ['labour productivity', 'capital_productivity']:
                    return get_nccs_impact_function_set(country, 'flood', 'service', business_interruption=True)
                return get_nccs_impact_function_set(country, 'flood', 'service', business_interruption=False)

            # If we're requesting something from the ERA study, get it
            if exposure_type in ENTITY_CODES['egypt'].keys():
                return get_unu_impf_set(country, hazard_type, exposure_type)

            raise ValueError(f'We were not prepared for an exposure type of {exposure_type} in Egypt')
        
        if hazard_type == 'heatwave':
            if exposure_type == 'agriculture':
                crops = get_unu_impf(country, 'heatwave', 'crops', clip=(0, 100))
                livestock = get_unu_impf(country, 'heatwave', 'livestock')
                if impact_type in ['labour productivity', 'capital_productivity']:
                    crops = convert_impf_to_sectoral_bi_dry(crops, 'agriculture', crops.id)
                    livestock = convert_impf_to_sectoral_bi_dry(livestock, 'agriculture', livestock.id)
                return ImpactFuncSet([crops, livestock])

        raise ValueError(f'We were not prepared for a hazard type of {hazard_type} in Egypt')

    raise ValueError(f'We were not prepared to get exposures from {country}. Please use either "thailand" or "egypt"')
