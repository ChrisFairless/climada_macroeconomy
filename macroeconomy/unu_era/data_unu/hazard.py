from pathlib import Path
import numpy as np
from climada.hazard import Hazard

DATA_DIR = {
    'thailand': '/Users/chrisfairless/Projects/UNU/data/Thailand/hazard',
    'egypt': '/Users/chrisfairless/Projects/UNU/data/Egypt/hazard'
}


def get_unu_flood_hazard(country, scenario):
    return_periods = [2, 5, 10, 25]
    scenario_string = 'today' if scenario == 'historical' else scenario
    filename = f'fl_{country}_{scenario_string}.tif'
    haz_path = Path(DATA_DIR[country], filename)
    haz = Hazard.from_raster(haz_path, band=[1,2,3,4], haz_type='RF')
    haz.frequency = np.array([1/rp for rp in return_periods])
    return haz
    
