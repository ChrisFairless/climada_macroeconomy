import logging
import sys
import os
from copy import deepcopy
import numpy as np
from typing import Union
from pathlib import Path
from functools import reduce
from climada.engine import Impact
from nccs.pipeline.direct.calc_yearset import combine_yearsets, cap_impact

from macroeconomy.unu_era import base
from macroeconomy.cred_input import CREDInput
from macroeconomy.unu_era.base import HAZARD_TYPES, HAZ_EXPOSURE_IMPACTS

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

CRED_TEMPLATE = {
    # TODO make relative to project root
    'thailand': '/Users/chrisfairless/Projects/UNU/data/Thailand/ModelSimulationandCalibration5Sectorsand1Regions.xlsx',
    'egypt': '/Users/chrisfairless/Projects/UNU/data/Egypt/ModelSimulationandCalibration4Sectorsand1Regions.xlsx'
}

# We don't use this any more

# CRED_EXPOSURE_IMPACT_TYPES = {
#     'thailand': [
#         ('housing', 'asset loss'),
#         ('agriculture', 'asset loss'),
#         ('agriculture', 'labour productivity'),
#         ('agriculture', 'capital productivity'),
#         ('services', 'asset loss'),
#         ('services', 'labour productivity'),
#         ('services', 'capital productivity'),
#         ('tourism', 'asset loss'),
#         ('tourism', 'labour productivity'),
#         ('tourism', 'capital productivity'),
#         ('energy', 'asset loss'),
#         ('energy', 'labour productivity'),
#         ('energy', 'capital productivity'),
#         ('manufacturing', 'asset loss'),
#         ('manufacturing', 'labour productivity'),
#         ('manufacturing', 'capital productivity')
#     ],
#     'egypt': [
#         ('housing', 'asset loss'),
#         ('agriculture', 'asset loss'),
#         ('agriculture', 'labour productivity'),
#         ('agriculture', 'capital productivity'),
#         # ('services', 'asset loss'),
#         # ('services', 'labour productivity'),
#         # ('services', 'capital productivity'),
#         ('tourism', 'asset loss'),
#         ('tourism', 'labour productivity'),
#         ('tourism', 'capital productivity'),
#         ('energy', 'asset loss'),
#         ('energy', 'labour productivity'),
#         ('energy', 'capital productivity'),
#         ('manufacturing', 'asset loss'),
#         ('manufacturing', 'labour productivity'),
#         ('manufacturing', 'capital productivity')        
#     ]
# }


# TODO refactor: one method to create impacts, one to load
def get_cred_impacts(
    country: str,
    climate_scenario: str,
    impacts_directory: Union[str, Path] = None,
    haz_type_list: list = HAZARD_TYPES,
    write_files: bool=True
    ):
    haz_exposure_impact_types = HAZ_EXPOSURE_IMPACTS[country]
    impacts = {}

    if isinstance(haz_type_list, str):
        LOGGER.warning('haz_type_list should be a list. Converting')
        haz_type_list = [haz_type_list]


    for haz_type in haz_type_list:
        for exposure_type, impact_type in haz_exposure_impact_types[haz_type]:
            if exposure_type not in impacts:
                impacts[exposure_type] = {impact_type: {}}
            if impact_type not in impacts[exposure_type].keys():
                impacts[exposure_type][impact_type] = {}

            if impacts_directory:
                if not os.path.exists(impacts_directory):
                    os.makedirs(impacts_directory, exist_ok=True)
            
            if haz_type in str(impacts_directory):
                raise ValueError(f'I think the impacts directory was specified wrong. It should be a location with subfolders for each hazard. The hazard {haz_type} is already in the provided path: {impacts_directory}')

            if impacts_directory:
                haz_impacts_directory = Path(impacts_directory, haz_type)
                if not os.path.exists(impacts_directory):
                    os.makedirs(impacts_directory, exist_ok=True)
                imp_filepath = Path(haz_impacts_directory, f'{exposure_type}_{impact_type}_{climate_scenario}.hdf5'.replace(' ', '_'))
        
            if impacts_directory and os.path.exists(imp_filepath):
                LOGGER.info(f'Reading existing impact for {haz_type} - {climate_scenario} - {exposure_type} - {impact_type}')
                impacts[exposure_type][impact_type][haz_type] = Impact.from_hdf5(imp_filepath)
            else:
                LOGGER.info(f'Generating impacts for {haz_type} - {climate_scenario} - {exposure_type} - {impact_type}')
                imp = base.get_impact(
                    hazard_type=haz_type,
                    exposure_type=exposure_type,
                    impact_type=impact_type,
                    country=country,
                    climate_scenario=climate_scenario,
                    normalise=True
                )
                impacts[exposure_type][impact_type][haz_type] = imp
                if impacts_directory and write_files:
                    imp.write_hdf5(imp_filepath)
    
    return impacts




# TODO refactor: don't create missing impacts
def generate_cred_input(country, climate_scenario, haz_type_list, n_sim_years=None, measures=None, output_path=None, impacts_directory=None, write_files=True, seed=None):
    cred_template = CRED_TEMPLATE[country]
    scenario = 'Scenario'
    cred_input = CREDInput(cred_template, scenarios=[scenario])

    if n_sim_years:
        cred_input.truncate_to_n_years(n_sim_years)  # 2014 to 2050   # TODO make this more easily user-accessible
        cred_input.n_sim_years = n_sim_years

    validate_measures(measures, cred_input)

    impacts_historical = get_cred_impacts(country=country, climate_scenario='historical', haz_type_list=haz_type_list, impacts_directory=impacts_directory, write_files=write_files)
    if climate_scenario == 'historical':
        impacts_scenario = deepcopy(impacts_historical)
    else:
        impacts_scenario = get_cred_impacts(country=country, climate_scenario=climate_scenario, haz_type_list=haz_type_list, impacts_directory=impacts_directory, write_files=write_files)

    exposure_impact_types = HAZ_EXPOSURE_IMPACTS[country]
    exposure_impact_types = list(set(sum(list(exposure_impact_types.values()), [])))

    for (exposure_type, impact_type) in exposure_impact_types:
        # TODO replace with proper Snapshots and interpolation when CLIMADA is ready for it. For now, for exactly this use case, this is about equivalent
        imp_historical_dict = impacts_historical[exposure_type][impact_type]
        imp_scenario_dict = impacts_scenario[exposure_type][impact_type]

        imp_yearset_historical_list = [base.create_yearset(imp, cred_input.n_sim_years, seed) for imp in imp_historical_dict.values()]
        imp_yearset_scenario_list = [base.create_yearset(imp, cred_input.n_sim_years, seed) for imp in imp_scenario_dict.values()]

        imp_yearset_historical = combine_yearsets_without_imp_mat(imp_yearset_historical_list, cap_exposure=1)
        imp_yearset_scenario = combine_yearsets_without_imp_mat(imp_yearset_scenario_list, cap_exposure=1)

        # TODO start interpolation from 2024 not 2014
        annual_impacts = interpolate_between_yearsets(imp_yearset_historical, imp_yearset_scenario, seed)

        # This is where we apply measures! Since they're all scaling the impact
        if measures and len(measures) != 0:
            if exposure_type in measures:
                annual_impacts = np.multiply(annual_impacts, measures[exposure_type])

        # Cap at 100% loss
        # TODO warn when this happens...
        annual_impacts = np.array([min(x, 1) for x in annual_impacts])

        if exposure_type == 'housing':
            cred_input.set_housing_annual_impacts(
                scenario=scenario,
                annual_impacts=annual_impacts
            )
        else:
            cred_input.set_sector_annual_impacts(
                scenario=scenario,
                sector=exposure_type,
                impact_type=impact_type,
                annual_impacts=annual_impacts
            )
    if output_path:
        LOGGER.info('Writing output')
        cred_input.to_excel(output_path, overwrite=True)
    return cred_input


def combine_yearsets_without_imp_mat(impact_list, cap_exposure=None):
    imp0 = impact_list[0]
    coord_exp = np.array([np.array([0, 0])])
    freq = np.ones(len(imp0.event_id)) / len(imp0.event_id)
    eai_exp = np.array([np.sum([imp.aai_agg for imp in impact_list])])
    at_event = reduce(np.add, [imp.at_event for imp in impact_list])
    aai_agg = eai_exp

    imp_combined = Impact(
        event_id=imp0.event_id,
        event_name=imp0.event_name,
        date=imp0.date,
        frequency=freq,
        frequency_unit=imp0.frequency_unit,
        coord_exp=coord_exp,
        crs=imp0.crs,
        eai_exp=eai_exp,
        at_event=at_event,
        aai_agg=aai_agg,
        unit=imp0.unit,
        imp_mat=None,
        haz_type='COMBINED'
    )
    if cap_exposure is not None:
        imp_combined = cap_impact(imp_combined, cap_exposure)
    return imp_combined


def interpolate_between_yearsets(ys1, ys2, seed):
    annual_impacts_historical = ys1.at_event
    annual_impacts_scenario = ys2.at_event
    n_years = annual_impacts_historical.size
    if seed:
        np.random.seed(seed)
    year_rolls = np.random.uniform(size=n_years)
    annual_impacts = [
        histyear if roll > year/n_years 
        else scenarioyear 
        for year, (histyear, scenarioyear, roll) in enumerate(zip(annual_impacts_historical, annual_impacts_scenario, year_rolls))
        ]
    return annual_impacts


def validate_measures(measures, cred_input):
    if not measures:
        return None
    measure_lengths = np.unique([len(meas) for meas in measures.values()])
    if len(measure_lengths) > 1:
        raise ValueError('Provided measures have different lengths')
    if measure_lengths[0] != cred_input.n_sim_years:
        raise ValueError('Provided measures have different lengths from the data in the input')
    expected_measure_names = set([s.lower() for s in cred_input.sectors]).union({'housing'})
    measures_without_sector = set(measures.keys()).difference(expected_measure_names)
    if len(measures_without_sector) > 0:
        raise ValueError(f'Unexpected sectors in the specified measures: {measures_without_sector}')
    sectors_without_measure = expected_measure_names.difference(set(measures.keys()))
    if len(sectors_without_measure) > 0:
        LOGGER.warning(f'Not all sectors have measures: {sectors_without_measure}')
        


def generate_many_cred_inputs(country, climate_scenario, haz_type_list, n_sim_years, measures, n_inputs_to_create, output_dir, impacts_directory=None, write_files=True, overwrite_existing=False, seed=None):
    LOGGER.info(f'Sampling impacts to create possible futures')
    np.random.seed(seed)
    output_path_list = []

    for i in range(n_inputs_to_create):
        i_str = "{:03d}".format(i+1)
        output_path = Path(output_dir, f'sample_{i_str}.xlsx')
        output_path_list.append(output_path)
        if os.path.exists(output_path) and not overwrite_existing:
            LOGGER.info(f'Input file {i_str} already exists at {output_path} and overwrite_existing = False. Skipping this input.')
            continue
        LOGGER.info(f'Generating future {i_str}')
        i_seed = np.random.randint(1, 999999)
        _ = generate_cred_input(country=country, climate_scenario=climate_scenario, haz_type_list=haz_type_list, n_sim_years=n_sim_years, measures=measures, output_path=output_path, impacts_directory=impacts_directory, write_files=write_files, seed=i_seed)
    
    LOGGER.info(f'Finished creating CRED inputs')
    return output_path_list