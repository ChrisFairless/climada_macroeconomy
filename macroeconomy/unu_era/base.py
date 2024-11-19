import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix

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
from macroeconomy.unu_era.data_unu.hazard import get_unu_heatwave_hazard, get_unu_flood_hazard, get_unu_drought_hazard
from macroeconomy.unu_era.data_unu.impact_functions import get_unu_heatwave_impfset_agriculture_labour, get_unu_heatwave_impfset_manufacturing_labour, get_unu_heatwave_impfset_tourism_labour, get_unu_heatwave_impfset_energy_labour, get_unu_heatwave_impfset_services_labour
from macroeconomy.unu_era.interpolation import interpolate_ev


# This is your one-stop shop for all impact data used in the UNU ERA calculations
v1 = True   # For v1: use NCCS data for flood

HAZARD_TYPES = [
    'flood',
    'heatwave',
    'drought'
    ]

CLIMATE_SCENARIOS = [
    'historical',
    'rcp26',
    'rcp85'
]

HAZ_EXPOSURE_IMPACTS = {
    'thailand': { 
        'flood': [
            # # Modelled by the UNU ERA team
            # ('people', 'diarrhea'),
            # ('people - students', ''),
            # ('people - monks', ''),
            # ('people - tree farmers', ''),
            # ('people - grass farmers', ''),
            # # ('people - water', ''),
            # ('roads', 'mobility'),
            # ('tree crops', 'asset loss'),
            # ('grass crops', 'asset loss'),
            # ('markets', 'asset loss'),

            # Modelled by CRED
            ('housing', 'asset loss'),
            ('agriculture', 'asset loss'),
            ('agriculture', 'capital productivity'),
            ('services', 'asset loss'),
            ('services', 'capital productivity'),
            ('tourism', 'asset loss'),
            ('tourism', 'capital productivity'),
            ('energy', 'asset loss'),
            ('energy', 'capital productivity'),
            ('manufacturing', 'asset loss'),
            ('manufacturing', 'capital productivity')
        ],
        'heatwave': [
            ('agriculture', 'labour productivity'),
            ('services', 'labour productivity'),
            ('tourism', 'labour productivity'),
            ('energy', 'labour productivity'),
            ('manufacturing', 'labour productivity'),
        ],
        'drought': [
            ('agriculture', 'asset loss'),
        ]
    },
    'egypt': {
        'flood': [
            # # Modelled by the UNU ERA team
            # ('crops', 'asset loss'),
            # ('livestock', 'asset loss'),
            # ('hotels', 'asset loss'),
            # ('power plant', 'asset loss'),
            # ('roads', 'mobility'),
            # ('people', 'health'),
            # ('people - students', ''),
            
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
            ('agriculture', 'labour productivity'),
            ('tourism', 'labour productivity'),
            ('energy', 'labour productivity'),
            ('manufacturing', 'labour productivity'),
        ]
    }
}

# Scaling factors to bring the AAI up to the UNU waterfall values
SCALING_V1 = {
    'thailand': {
        'flood': {
            'agriculture': {  # apply to all impact_types
                'historical': 16.36,
                'rcp26': 4.74,
                'rcp85': 6.96
            }
        },
        # 'drought': {
        #     'agriculture': {
        #         'historical': 0.16,
        #         'rcp26': 0.37,
        #         'rcp85': 0.46
        #     }
        # }
    }
}


def get_impact_yearset(hazard_type, exposure_type, impact_type, country, climate_scenario, n_sim_years, normalise, seed=None):
    imp = get_impact(hazard_type, exposure_type, impact_type, country, climate_scenario, normalise)
    if hazard_type == 'flood':
        return create_yearset(imp, n_sim_years, seed)
    return yearset_from_rp(imp, n_sim_years, seed)

def get_impact(hazard_type, exposure_type, impact_type, country, climate_scenario, normalise):
    haz = get_hazard(hazard_type, country, climate_scenario)
    exp = get_exposure(exposure_type, country, hazard_type)
    if normalise:
        exp.gdf['value'] = exp.gdf['value'] / sum(exp.gdf['value'])
    impf_set = get_impact_funcset(hazard_type, exposure_type, impact_type, country)
    if v1:
        try:
            scale = SCALING_V1[country][hazard_type][exposure_type][climate_scenario]            
            impf_set = scale_impf_set(impf_set, scale)
        except KeyError:
            # No scaling defined for this combination
            pass
    return ImpactCalc(exp, impf_set, haz).impact(save_mat=True)


def scale_impf_set(impf_set, scale):
    out = []
    haz_type = impf_set.get_hazard_types()
    assert(len(haz_type) == 1)
    for id in impf_set.get_ids(haz_type[0]):
        impf = impf_set.get_func(haz_type=haz_type[0], fun_id=id)
        impf.mdd = impf.mdd * scale
        out.append(impf)
    return ImpactFuncSet(out)


def create_yearset(imp, n_sim_years, seed=None):
    if len(np.unique(imp.frequency)) == 1:   # Annual-ish event data
        return yearset_from_imp(imp, n_sim_years, seed=seed)
    if len(imp.at_event) < 15:       # Return period data
        return yearset_from_rp(imp, n_sim_years, seed=seed)
    else:                            # Uhh ... tropical cyclone data?
        raise ValueError('Unrecognised form of impact object. Please add code to handle this')


def yearset_from_rp(imp, n_sim_years, seed=None):
    # Handle an impact object containing return period impacts
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
        extrapolation = True,
        y_asymptotic = np.nan
    )
    annual_impacts = np.clip(annual_impacts, 0, np.max(imp.at_event))
    if np.any(annual_impacts > 1):
        raise ValueError('The yearset generator somehow created an impact > 1. For the moment we do not allow that')
    ys = Impact(
        event_id = np.arange(n_sim_years),
        event_name = [str(i) for i in np.arange(n_sim_years)],
        date = np.zeros_like(np.arange(n_sim_years)),
        frequency = np.ones_like(np.arange(n_sim_years)),
        coord_exp=np.array([np.array([0,0])]),
        imp_mat=csr_matrix([[x] for x in annual_impacts]),
        eai_exp=np.array([np.mean(annual_impacts)]),
        aai_agg=np.mean(annual_impacts),
        at_event=annual_impacts,
        haz_type=imp.haz_type
    )
    return ys



def get_hazard(hazard_type, country, climate_scenario):
    if country == 'egypt':
        if hazard_type == 'flood':
            if v1:
                return get_climada_flood_hazard(country, climate_scenario)
            return get_unu_flood_hazard(country, climate_scenario)
        if hazard_type == 'heatwave':
            return get_unu_heatwave_hazard(country, climate_scenario)
        raise ValueError(f"Can't currently get {hazard_type} data for {country}")
    if country == 'thailand':
        if hazard_type == 'flood':
            if v1:
                return get_climada_flood_hazard(country, climate_scenario)
            return get_unu_flood_hazard(country, climate_scenario)
        if hazard_type == 'heatwave':
            return get_unu_heatwave_hazard(country, climate_scenario)
        if hazard_type == 'drought':
            return get_unu_drought_hazard(country, climate_scenario, invert=True)
        raise ValueError(f"Can't currently get {hazard_type} data for {country}")
    raise ValueError(f'No data for country {country}')



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


def get_exposure(exposure_type, country, hazard_name):
    if country == 'thailand':
        # Housing is CLIMADA's LitPop
        if exposure_type == 'housing':
            return get_climada_economic_assets(country)

        # Agriculture is the sum of the two crop types in ERA
        # This misses livestock. Another option would be the NCCS agriculture but it's not calibrated well. We'll assume livestock are affected similarly
        if exposure_type == 'agriculture':
            if hazard_name in ['flood', 'drought']:
                trees = get_unu_exposure(country, 'tree crops', hazard_name)
                grasses = get_unu_exposure(country, 'grass crops', hazard_name )
            elif hazard_name == 'heatwave':
                trees = get_unu_exposure(country, 'tree crops', 'flood')
                grasses = get_unu_exposure(country, 'grass crops', 'flood')
            else:
                raise ValueError(f'Unrecognised hazard: {hazard_name}')
            return Exposures.concat([trees, grasses])

        # Some sectors we borrow from NCCS
        if exposure_type in ['services', 'energy', 'manufacturing']:
            return get_nccs_sector_exposure(country, exposure_type)
        
        # Tourism we pretend is the same as services
        # (which in turn is just LitPop: we have to remember not to look at the absolute values here...)
        if exposure_type == 'tourism':
            return get_nccs_sector_exposure(country, 'services')
    
        # Otherwise if we're requesting something from the ERA study, get it
        if exposure_type in ENTITY_CODES['thailand'].keys():
            return get_unu_exposure(country, exposure_type, hazard_name)

        raise ValueError(f'We were not prepared for an exposure type of {exposure_type} in Thailand')

    if country == 'egypt':
        # If we're requesting something from the ERA study, get it
        if exposure_type in ENTITY_CODES['egypt'].keys():
            return get_unu_exposure(country, exposure_type, hazard_name)

        # Housing is  CLIMADA's LitPop
        if exposure_type == 'housing':
            return get_climada_economic_assets(country)

        # Agriculture is the sum of crops and livestock in ERA
        if exposure_type == 'agriculture':
            crops = get_unu_exposure(country, 'crops', hazard_name)
            livestock = get_unu_exposure(country, 'livestock', hazard_name)
            return Exposures.concat([crops, livestock])

        # Some sectors we borrow from NCCS
        if exposure_type in ['services', 'manufacturing']:
            return get_nccs_sector_exposure(country, exposure_type)

        # Energy we'll assume is the same as power plants
        if exposure_type == 'energy':
            if not v1:
                return get_unu_exposure(country, 'power plant', hazard_name)
            return get_nccs_sector_exposure(country, 'energy')

        # Tourism we assume is the same as hotels
        if exposure_type == 'tourism':
            if not v1:
                return get_unu_exposure(country, 'hotels', hazard_name)
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
            if exposure_type == 'agriculture':
                trees = get_unu_impf(country, 'flood', 'tree crops', clip=(0, 100))
                grasses = get_unu_impf(country, 'flood', 'grass crops', clip=(0, 100))
                if impact_type == 'asset loss':
                    return ImpactFuncSet([trees, grasses])
                if impact_type in ['labour productivity', 'capital productivity']:
                    trees = convert_impf_to_sectoral_bi_wet(trees, 'agriculture', trees.id)
                    grasses = convert_impf_to_sectoral_bi_wet(trees, 'agriculture', grasses.id)
                    return ImpactFuncSet([trees, grasses])
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            # Some sectors we borrow from NCCS
            if exposure_type in ['services', 'energy', 'manufacturing']:
                if impact_type == 'asset loss':
                    return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=False)
                if impact_type in ['labour productivity', 'capital productivity']:
                    return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=True)
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")
            
            # Tourism we pretend is the same as services
            # (which in turn is just LitPop: we have to remember not to look at the absolute values here...)
            if exposure_type == 'tourism':
                if impact_type == 'asset loss':
                    return get_nccs_impact_function_set(country, hazard_type, 'services', business_interruption=False)
                if impact_type in ['labour productivity', 'capital productivity']:
                    return get_nccs_impact_function_set(country, hazard_type, 'services', business_interruption=True)
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            # Otherwise if we're requesting something else from the ERA study, get it
            if exposure_type in ENTITY_CODES['thailand'].keys():
                return get_unu_impf_set(country, hazard_type, exposure_type)

            raise ValueError(f'We were not prepared for an exposure type of {exposure_type} for Thailand flood')
        
        if hazard_type == 'heatwave':
            if exposure_type == 'agriculture':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_agriculture_labour('thailand')
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            if exposure_type == 'manufacturing':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_manufacturing_labour()
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            if exposure_type == 'tourism':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_tourism_labour()
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            if exposure_type == 'energy':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_energy_labour()
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            if exposure_type == 'services':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_services_labour()
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            raise ValueError(f'We were not prepared for an exposure type of {exposure_type} for Thailand heatwave')

        if hazard_type == 'drought':
            if exposure_type == 'agriculture':
                trees = get_unu_impf(country, 'drought', 'tree crops') #, clip=(0, 100))
                grasses = get_unu_impf(country, 'drought', 'grass crops')
                if impact_type == 'asset loss':
                    return ImpactFuncSet([trees, grasses])
                # (No labour productivity loss from drought)
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            raise ValueError(f'We were not prepared for an exposure type of {exposure_type} for Thailand drought')

        raise ValueError(f'We were not prepared for a hazard type of {hazard_type} in Thailand')

    if country == 'egypt':
        if hazard_type == 'flood':
            # Housing damage from CLIMADA
            if exposure_type == 'housing':
                return get_climada_flood_impact_function_set(country)

            # Agriculture is the sum of crops and livestock in ERA
            if exposure_type == 'agriculture':
                if not v1:
                    crops = get_unu_impf(country, 'flood', 'crops', clip=(0, 100))
                    livestock = get_unu_impf(country, 'flood', 'livestock')
                    if impact_type == 'asset loss':
                        return ImpactFuncSet([crops, livestock])
                    if impact_type in ['labour productivity', 'capital productivity']:
                        crops = convert_impf_to_sectoral_bi_wet(crops, 'agriculture', crops.id)
                        livestock = convert_impf_to_sectoral_bi_wet(livestock, 'agriculture', livestock.id)
                        return ImpactFuncSet([crops, livestock])
                    raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")
                
                if impact_type == 'asset loss':
                    crops = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=False)
                    livestock = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=False)
                    crops.id = 501
                    livestock.id = 502
                    return ImpactFuncSet([crops, livestock])
                if impact_type in ['labour productivity', 'capital productivity']:
                    crops = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=True)
                    livestock = get_nccs_impact_function(country, 'flood', 'agriculture', business_interruption=True)
                    crops.id = 501
                    livestock.id = 502
                    return ImpactFuncSet([crops, livestock])
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            # Some sectors we borrow from NCCS
            if exposure_type in ['services', 'manufacturing']:
                if impact_type == 'asset loss':
                    return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=False)
                if impact_type in ['labour productivity', 'capital productivity']:
                    return get_nccs_impact_function_set(country, hazard_type, exposure_type, business_interruption=True)
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            # Energy we'll assume is the same as power plants, with business interruption as in the NCCS energy sector
            if exposure_type == 'energy':
                if not v1:
                    power = get_unu_impf(country, 'flood', 'power plant')
                    if impact_type == 'asset loss':
                        return ImpactFuncSet([power])
                    if impact_type in ['labour productivity', 'capital productivity']:
                        power = convert_impf_to_sectoral_bi_wet(power, 'energy', power.id)
                        return ImpactFuncSet([power])
                    raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

                if impact_type == 'asset loss':
                    return get_nccs_impact_function_set(country, 'flood', 'energy', business_interruption=False)
                if impact_type in ['labour productivity', 'capital productivity']:
                    return get_nccs_impact_function_set(country, 'flood', 'energy', business_interruption=False)
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            # Tourism we assume is the same asset loss as hotels, and buiness interuption as in the NCCS services sector 
            if exposure_type == 'tourism':
                if not v1:
                    hotels = get_unu_impf(country, 'flood', 'hotels')
                    if impact_type == 'asset loss':
                        return ImpactFuncSet([hotels])
                    if impact_type in ['labour productivity', 'capital productivity']:
                        hotels = convert_impf_to_sectoral_bi_wet(hotels, 'service', hotels.id)
                        return ImpactFuncSet([hotels])

                if impact_type == 'asset loss':
                    return get_nccs_impact_function_set(country, 'flood', 'service', business_interruption=False)
                if impact_type in ['labour productivity', 'capital productivity']:
                    return get_nccs_impact_function_set(country, 'flood', 'service', business_interruption=True)
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            # If we're requesting something from the ERA study, get it
            if exposure_type in ENTITY_CODES['egypt'].keys():
                return get_unu_impf_set(country, hazard_type, exposure_type)

            raise ValueError(f'We were not prepared for an exposure type of {exposure_type} in Egypt')
        
        if hazard_type == 'heatwave':
            if exposure_type == 'agriculture':
                if impact_type == "asset loss":
                    crops = get_unu_impf(country, 'heatwave', 'crops', clip=(0, 100))
                    livestock = get_unu_impf(country, 'heatwave', 'livestock')
                    return ImpactFuncSet([crops, livestock])
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_agriculture_labour('egypt')
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            if exposure_type == 'manufacturing':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_manufacturing_labour()
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            if exposure_type == 'tourism':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_tourism_labour()
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

            if exposure_type == 'energy':
                if impact_type == 'labour productivity':
                    return get_unu_heatwave_impfset_energy_labour()
                raise ValueError(f"We were not prepared for impact_type {impact_type} with exposure_type {exposure_type}")

        raise ValueError(f'We were not prepared for a hazard type of {hazard_type} in Egypt')

    raise ValueError(f'We were not prepared to get exposures from {country}. Please use either "thailand" or "egypt"')


