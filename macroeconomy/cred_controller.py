import os
import sys
import logging
import pandas as pd
import numpy as np
from typing import Union, List, Optional
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from climada.engine import Impact
from climada.entity import MeasureSet

from macroeconomy.cred_model import MacroEconomyCRED
from macroeconomy.cred_input import CREDInput
from macroeconomy.cred_output import CREDOutput

LOGGER = logging.getLogger(__name__)
if len(LOGGER.handlers) == 0:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)


class CREDController():
    # Class to organise and execute an ensemble of CRED simulations
    # TODO And to explore the inputs and outputs until we split these into separate classes

    def __init__(
        self,
        cred_template: MacroEconomyCRED = None,
        input_dir: Union[str, Path] = None,
        output_dir: Union[str, Path] = None,
        scenario = 'Scenario',
        seed: int = None,
        ):
        # Input folder is a location where DGE-CRED model inputs are stored, minus the ones that come from CLIMADA
        # impact_list is a list of paths/pathlikes to climada impact objects or a list of impact objects
        np.random.seed == seed
        self.cred_template = cred_template
        # self.experiment_name = experiment_name
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.scenario = scenario
        if self.input_dir == self.output_dir:
            raise ValueError('input dir must be different from output dir')
        if self.input_dir:
            self.example_input = CREDInput(Path(self.input_dir, os.listdir(self.input_dir)[0]), scenarios=[self.scenario])
            self.output_var_lookup = CREDOutput.get_output_var_lookup(self.example_input.sectors)
            self.input_var_lookup = CREDInput.get_input_var_lookup(self.example_input.sectors)
        self.processed_inputs = None
        self.processed_outputs = None


    def run_experiment(self, overwrite_existing=False):
        if not self.cred_template:
            raise ValueError('A cred_template must be provided when the CREDController is created if you wish to run the experiment')
        if not self.input_dir:
            raise ValueError('An input_dir must be provided when the CREDController is created if you wish to run the experiment')
        if not self.output_dir:
            raise ValueError('An output_dir must be provided when the CREDController is created if you wish to run the experiment')

        input_file_list = os.listdir(self.input_dir)
        output_file_list = [Path(self.output_dir, f) for f in input_file_list]
        n_runs = len(input_file_list)

        LOGGER.info('Running baseline')
        input_excel = Path(self.input_dir, input_file_list[0])
        output_excel = Path(self.output_dir, 'baseline.xlsx')
        # We'll alway run the baseline because we need to regenerate it if the previous CRED run wasn't with the same setup
        # TODO find out how to test for this
        cred = self.cred_instance_from_template(input_excel, output_excel, ['Baseline'])
        cred.timeout = None
        cred.run()

        for i, f in enumerate(input_file_list):
            LOGGER.info(f'CRED model run {i} of {n_runs}')
            input_excel = Path(self.input_dir, f)
            output_excel = Path(self.output_dir, f)
            if os.path.exists(output_excel) and not overwrite_existing:
                LOGGER.info(f'...output already exists and overwrite_existing = False. Skipping.')
                continue
            cred = self.cred_instance_from_template(input_excel, output_excel, [self.scenario])
            try:
                cred.run()
            except FileNotFoundError as e:
                LOGGER.info(f'Model run {i} failed and did not produce output: {e}.')
        
        return output_file_list
    

    def cred_instance_from_template(self, input_excel, output_excel, scenarios):
        return MacroEconomyCRED(
            input_excel=input_excel,
            output_excel=output_excel,
            n_sim_years=self.cred_template.n_sim_years,
            n_sectors=self.cred_template.n_sectors,
            n_regions=self.cred_template.n_regions,
            scenarios=scenarios,
            ForwardLooking=self.cred_template.ForwardLooking,
            Subsecstart=self.cred_template.Subsecstart,
            Subsecend=self.cred_template.Subsecend,
            timeout=self.cred_template.timeout
        )


    # TODO make a class to hold lists of outputs and calculations for them
    def load_all_outputs(self):
        infiles = os.listdir(self.input_dir)
        infiles = [Path(self.input_dir, f) for f in infiles]
        outfiles = os.listdir(self.output_dir)
        outfiles = [Path(self.output_dir, f) for f in outfiles if f!= 'baseline.xlsx']
        baseline = CREDOutput(infiles[0], Path(self.output_dir, 'baseline.xlsx'), ['Baseline'])
        return baseline, [CREDOutput(inf, outf, [self.scenario]) for inf, outf in zip(infiles, outfiles)]


    def process_outputs(self):
        baseline, output_list = self.load_all_outputs()        
        out = {}
        for i, (labelvar, plotvar) in enumerate(self.output_var_lookup.items()):
            df = pd.DataFrame()
            for output in output_list:
                name = Path(output.output_excel_path).name
                df[name] = output.data[self.scenario][plotvar]
            df['mean'] = df.mean(axis=1)
            name = Path(baseline.output_excel_path).name
            df['Baseline'] = baseline.data['Baseline'][plotvar]
            df['Year'] = baseline.data['Baseline']['Year']
            df.set_index('Year', inplace=True)
            out[labelvar] = df
        self.processed_outputs = out
        return out
    

    def load_all_inputs(self):
        infiles = os.listdir(self.input_dir)
        infiles = [Path(self.input_dir, f) for f in infiles]
        return [CREDInput(inf, scenarios=["Scenario"], set_impacts_to_zero=False) for inf in infiles]


    def process_inputs(self):
        input_list = self.load_all_inputs()
        out = {}
        for i, (labelvar, plotvar) in enumerate(self.input_var_lookup.items()):
            df = pd.DataFrame()
            for inp in input_list:
                name = Path(inp.input_excel_path).name
                df[name] = inp.data[self.scenario][plotvar]
            df['mean'] = df.mean(axis=1)
            df['Time'] = inp.data[self.scenario]['Time']
            df.set_index('Time', inplace=True)
            out[labelvar] = df
        self.processed_inputs = out
        return out               
    

    def plot(self, varlist=None, relative_to_baseline=False, absolute=True):
        if not varlist:
            varlist = self.output_var_lookup.keys()

        if not self.processed_outputs:
            self.process_outputs()
        
        if isinstance(varlist, str):
            varlist=[varlist]

        if len(varlist) == 1:
            plot_rows = 1
            plot_cols = 1
        else:
            plot_rows = int(np.ceil(len(varlist)/2))
            plot_cols = 2

        fig, axs = plt.subplots(plot_rows, plot_cols, figsize=(10, 18), sharex=True)

        for i, (varname, plotdata) in enumerate(self.processed_outputs.items()):
            i_row = int(np.floor(i/2))
            i_col = np.mod(i, 2)

            if not relative_to_baseline:
                for col in plotdata.columns:
                    if col == 'Baseline':
                        axs[i_row, i_col].plot(plotdata.index, plotdata[col], color='black', label='Baseline')
                    elif col == 'mean':
                        axs[i_row, i_col].plot(plotdata.index, plotdata[col], color='orange', label='Mean of simulations')
                    else:
                        axs[i_row, i_col].plot(plotdata.index, plotdata[col], color='blue', alpha=0.1, label='_nolegend_')
                
                axs[i_row, i_col].set_title(varname)
                custom_lines = [Line2D([0], [0], color='black', lw=1),
                                Line2D([0], [0], color='orange', lw=1),
                                Line2D([0], [0], color='blue', alpha=0.1, lw=1)]
                axs[i_row, i_col].legend(custom_lines, ['Baseline', 'Simulation mean', 'Individual runs'])

            else:
                baseline = plotdata['Baseline']
                denominator = 1 if absolute else baseline
                axs[i_row, i_col].hlines(y=0, xmin=baseline.index.min(), xmax=baseline.index.max(), linewidth=1, color='black')
                for col in plotdata.columns:
                    if col == 'Baseline':
                        continue
                    elif col == 'mean':
                        axs[i_row, i_col].plot(plotdata.index, (plotdata[col] - baseline) / denominator, color='orange', label='Mean of simulations')
                    else:
                        axs[i_row, i_col].plot(plotdata.index, (plotdata[col] - baseline) / denominator, color='blue', alpha=0.1, label='_nolegend_')

                axs[i_row, i_col].set_title(f'{varname} relative to baseline')
                custom_lines = [Line2D([0], [0], color='orange', lw=1),
                                Line2D([0], [0], color='blue', alpha=0.1, lw=1)]
                axs[i_row, i_col].legend(custom_lines, ['Simulation mean', 'Individual runs'])

        fig.suptitle('CRED output')
        plt.xlabel('Year')
        plt.legend()
        return plt
    

    def plot_input(self, varlist=None):
        if not varlist:
            varlist = self.input_var_lookup.keys()

        if not self.processed_inputs:
            self.process_inputs()
        
        if isinstance(varlist, str):
            varlist=[varlist]

        if len(varlist) == 1:
            plot_rows = 1
            plot_cols = 1
        else:
            plot_rows = int(np.ceil(len(varlist)/2))
            plot_cols = 2

        fig, axs = plt.subplots(plot_rows, plot_cols, figsize=(10, 18), sharex=True)

        for i, (varname, plotdata) in enumerate(self.processed_inputs.items()):
            i_row = int(np.floor(i/2))
            i_col = np.mod(i, 2)

            for col in plotdata.columns:
                if col == 'mean':
                    axs[i_row, i_col].plot(plotdata.index, plotdata[col], color='red', label='Mean of simulations')
                else:
                    if varname != 'Population':
                        alpha = 1 / np.power(self.cred_template.n_sim_years, 0.5)
                        axs[i_row, i_col].bar(plotdata.index, plotdata[col], color='blue', width=1.0, alpha=alpha, label='_nolegend_')
            
            axs[i_row, i_col].set_title(varname)
            custom_lines = [Line2D([0], [0], color='red', lw=1),
                            Line2D([0], [0], color='blue', alpha=0.1, lw=1)]
            axs[i_row, i_col].legend(custom_lines, ['Input mean', 'Individual inputs'])

        fig.suptitle('CRED input')
        plt.xlabel('Time')
        plt.legend()
        return plt



    # def baseline_results_as_impacts(self, output_var_list, n_years_to_average):
    #     return self._results_as_impacts('baseline', output_var_list, n_years_to_average)
    
    # def scenario_results_as_impacts(self, output_var_list, n_years_to_average):
    #     return self._results_as_impacts('scenario', output_var_list, n_years_to_average)

    @staticmethod
    def _subset_result_years(df, begin_slice, end_slice):
        return df[np.multiply(df['Year'] >= begin_slice, df['Year'] <= end_slice)]

    def as_impact(self, output_var, n_years_to_average):
        # def results_as_impacts(self, scenario_name, output_var_list, n_years_to_average):
        # TODO CREDEnsembleResults class?
        results_list = [self.read_one_result(f'Results_run_{i}.xlsx', output_var=output_var) for i in range(self.n_simulations)]
        colname = self.output_var_lookup[output_var]
        var_hist_list = [np.mean(self._subset_result_years(result, self.start_year, self.start_year + n_years_to_average - 1)[colname]) for result in results_list]
        var_future_list = [np.mean(self._subset_result_years(result, self.end_year - n_years_to_average + 1, self.end_year)[colname]) for result in results_list]
        var_delta_list = [fut - base for base, fut in zip(var_hist_list, var_future_list)]
        event_ids = [str(i) for i in range(self.n_simulations)]
        imp = Impact(
            event_id = event_ids,
            event_name = event_ids,
            date = np.arange(self.n_simulations),
            frequency = np.full_like(event_ids, 1/self.n_simulations, dtype=float),
            at_event = var_delta_list,
            aai_agg = np.mean(var_delta_list)
            # eai_exp = np.mean(var_future_list)
            )
        return imp

            
    def read_one_result(self, filename, output_var):
        if output_var not in self.output_var_lookup.keys():
            raise ValueError(f'please request output variables contained in {self.output_var_lookup.keys()}')
        excel_colname = self.output_var_lookup[output_var]
        excel_colname = ['Year',  excel_colname]
        result = pd.read_excel(Path(self.results_dir, filename), sheet_name='Baseline')
        result = self._subset_result_years(result, self.start_year, self.end_year)
        result = result[excel_colname]
        return result
