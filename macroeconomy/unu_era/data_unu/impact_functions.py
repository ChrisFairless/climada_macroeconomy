import numpy as np
from climada.entity import ImpactFunc, ImpactFuncSet

# Most impact functions are read from Entity files and read through the get_unu_impf method in entity.py
# But a few are stored here too

def get_unu_heatwave_impfset_agriculture_labour(country):
    if country == 'egypt':
        crops = linear_impf(m=0.05 / 365, haz_type='HW', id=501)
        livestock = linear_impf(m=0.05 / 365, haz_type='HW', id=502)
        return ImpactFuncSet([crops, livestock])
    if country == 'thailand':
        trees = linear_impf(m=0.05 / 365, haz_type='HW', id=201)
        grass = linear_impf(m=0.05 / 365, haz_type='HW', id=202)
        return ImpactFuncSet([trees, grass])
    raise ValueError(f'Unexpected country: {country}')

def get_unu_heatwave_impfset_manufacturing_labour():
    return linear_impf_set(m=0.02 / 365, haz_type='HW', id=1)

def get_unu_heatwave_impfset_tourism_labour():
    return linear_impf_set(m=0.02 / 365, haz_type='HW', id=1)

def get_unu_heatwave_impfset_energy_labour():
    return linear_impf_set(m=0.02 / 365, haz_type='HW', id=1)

def get_unu_heatwave_impfset_services_labour():
    return linear_impf_set(m=0.02 / 365, haz_type='HW', id=1)

def linear_impf(m, haz_type='', id=1, **kwargs):
    return ImpactFunc(
        haz_type=haz_type,
        id=id,
        intensity=np.array([0,1000]),
        mdd=np.array([0, 1000*m]),
        paa=np.array([1,1]),
        **kwargs
    )

def linear_impf_set(m, haz_type='', id=1, **kwargs):
    return ImpactFuncSet([linear_impf(m, haz_type, id, **kwargs)])