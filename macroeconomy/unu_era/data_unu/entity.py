import functools
from copy import deepcopy
import numpy as np
from pathlib import Path
from climada.entity import Entity, ImpactFuncSet

# Some functions to make our UNU project more friendly

DATA_DIR = {
    'thailand': '/Users/chrisfairless/Projects/UNU/data/Thailand',
    'egypt': '/Users/chrisfairless/Projects/UNU/data/Egypt'
}

ENTITY_FILES = {
    'thailand': {
        'flood': {
            'people - monks':           '5_entity_TODAY_THAI_Flood_ppl_others.xlsx',
            'people - students':        '5_entity_TODAY_THAI_Flood_ppl_others.xlsx',
            'people - tree farmers':    '5_entity_TODAY_THAI_Flood_ppl_1_farmers.xlsx',
            'people - grass farmers':   '5_entity_TODAY_THAI_Flood_ppl_1_farmers.xlsx',
            'people':                   '5_entity_TODAY_THAI_Flood_ppl_diarrhea.xlsx',
            'tree crops':               '4_entity_TODAY_THAI_Flood_USD_1.xlsx',
            'grass crops':              '4_entity_TODAY_THAI_Flood_USD_1.xlsx',
            'markets':                  '4_entity_TODAY_THAI_Flood_USD_1.xlsx',            
            'roads':                    '6_entity_TODAY_THAI_Flood_roads_1.xlsx'
        }
    },
    'egypt': {
        'flood': {
            'people - students':        '3_entity_TODAY_EGYPT_Flood_ppl_students.xlsx',
            'people':                   '3_entity_TODAY_EGYPT_Flood_ppl.xlsx',
            'roads':                    '4_entity_TODAY_EGYPT_Flood_roads_2km.xlsx',
            'crops':                    '5_entity_TODAY_EGYPT_Flood_USD_new.xlsx',
            'livestock':                '5_entity_TODAY_EGYPT_Flood_USD_new.xlsx',
            'hotels':                   '5_entity_TODAY_EGYPT_Flood_USD_new.xlsx',
            'power plant':              '5_entity_TODAY_EGYPT_Flood_USD_new.xlsx'
        }
    }
}

ENTITY_CODES = {
    'thailand': {
        'people - monks': 101,
        'people - students': 102,
        'people - tree farmers': 103,
        'people - grass farmers': 104,
        'people': 105,
        'tree crops': 201,
        'grass crops': 202,
        'markets': 203,
        'roads': 301
    },
    'egypt': {
        'people - students': 301,
        'people': 302,
        'roads': 401,
        'crops': 501,
        'livestock': 502,
        'hotels': 503,
        'power plant': 504
    }
}

def get_unu_entity(country, hazard_name, exposure_name):
    filename = ENTITY_FILES[country][hazard_name][exposure_name]
    pathname = Path(DATA_DIR[country], filename)

    entity = deepcopy(_load_unu_entity(pathname))

    # Subset everything to a single exposure type if requested
    category_id = ENTITY_CODES[country][exposure_name]
    if not category_id:
        raise ValueError(f'Could not find an id for {country} {exposure_name}')
    entity.exposures.gdf = entity.exposures.gdf.loc[entity.exposures.gdf['category_id'] == category_id, ]
    impf_list = entity.impact_funcs.get_func(fun_id = category_id)
    assert(len(impf_list) == 1)  # There should only be one impact function with this ID since it's a one-hazard entity file
    entity.impact_funcs = ImpactFuncSet(impf_list)

    return entity, category_id


# In my current workflow we read these files quite often. Turn this off to save a bit of RAM
@functools.cache
def _load_unu_entity(pathname):
    entity = Entity.from_excel(pathname)
    # Set default impact function ID equal to the category ID
    entity.exposures.gdf['impf_'] = entity.exposures.gdf['category_id']
    # Remove cover and deductible columns: we don't want to do any insurance calculations yet
    entity.exposures.gdf.drop(columns=['cover', 'deductible'], inplace=True)
    return entity


def get_unu_exposure(country, exposure_name):
    entity, category_id = get_unu_entity(country, hazard_name='flood', exposure_name=exposure_name)
    exp = entity.exposures
    return exp


# In the current setup there is only one impact per type of exposure, 
# so we don't need to stress about an impact_type parameter here. Yet.
def get_unu_impf(country, hazard_name, exposure_name = None):
    if hazard_name != 'flood':
        raise ValueError('Not ready for non-flood hazards')
    entity, category_id = get_unu_entity(country, hazard_name=hazard_name, exposure_name=exposure_name)
    impf = entity.impact_funcs.get_func(haz_type = 'FL', fun_id = category_id)

    # Can't currently deal with negative impacts, sorry!
    impf.mdd = np.clip(impf.mdd, 0, 100)

    # bugfix for diarrhoea and people - health which needs 0 impact at 0 hazard
    if impf.mdd[0] != 0:
        if impf.id not in [105, 302]: 
            raise ValueError(f'Unexpected non-zero impact function MDD. Thought this was just the case with diarrhoea and health. If you want to fix this add the id {impf.id} to the list where this error is called') 
        impf.intensity = np.append(np.array([0]), impf.intensity)
        impf.paa = np.append(np.array([1]), impf.paa)
        impf.mdd = np.append(np.array([0]), impf.mdd)
    
    return drop_impf_leading_zeroes(impf)


def drop_impf_leading_zeroes(impf):
    if impf.calc_mdr(impf.intensity[1]) != 0:
        return impf
    if impf.mdd[1] != 0:
        raise ValueError('This impact function is too complex for my simple simplification. Looks like it has a paa of zero somewhere...')
    if impf.calc_mdr(impf.intensity[0]) != 0:
        raise ValueError('This impact function is too complex for my simple simplification. Looks like it has a non-zero mdr when the hazard is zero, and a zero after that...')
    impf.intensity = impf.intensity[1:]
    impf.paa = impf.paa[1:]
    impf.mdd = impf.mdd[1:]
    return drop_impf_leading_zeroes(impf)


def get_unu_impf_set(country, hazard_name, exposure_name = None):
    impf = get_unu_impf(country, hazard_name, exposure_name)
    return ImpactFuncSet([impf])


def _get_unu_adaptation_measure_scaling(sector, exposure_name):
    entity, category_id = get_unu_entity(country, hazard_name='flood', exposure_name=exposure_name)
    measures = entity.measure_set
    return np.array([m.mdd_impact[0] for m in measures]).unique()