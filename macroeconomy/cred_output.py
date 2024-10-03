import pandas as pd
import numpy as np
import logging
import shutil
import os
from typing import Union, List, Dict
from pathlib import Path
import matplotlib.pyplot as plt

from macroeconomy.cred_input import CREDInput

LOGGER = logging.getLogger(__name__)

# TODO / WARNING: Currently this module is designed to work with the out-of-the-box setup for the UNU-specific installation 
# of CRED with 5 sectors, 1 region and fixed exogenous parameters. This will need to be adapted in the future!
OUTPUT_VAR_LOOKUP = {
    'GDP': 'Y',
    'sector1 GDP': 'Y_1',
    'sector2 GDP': 'Y_2',
    'sector3 GDP': 'Y_3',
    'sector4 GDP': 'Y_4',
    'sector5 GDP': 'Y_5',
    'sector1 Employment': 'N_1',
    'sector2 Employment': 'N_2',
    'sector3 Employment': 'N_3',
    'sector4 Employment': 'N_4',
    'sector5 Employment': 'N_5',
    'Houses': 'H',
    'Population': 'PoP'
}


class CREDOutput:
    def __init__(
        self,
        input_excel_path,
        output_excel_path,
        scenarios=["Scenario"],
    ):
        self.input_excel_path = input_excel_path
        self.output_excel_path = output_excel_path

        scenarios = list(set(scenarios).difference({'Baseline'}))
        assert(len(scenarios) > 0)
        self.scenarios = scenarios
        self.scenarios_with_baseline = list(set(scenarios).union({'Baseline'}))

        if not os.path.exists(output_excel_path):
            raise FileNotFoundError(f'Output Excel file not found at {self.user_output_excel}')

        with pd.ExcelFile(output_excel_path) as xl:
            self.data = {scenario: pd.read_excel(xl, sheet_name=scenario) for scenario in self.scenarios_with_baseline}

        self.n_sim_years = self.data['Baseline'].shape[0]
        self.input = CREDInput(input_excel_path, scenarios=scenarios)
        self.input.truncate_to_n_years(self.n_sim_years)
        self.sectors = self.input.sectors
        self.n_sectors = self.input.n_sectors


    def plot(self, varlist=OUTPUT_VAR_LOOKUP.keys(), add_sector_shocks=True):
        if isinstance(varlist, str):
            varlist=[varlist]

        if len(varlist) == 1:
            plot_rows = 1
            plot_cols = 1
        else:
            plot_rows = int(np.ceil(len(varlist)/2))
            plot_cols = 2

        fig, axs = plt.subplots(plot_rows, plot_cols, figsize=(10, 18), sharex=True)

        for i, var in enumerate(varlist):
            i_row = int(np.floor(i/2))
            i_col = np.mod(i, 2)

            if var in OUTPUT_VAR_LOOKUP.keys():
                plotvar, labelvar = OUTPUT_VAR_LOOKUP[var], var
            else:
                plotvar, labelvar = var, var
            
            for i, sector in enumerate(self.input.sectors):
                pattern = f'sector{i+1}'
                labelvar = labelvar.replace(pattern, sector)
            
            all_vars = self.data['Baseline'].columns
            if plotvar not in all_vars:
                raise ValueError(f"Can't plot {plotvar}: variable must be one of {list(OUTPUT_VAR_LOOKUP.keys())} or a native CRED variable:\n{all_vars}")
            
            years = self.data['Baseline']['Year']

            if add_sector_shocks:
                print(f'plotvar: {plotvar}')           
                try:
                    plotvar_num = plotvar.split('_')[-1]
                    i_sector = int(plotvar_num)
                    input_shock_var = f'exo_D_{i_sector}_1'
                except ValueError:
                    input_shock_var = None
                if plotvar == 'H':
                    input_shock_var = f'exo_DH'
                print(f'input_shock_var: {input_shock_var}')
                if input_shock_var:
                    shock_data = [self.input.data[s][input_shock_var] for s in self.scenarios]
                    if len(shock_data) > 1:
                        if not np.all([np.allclose(shock_data[0], shock_data[i]) for i in range(1, len(shock_data))]):
                            raise ValueError('Unplottable: different input scenarios have different shocks')
                    print(shock_data[0])
                    axtwin = axs[i_row, i_col].twinx()
                    axtwin.bar(years, shock_data[0], color='lightgrey', width=0.4, linewidth=0)


            for scenario in self.scenarios_with_baseline:
                plotdata = self.data[scenario].iloc[0:self.n_sim_years].set_index('Year')[plotvar]
                axs[i_row, i_col].plot(plotdata.index, plotdata, label=scenario)
            
            axs[i_row, i_col].set_title(labelvar)

        fig.suptitle('CRED output')
        plt.xlabel('Year')
        plt.legend()
        return plt


    def plot_relative_to_baseline(self, varlist=OUTPUT_VAR_LOOKUP.keys(), absolute=True):
        if isinstance(varlist, str):
            varlist=[varlist]

        if len(varlist) == 1:
            plot_rows = 1
            plot_cols = 1
        else:
            plot_rows = int(np.ceil(len(varlist)/2))
            plot_cols = 2

        fig, axs = plt.subplots(plot_rows, plot_cols, figsize=(10, 18), sharex=True)

        for i, var in enumerate(varlist):
            i_row = int(np.floor(i/2))
            i_col = np.mod(i, 2)

            if var in OUTPUT_VAR_LOOKUP.keys():
                plotvar, labelvar = OUTPUT_VAR_LOOKUP[var], var
            else:
                plotvar, labelvar = var, var
            
            for i, sector in enumerate(self.input.sectors):
                pattern = f'sector{i+1}'
                labelvar = labelvar.replace(pattern, sector)
            
            all_vars = self.data['Baseline'].columns
            if plotvar not in all_vars:
                raise ValueError(f"Can't plot {plotvar}: variable must be one of {list(OUTPUT_VAR_LOOKUP.keys())} or a native CRED variable:\n{all_vars}")
            
            for scenario in self.scenarios:
                plotdata_scenario = self.data[scenario][0:self.n_sim_years, ][plotvar]
                plotdata_baseline = self.data['Baseline'][0:self.n_sim_years, ][plotvar]
                plotdata = plotdata_scenario - plotdata_baseline
                if not absolute:
                    plotdata = plotdata / plotdata_baseline
                plotdata = plotdata.set_axis(self.data[scenario][0:self.n_sim_years, ]['Year']) 
                axs[i_row, i_col].plot(plotdata.index, plotdata, label=scenario)
            
            axs[i_row, i_col].set_title(labelvar)

        fig.suptitle('CRED output')
        plt.xlabel('Year')
        plt.legend()
        return plt