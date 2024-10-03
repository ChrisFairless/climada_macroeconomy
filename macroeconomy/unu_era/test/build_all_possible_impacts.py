import sys
sys.path.append('../../..')
import logging
from macroeconomy.unu_era.base import HAZARD_TYPES, EXPOSURE_IMPACT_TYPES, CLIMATE_SCENARIOS, get_impact_yearset


# Not a unittest: this takes too long
# Run from the command line if you want to check all the impacts defined in base.py are reachable

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
LOGGER.addHandler(handler)


N_SIM_YEARS = 10
DEFAULTS = {
    'climate_scenario': 'historical',
    'exposure_type': 'tourism',
    'impact_type': 'labour production'
}

def build_all_exposure_impacts():
    LOGGER.info(f'\nTEST: TESTING ALL EXPOSURE-IMPACT COMBINATIONS FOR CLIMATE SCENARIO {DEFAULTS["climate_scenario"]}\n')

    if len(HAZARD_TYPES) > 1:
        LOGGER.warning('Not ready to deal with non-flood hazards. This will fail')

    for country, country_impacts in EXPOSURE_IMPACT_TYPES.items():
        LOGGER.info(f'\nWorking on {country}\n')
        n_impacts = len(country_impacts)
        for i, (exposure_type, impact_type) in enumerate(country_impacts):
            LOGGER.info(f'{i}/{n_impacts}: {exposure_type}: {impact_type}')
            _ = get_impact_yearset(
                hazard_type='flood',
                exposure_type=exposure_type,
                impact_type=impact_type,
                country=country,
                climate_scenario=DEFAULTS['climate_scenario'],
                n_sim_years=N_SIM_YEARS,
                normalise=True
            )



def build_all_scenarios():
    LOGGER.info(f'\nTEST: TESTING ALL SCENARIOS FOR IMPACT {DEFAULTS["exposure_type"]}: {DEFAULTS["impact_type"]}\n')

    if len(HAZARD_TYPES) > 1:
        LOGGER.warning('Not ready to deal with non-flood hazards. This will fail')

    n_scenarios = len(CLIMATE_SCENARIOS)
    for country, country_impacts in EXPOSURE_IMPACT_TYPES.items():
        LOGGER.info(f'\nWorking on {country}\n')
        for i, climate_scenario in enumerate(CLIMATE_SCENARIOS):
            LOGGER.info(f'{i}/{n_scenarios}: {climate_scenario}')
            _ = get_impact_yearset(
                hazard_type='flood', 
                exposure_type=DEFAULTS['exposure_type'],
                impact_type=DEFAULTS['impact_type'],
                country=country,
                climate_scenario=climate_scenario,
                n_sim_years=N_SIM_YEARS,
                normalise=True
                )


if __name__ == "__main__":
    build_all_exposure_impacts()
    build_all_scenarios()