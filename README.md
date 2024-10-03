# CLIMADA coupled to the DGE-CRED macroeconomic model

## How it works

#TODO documentation

## Installation and setup

We recommend building and using this package in a virtual environment, such as conda.

If you are likely to be messing with the insides of CLIMADA (rather than installing from a remote) you will need to use mamba. Otherwise it's your choice. If you choose mamba see the instructions at https://climada-python.readthedocs.io/en/stable/ on how to get started.

The package has three requirements files in the requirements/ folder, and you will need to install one or more of them depending on what you want usethe package for. In the future it would make sense to split this into three smaller packages, but for now it's all in one place.
- **base_macroeconomy_cred.yml:** For users who only want the functionality of the DGE-CRED model wrapped in python
- **climada_macroeconomy_cred.yml:** For users who want to couple outputs from CLIMADA to the DGE-CRED model
- **unu_calculations.yml:** For users who want to reproduce calculations run for the UNU ERA project on disaster risk in Thailand and Egypt. Note: this requires access to particular datasets that (as of Sept 2024) aren't avaiable online. For free copies for commercial or non-commercial use, contact the package maintainers and we'll let you know if we can help.


In particular, this module requires both the [core CLIMADA](https://climada-python.readthedocs.io/en/stable/)  and [CLIMADA Petals](https://climada-petals.readthedocs.io/en/stable/) to run a full disaster-forced simulation.

To install with conda/mamba on your system, clone this repository, and run

```
mamba create -n climada_macroeconomy --file=requirements/base_macroeconomy_cred.yml python=3.11
```
(note: as far as I know this will run with any python between 3.9 and 3.11, the versions currently supported by CLIMADA)

If you want to add the CLIMADA functionality, then run

```
mamba env create -n climada_macroeconomy --file=requirements/climada_macroeconomy_cred.yml
```

If you want to add the UNU analyses, then run

```
mamba env create -n climada_macroeconomy --file=requirements/unu_calculations.yml
```

