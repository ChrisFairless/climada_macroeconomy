import pandas as pd
import numpy as np
import logging
import shutil
import os
import matplotlib.pyplot as plt
from typing import Union, List, Dict
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# TODO / WARNING: Currently this module is designed to work with the out-of-the-box setup for the UNU-specific installation 
# of CRED with 5 sectors, 1 region and fixed exogenous parameters. This will need to be adapted in the future!

class CREDInput:
    def __init__(
        self,
        input_excel_path,
        scenarios=["Scenario"],
        # n_sim_years=None,
        set_impacts_to_zero = False
    ):
        self.input_excel_path = input_excel_path
        if 'Baseline' in scenarios:
            LOGGER.warning("Don't provide 'Baseline' as an input scenario here: it doesn't have exogenous impacts. I'll remove that from the input scenarios for you")
            scenarios = list(set(scenarios).difference({'Baseline'}))
        self.scenarios = scenarios
        self.scenarios_with_baseline = ['Baseline'] + scenarios
        
        with pd.ExcelFile(input_excel_path) as xl:
            self.data = {scenario: pd.read_excel(xl, sheet_name=scenario) for scenario in self.scenarios}
            self.baseline = pd.read_excel(xl, sheet_name='Baseline')

        self.sectors = self.read_sectors_from_cred_input(self.input_excel_path)
        self.n_sectors = len(self.sectors)
        self.vars = self.map_variable_names()

        n_sim_years_list = np.unique([df.shape[0] for df in self.data.values()] + [self.baseline.shape[0]])
        self.n_sim_years = np.min(n_sim_years_list)
        self.input_var_lookup = self.get_input_var_lookup(self.sectors)

        if len(n_sim_years_list) > 1:
            LOGGER.warning(f'Unexpected: different scenarios have different numbers of years. Truncating to {self.n_sim_years} years')
            self.truncate_to_n_years(self.n_sim_years)
        
        if set_impacts_to_zero:
            self.set_impacts_to_zero()

    def truncate_to_n_years(self, n):
        for key, df_scenario in self.data.items():
            self.data[key] = df_scenario.iloc[0:n, ]
        self.baseline = self.baseline.iloc[0:n, ]

    def set_impacts_to_zero(self):
        # Set climate vars and adaptation vars to zero:
        # - Climate change parameters aren't used since we provide shocks directly
        # - Exogenous damages are set later
        for df_scenario in self.data.values():
            df_scenario['exo_tas_1'] = 0            # Global temperature
            df_scenario['exo_floods_1'] = 0         # Frequency of floods
            df_scenario['exo_droughts_1'] = 0       # Frequency of droughts
            df_scenario['exo_DH'] = 0               # Damage to housing stock
            df_scenario['exo_I_A_DH'] = 0           # No idea, undocumented
            df_scenario['exo_I_AP_DH'] = 0          # No idea, undocumented
            for i in range(1, self.n_sectors + 1):
                df_scenario[f'exo_GA_{i}_1'] = 0        # Adaptation expenditure against landslide (??)
                df_scenario[f'exo_IAP_{i}_1'] = 0       # No idea, undocumented
                df_scenario[f'exo_D_{i}_1'] = 0         # Sectoral damage
                df_scenario[f'exo_D_N_{i}_1'] = 0       # Labour productivity damage
                df_scenario[f'exo_D_K_{i}_1'] = 0       # Capital productivity damage


    def map_variable_names(self):
        vars = {}
        vars['exo_DH'] = 'Damage to housing stock'
        for i, sector in enumerate(self.sectors):
            vars[f'exo_D_{i+1}_1'] = f'{sector.capitalize()} damage'
            vars[f'exo_D_N_{i+1}_1'] = f'{sector.capitalize()} labour productivity'
            vars[f'exo_D_K_{i+1}_1'] = f'{sector.capitalize()} capital productivty'
        return vars


    def set_sector_annual_impacts(self, scenario, sector, impact_type, annual_impacts):
        col_name = self.get_sector_impact_column_name(sector, impact_type)
        self.set_scenario_input_columns(scenario, col_name, annual_impacts, unit_interval=True)


    def set_housing_annual_impacts(self, scenario, annual_impacts):
        col_name = 'exo_DH'
        self.set_scenario_input_columns(scenario, col_name, annual_impacts, unit_interval=True)


    def set_scenario_input_columns(self, scenario, colname, values, unit_interval=False):
        values = np.array(values)
        if values.size < self.n_sim_years:
            raise ValueError(f'The provided values have fewer years ({values.size}) than the input excel ({self.n_sim_years}). Either provide more years or delete rows from the input Excel file')
        if values.size > self.n_sim_years:
            LOGGER.info(f'The provided annual_impacts have more years ({values.size}) than the input simulation excel ({self.n_sim_years}). It will be truncated to match')
        if unit_interval:
            if values.max() > 1 or values.min() < 0:
                raise ValueError(f'The provided values must be in the range 0 - 1. Range: {values.min()} to {values.max()}')
        if scenario not in self.data:
            raise ValueError(f'Scenario "{scenario}" is not in the input data')
        if colname not in self.data[scenario]:
            raise ValueError(f'Variable {colname} is not in the input data for scenario {scenario}')
        self.data[scenario][colname] = values[0:self.n_sim_years]


    def get_sector_impact_column_name(self, sector, impact_type):
        if isinstance(sector, int):
            i_sector = sector 
        else:
            lowercase_sectors = np.array([s.lower() for s in self.sectors])
            if not sector.lower() in lowercase_sectors:
                raise ValueError(f'Could not match (lower case) sectors from input to spreadsheet names: input {sector.lower()}, spreadsheet names {lowercase_sectors}')
            i_sector = np.argwhere(lowercase_sectors == sector.lower())[0][0] + 1
                    
        if impact_type == 'asset loss':
            return f'exo_D_{i_sector}_1'
        if impact_type == 'labour productivity':
            return f'exo_D_N_{i_sector}_1'
        if impact_type == 'capital productivity':
            return f'exo_D_K_{i_sector}_1'
        raise ValueError(f'Unrecognised impact_type: {impact_type}')


    def to_excel(self, path, overwrite=False):
        if not overwrite and os.path.exists(path):
            raise FileExistsError(f'Output file already exists at {path}')

        shutil.copy2(self.input_excel_path, path)
        with pd.ExcelWriter(path, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
            for sheet, df in self.data.items():
                df.to_excel(writer, sheet, index=False)
            self.baseline.to_excel(writer, 'Baseline', index=False)


    def add_scenario(self):
        raise NotImplementedError()


    def set_dummy_impacts(self, scale=1, frequency=0.2, scale_imp_to_bi=0.25, seed=None):
        if seed:
            np.random.seed(seed)
        self.set_impacts_to_zero()
        years_with_events = [roll < frequency for roll in np.random.random(size=self.n_sim_years)]
        for scenario in self.scenarios:
            impacts = np.random.random(size=self.n_sim_years) * scale
            impacts = np.array([imp if event else 0 for imp, event in zip(impacts, years_with_events)])
            self.set_housing_annual_impacts(scenario, impacts)
            for i in range(1, self.n_sectors+1):
                impacts = np.random.random(size=self.n_sim_years) * scale
                impacts = np.array([imp if event else 0 for imp, event in zip(impacts, years_with_events)])
                self.set_sector_annual_impacts(scenario, i, "asset loss", impacts)
                self.set_sector_annual_impacts(scenario, i, "labour productivity", impacts * scale_imp_to_bi)
                self.set_sector_annual_impacts(scenario, i, "capital productivity", impacts * scale_imp_to_bi)


    def plot(self, varlist=None, plot_scenario=None):
        if not plot_scenario:
            if len(self.scenarios) == 1:
                plot_scenario = self.scenarios[0]
            else:
                raise ValueError('Please specify a scenario to plot')

        if not varlist:
            varlist = self.input_var_lookup.keys()

        if isinstance(varlist, str):
            varlist=[varlist]

        if len(varlist) == 1:
            plot_rows = 1
            plot_cols = 1
        else:
            plot_rows = int(np.ceil(len(varlist)/2))
            plot_cols = 2

        fig, axs = plt.subplots(plot_rows, plot_cols, figsize=(10, 2.5 * plot_rows), sharex=True)
        all_vars = self.data[plot_scenario].columns
        years = self.data[plot_scenario]['Time']

        for i, var in enumerate(varlist):
            i_row = int(np.floor(i/2))
            i_col = np.mod(i, 2)

            if var in self.input_var_lookup.keys():
                plotvar, labelvar = self.input_var_lookup[var], var
            else:
                plotvar, labelvar = var, var
            
            if plotvar not in all_vars:
                raise ValueError(f"Can't plot {plotvar}: variable must be one of {list(self.output_var_lookup.keys())} or a native CRED variable:\n{all_vars}")

            plotdata = self.data[plot_scenario].iloc[0:self.n_sim_years].set_index('Time')[plotvar]    
            if plotvar == 'exo_PoP':
                axs[i_row, i_col].plot(plotdata.index, plotdata)
            else:
                axs[i_row, i_col].bar(plotdata.index, plotdata)
            axs[i_row, i_col].set_title(labelvar)


    @staticmethod
    def get_input_var_lookup(sectors):
        varlookup_1 = {
            'Population': 'exo_PoP',
            'Damage to houses': 'exo_DH',
        }
        varlookup_2 = {f'{sector} damages': f'exo_D_{i+1}_1' for i, sector in enumerate(sectors)}
        varlookup_3 = {f'{sector} capital productivity': f'exo_D_K_{i+1}_1' for i, sector in enumerate(sectors)}
        varlookup_4 = {f'{sector} labour productivity': f'exo_D_N_{i+1}_1' for i, sector in enumerate(sectors)}
        return varlookup_1 | varlookup_2 | varlookup_3 | varlookup_4

    @staticmethod
    def read_sectors_from_cred_input(path):
        df = pd.read_excel(path, sheet_name='Content')
        i_row_sectors = np.argwhere(df['Sheets'] == 'Sectors')[0][0] + 1
        sectors = df.iloc[i_row_sectors:, 1]
        return sectors
