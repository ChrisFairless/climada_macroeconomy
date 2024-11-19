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
        self.scenarios = scenarios

        if not os.path.exists(output_excel_path):
            raise FileNotFoundError(f'Output Excel file not found at {self.user_output_excel}')

        with pd.ExcelFile(output_excel_path) as xl:
            self.data = {scenario: pd.read_excel(xl, sheet_name=scenario) for scenario in self.scenarios}
            try:                
                self.data['Baseline'] = pd.read_excel(xl, sheet_name='Baseline')
                self.scenarios_with_baseline = list(set(scenarios).union({'Baseline'}))
            except ValueError as e:
                self.scenarios_with_baseline = self.scenarios

        self.n_sim_years = self.data[self.scenarios_with_baseline[0]].shape[0]
        self.input = CREDInput(input_excel_path, scenarios=scenarios)
        self.input.truncate_to_n_years(self.n_sim_years)
        self.sectors = self.input.sectors
        self.n_sectors = self.input.n_sectors
        # Human readable names for output variables
        self.output_var_lookup = self.get_output_var_lookup(self.sectors)


    def plot(self, varlist=None, add_sector_shocks=True):
        if not varlist:
            varlist = self.output_var_lookup.keys()
            
        if isinstance(varlist, str):
            varlist=[varlist]

        if len(self.scenarios) == 0 and add_sector_shocks:
            raise ValueError("A model run with no non-baseline scenarios has no input shocks to plot")

        if len(varlist) == 1:
            plot_rows = 1
            plot_cols = 1
        else:
            plot_rows = int(np.ceil(len(varlist)/2))
            plot_cols = 2

        fig, axs = plt.subplots(plot_rows, plot_cols, figsize=(10, 2.5 * plot_rows), sharex=True)

        for i, var in enumerate(varlist):
            i_row = int(np.floor(i/2))
            i_col = np.mod(i, 2)

            if var in self.output_var_lookup.keys():
                plotvar, labelvar = self.output_var_lookup[var], var
            else:
                plotvar, labelvar = var, var
                        
            all_vars = self.data['Baseline'].columns
            if plotvar not in all_vars:
                raise ValueError(f"Can't plot {plotvar}: variable must be one of {list(self.output_var_lookup.keys())} or a native CRED output variable: {all_vars}")
            
            years = self.data['Baseline']['Year']

            if add_sector_shocks:
                try:
                    plotvar_num = plotvar.split('_')[-1]
                    i_sector = int(plotvar_num)
                    input_shock_var = f'exo_D_{i_sector}_1'
                except ValueError:
                    input_shock_var = None
                if plotvar == 'H':
                    input_shock_var = f'exo_DH'
                if input_shock_var:
                    shock_data = [self.input.data[s][input_shock_var] for s in self.scenarios]
                    if len(shock_data) > 1:
                        if not np.all([np.allclose(shock_data[0], shock_data[i]) for i in range(1, len(shock_data))]):
                            raise ValueError('Unplottable: different input scenarios have different shocks')
                    axtwin = axs[i_row, i_col].twinx()
                    axtwin.bar(years, shock_data[0], color='black', alpha=0.2, width=0.4, linewidth=0)

            for scenario in self.scenarios_with_baseline:
                plotdata = self.data[scenario].iloc[0:self.n_sim_years].set_index('Year')[plotvar]
                axs[i_row, i_col].plot(plotdata.index, plotdata, label=scenario)
            
            axs[i_row, i_col].set_title(labelvar)

        fig.suptitle('CRED output')
        plt.xlabel('Year')
        plt.legend()
        return plt


    def plot_relative_to_baseline(self, varlist=None, add_sector_shocks=True, absolute=True):
        if not varlist:
            varlist = self.output_var_lookup.keys()
            
        if isinstance(varlist, str):
            varlist=[varlist]

        if len(self.scenarios) == 0 and add_sector_shocks:
            raise ValueError("A model run with no non-baseline scenarios has no input shocks to plot")

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

            if var in self.output_var_lookup.keys():
                plotvar, labelvar = self.output_var_lookup[var], var
            else:
                plotvar, labelvar = var, var
            
            all_vars = self.data['Baseline'].columns
            if plotvar not in all_vars:
                raise ValueError(f"Can't plot {plotvar}: variable must be one of {list(self.output_var_lookup.keys())} or a native CRED variable:\n{all_vars}")
            years = self.data['Baseline']['Year']

            if add_sector_shocks:
                try:
                    plotvar_num = plotvar.split('_')[-1]
                    i_sector = int(plotvar_num)
                    input_shock_var = f'exo_D_{i_sector}_1'
                except ValueError:
                    input_shock_var = None
                if plotvar == 'H':
                    input_shock_var = f'exo_DH'
                if input_shock_var:
                    shock_data = [self.input.data[s][input_shock_var] for s in self.scenarios]
                    if len(shock_data) > 1:
                        if not np.all([np.allclose(shock_data[0], shock_data[i]) for i in range(1, len(shock_data))]):
                            raise ValueError('Unplottable: different input scenarios have different shocks')
                    axtwin = axs[i_row, i_col].twinx()
                    axtwin.bar(years, shock_data[0], color='black', alpha=0.2, width=0.4, linewidth=0)

            for scenario in self.scenarios:
                plotdata_scenario = self.data[scenario].iloc[0:self.n_sim_years].set_index('Year')[plotvar]
                plotdata_baseline = self.data['Baseline'].iloc[0:self.n_sim_years, ].set_index('Year')[plotvar]
                plotdata = plotdata_scenario - plotdata_baseline
                if not absolute:
                    plotdata = plotdata / plotdata_baseline
                # plotdata = plotdata.set_axis(self.data[scenario][0:self.n_sim_years, ]['Year']) 
                axs[i_row, i_col].plot(plotdata.index, plotdata, label=scenario)
            
            axs[i_row, i_col].hlines(y=0, xmin=plotdata.index.min(), xmax=plotdata.index.max(), linewidth=1, color='black')
            axs[i_row, i_col].set_title(labelvar)

        fig.suptitle('CRED output relative to baseline')
        plt.xlabel('Year')
        plt.legend()
        return plt


    @staticmethod
    def get_output_var_lookup(sectors):
        varlookup_misc = {
            'GDP': 'Y',
            'Houses': 'H',
            'Consumption': 'C',
            'Population': 'PoP',
            'Government Debt': 'BG'
        }
        varlookup_gdp = {f'{sector} GDP': f'Y_{i+1}' for i, sector in enumerate(sectors)}
        varlookup_employment = {f'{sector} Employment': f'N_{i+1}' for i, sector in enumerate(sectors)}
        varlookup_capital = {f'{sector} Capital': f'K_{i+1}' for i, sector in enumerate(sectors)}
        varlookup_domestic_price_index = {f'{sector} Domestic Price Index': f'P_D_{i+1}' for i, sector in enumerate(sectors)}
        varlookup_wage_index = {f'{sector} Wage Index': f'K_{i+1}' for i, sector in enumerate(sectors)}
        varlookup_output = {f'{sector} Domestically Used Output': f'Q_D_{i+1}' for i, sector in enumerate(sectors)}


        return varlookup_misc | varlookup_gdp | varlookup_employment | varlookup_capital | varlookup_domestic_price_index | varlookup_wage_index | varlookup_output