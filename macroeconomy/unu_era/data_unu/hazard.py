from pathlib import Path
import numpy as np
import logging
from scipy.sparse import csr_matrix
from climada.hazard import Hazard, Centroids
import climada.util.hdf5_handler as u_hdf5

DATA_DIR = {
    'thailand': '/Users/chrisfairless/Projects/UNU/data/Thailand/hazard/',
    'egypt': '/Users/chrisfairless/Projects/UNU/data/Egypt/hazard'
}

DEF_VAR_MAT = {'field_name': 'hazard',
               'var_name': {'per_id': 'peril_ID',
                            'even_id': 'event_ID',
                            'ev_name': 'name',
                            'freq': 'frequency',
                            'inten': 'intensity',
                            'unit': 'units',
                            'frac': 'fraction',
                            'comment': 'comment',
                            'datenum': 'datenum',
                            'orig': 'orig_event_flag'
                            },
               'var_cent': {'field_names': ['centroids', 'hazard'],
                            'var_name': {'cen_id': 'centroid_ID',
                                         'lat': 'lat',
                                         'lon': 'lon'
                                         }
                            }
               }
"""MATLAB variable names"""

LOGGER = logging.getLogger(__name__)

def get_unu_flood_hazard(country, scenario):
    return_periods = [2, 5, 10, 25]
    scenario_string = 'today' if scenario == 'historical' else scenario
    filename = f'fl_{country}_{scenario_string}.tif'
    haz_path = Path(DATA_DIR[country], 'flood', filename)
    haz = Hazard.from_raster(haz_path, band=[1,2,3,4], haz_type='FL')
    haz.frequency = np.array([1/rp for rp in return_periods])
    return haz


def get_unu_heatwave_hazard(country, scenario):
    return_periods = [2, 5, 10, 25]
    if country == 'egypt':
        if scenario == 'historical':
            filename = 'hazard_today_Egypt_HW.mat'
        elif scenario == 'rcp26':
            filename = 'Hazard_EGY_RCP45_HW_new.mat'
        elif scenario == 'rcp85':
            filename = 'Hazard_EGY_RCP85_HW_new.mat'

    else:
        raise ValueError(f'Not yet implemented for country {country}')
    haz_path = Path(DATA_DIR[country], 'heatwave', filename)
    haz = climada_haz_from_mat(haz_path)

    # The Egypt heatwave hazard seems to have got ordered wrong? This should fix it
    if country == 'egypt':
        haz = flip_hazard(haz)
        haz = drop_coastal_grid_points(haz)
    
    return haz    


def flip_hazard(haz: Hazard):
    m = haz.intensity.todense()
    n_lat = len(np.unique(haz.centroids.lat))
    n_lon = len(np.unique(haz.centroids.lon))

    for i in range(m.shape[0]):
        vals = m[i]
        vals = vals.reshape((n_lat, n_lon), order='C')
        vals = np.ravel(vals, order='F')
        m[i] = vals
    haz.intensity = csr_matrix(m)
    return haz


# For heatwaves we want to drop any point that maps to a centroid over the ocean.
# From trial and error this means grid cells up to 10km inland
# Note this will remove the region_ids. We don't use them anywhere else though
def drop_coastal_grid_points(haz, threshold = -10000):
    if not hasattr(haz.centroids, 'get_dist_coast'):
        raise ValueError('I think you are using an old version of CLIMADA. Rewrite this method using `set_dist_coast`')
    dist_coast = haz.centroids.get_dist_coast(signed=True)
    if hasattr(haz.centroids, 'gdf'):  # Newer CLIMADA
        haz.centroids.gdf['region_id'] = dist_coast <= threshold
    else:   # Older CLIMADA
        haz.centroids.region_id = dist_coast <= threshold
    haz = haz.select(reg_id = 1)
    return haz



# This method was retired in CLIMADA but we need it
# Copied from CLIMADA v4.0.0 with small adjustments
def climada_haz_from_mat(file_name, var_names=None):
    """Read climada hazard generate with the MATLAB code in .mat format.

    Parameters
    ----------
    file_name : str
        absolute file name
    var_names : dict, optional
        name of the variables in the file,
        default: DEF_VAR_MAT constant

    Returns
    -------
    haz : climada.hazard.Hazard
        Hazard object from the provided MATLAB file

    Raises
    ------
    KeyError
    """
    # pylint: disable=protected-access
    if not var_names:
        var_names = DEF_VAR_MAT
    LOGGER.info('Reading %s', file_name)
    try:
        data = u_hdf5.read(file_name)
        try:
            data = data[var_names['field_name']]
        except KeyError:
            pass

        centroids = climada_centroids_from_mat(file_name, var_names=var_names['var_cent'])
        attrs = Hazard._read_att_mat(data, file_name, var_names, centroids)
        haz = Hazard(haz_type=u_hdf5.get_string(data[var_names['var_name']['per_id']]),
                    centroids=centroids,
                    **attrs
                    )
    except KeyError as var_err:
        raise KeyError("Variable not in MAT file: " + str(var_err)) from var_err
    return haz


# This method was retired in CLIMADA but we need it
# Copied from CLIMADA v4.0.0 with small adjustments
def climada_centroids_from_mat(file_name, var_names=None):
    """Read centroids from CLIMADA's MATLAB version.

    Parameters
    ----------
    file_name : str
        absolute or relative file name
    var_names : dict, optional
        name of the variables

    Raises
    ------
    KeyError

    Returns
    -------
    centr : Centroids
        Centroids with data from the given file
    """
    LOGGER.info('Reading %s', file_name)
    if var_names is None:
        var_names = DEF_VAR_MAT

    cent = u_hdf5.read(file_name)
    # Try open encapsulating variable FIELD_NAMES
    num_try = 0
    for field in var_names['field_names']:
        try:
            cent = cent[field]
            break
        except KeyError:
            num_try += 1
    if num_try == len(var_names['field_names']):
        LOGGER.warning("Variables are not under: %s.", var_names['field_names'])

    try:
        cen_lat = np.squeeze(cent[var_names['var_name']['lat']])
        cen_lon = np.squeeze(cent[var_names['var_name']['lon']])
        centr = Centroids.from_lat_lon(cen_lat, cen_lon)

        try:
            centr.dist_coast = np.squeeze(cent[var_names['var_name']['dist_coast']])
        except KeyError:
            pass
        try:
            centr.region_id = np.squeeze(cent[var_names['var_name']['region_id']])
        except KeyError:
            pass
    except KeyError as err:
        raise KeyError("Not existing variable: %s" % str(err)) from err

    return centr