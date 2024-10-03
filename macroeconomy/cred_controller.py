import os
import logging
import pandas as pd
from typing import Union
from pathlib import Path
from matplotlib.lines import Line2D
from macroeconomy.cred_model import MacroEconomyCRED
from macroeconomy.cred_input import CREDInput
from macroeconomy.cred_input import CREDOutput, OUTPUT_VAR_LOOKUP

LOGGER = logging.getLogger(__name__)
if len(LOGGER.handlers) == 0:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)


class CREDController():
    # Class to organise and execute an ensemble of CRED simulations

    def __init__(
        self,
        cred_template: MacroEconomyCRED,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        scenario = 'Scenario',
        # experiment_name: str,
        seed: int = None,
        ):
        # Input folder is a location where DGE-CRED model inputs are stored, minus the ones that come from CLIMADA
        # impact_list is a list of paths/pathlikes to climada impact objects or a list of impact objects
        np.random.seed == seed
        self.cred_template = cred_template
        # self.experiment_name = experiment_name
        self.input_dir = input_dir
        self.output_dir = output_dir
        if self.input_dir == self.output_dir:
            raise ValueError('input dir must be different from output dir')
        self.example_input = CREDInput(Path(self.input_dir, os.listdir(self.input_dir)[0]), scenarios=[self.scenario])


    def run_experiment(self):   # TODO make this more flexible with inputs
        input_file_list = os.listdir(self.input_dir)
        n_runs = len(input_file_list)

        print('Running baseline')
        input_excel = Path(self.input_dir, input_file_list[0])
        output_excel = Path(self.output_dir, 'baseline.xlsx')
        cred = self.cred_instance_from_template(input_excel, output_excel, ['Baseline'])
        cred.run()
        cred.remove_existing_output()   # we don't actually need the baseline file: it's in all the outputs

        for i, f in enumerate(input_file_list):
            LOGGER.info(f'CRED model run {i} of {n_runs}')
            input_excel = Path(self.input_dir, f)
            output_excel = Path(self.output_dir, f)
            cred = self.cred_instance_from_template(input_excel, output_excel, [scenario])
            cred.run()
    

    def cred_instance_from_template(input_excel, output_excel, scenarios):
        return MacroEconomyCRED(
            input_excel=input_excel,
            output_excel=output_excel,
            n_sim_years=self.cred_template.n_sim_years,
            n_sectors=self.cred_template.n_sectors,
            n_regions=self.cred_template.n_regions,
            scenarios=scenarios,
            ForwardLooking=self.cred_template.ForwardLooking,
            iStepSimulation=self.cred_template.iStepSimulation
        )


    def load_all_outputs(self):
        infiles = os.listdir(self.input_dir)
        infiles = [Path(self.input_dir, f) for f in infiles]
        outfiles = os.listdir(self.output_dir)
        outfiles = [Path(self.output_dir, f) for f in outfiles if f!= 'baseline.xlsx']
        return [CREDOutput(inf, outf, [self.scenario]) for inf, outf in zip(infiles, outfiles)]


    def process_outputs(self):
        output_list = self.load_all_outputs()        
        varlist=OUTPUT_VAR_LOOKUP.keys()
        out = {}
        for i, var in enumerate(varlist):
            labelvar = OUTPUT_VAR_LOOKUP[var]
            for i, sector in enumerate(self.example_input.sectors):
                pattern = f'sector{i+1}'
                labelvar = labelvar.replace(pattern, sector)
            df = pd.DataFrame()
            
            for output in output_list:
                name = Path(output.output_excel).name
                df[name] = output.data[self.scenario][var]
            df['mean'] = df.mean(axis=1)            
            df['Baseline'] = output_list[0].data['Baseline'][plotvar]
            out[labelvar] = df
    

    def load_all_inputs(self):
        infiles = os.listdir(self.input_dir)
        infiles = [Path(self.input_dir, f) for f in infiles]
        return [CREDInput(inf, scenarios=["Scenario"], set_impacts_to_zero=False) for inf in infiles]


    def process_inputs(self):
        input_list = self.load_all_inputs()


                        plotvar_num = plotvar.split('_')[-1]
                try:
                    i_sector = int(plotvar_num)
                    input_shock_var = f'exo_D_{i_sector}_1'
                    shock_data = [self.input.data[s][input_shock_var] for s in self.scenarios]
                    if len(shock_data) > 1:
                        if not np.all([np.allclose(shock_data[0], shock_data[i]) for i in range(1, len(shock_data))]):
                            raise ValueError('Unplottable: different input scenarios have different shocks')
                    axtwin = axs[i_row, i_col].twinx()
                    axtwin.bar(years, shock_data[0], label=scenario, color='lightgrey', width=0.4, linewidth=0)
                except ValueError:
                    pass
                
    

    def plot(self, varlist=OUTPUT_VAR_LOOKUP.keys(), outputs_processed=None):
        if not outputs_processed:
            outputs_processed = self.process_outputs()
        
        if isinstance(varlist, str):
            varlist=[varlist]

        if len(varlist) == 1:
            plot_rows = 1
            plot_cols = 1
        else:
            plot_rows = int(np.ceil(len(varlist)/2))
            plot_cols = 2

        fig, axs = plt.subplots(plot_rows, plot_cols, figsize=(10, 18), sharex=True)

        for i, (varname, df) in enumerate(outputs_processed):
            i_row = int(np.floor(i/2))
            i_col = np.mod(i, 2)

            plotdata = self.data[varname].set_index('Year')
            for col in plotdat.columns:
                if col == 'Baseline':
                    axs[i_row, i_col].plot(plotdata.index, plotdata[col], color='black', label='Baseline')
                elif col == 'mean':
                    axs[i_row, i_col].plot(plotdata.index, plotdata[col], color='orange', label='Mean of simulations')
                else:
                    axs[i_row, i_col].plot(plotdata.index, plotdata[col], color='lightblue', label='col')
            
            axs[i_row, i_col].set_title(varname)
            custom_lines = [Line2D([0], [0], color='black', lw=1),
                            Line2D([0], [0], color='orange', lw=1),
                            Line2D([0], [0], color='lightblue', lw=1)]
            ax[i_row, i_col].legend(custom_lines, ['Baseline', 'Simulation mean', 'Individual runs'])

        fig.suptitle('CRED output')
        plt.xlabel('Year')
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
        colname = OUTPUT_VAR_LOOKUP[output_var]
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
        if output_var not in OUTPUT_VAR_LOOKUP.keys():
            raise ValueError(f'please request output variables contained in OUTPUT_VAR_LOOKUP')
        excel_colname = OUTPUT_VAR_LOOKUP[output_var]
        excel_colname = ['Year',  excel_colname]
        result = pd.read_excel(Path(self.results_dir, filename), sheet_name='Baseline')
        result = self._subset_result_years(result, self.start_year, self.end_year)
        result = result[excel_colname]
        return result

    
    def sample_yearsets(self):
        simulation_years = np.arange(self.start_year, self.end_year+1)
        n_years = len(simulation_years)
        events_per_year = np.ones(n_years).astype('int')
        ys = {}
        for (sector, imp) in self.sector_impacts.items():
            sampling_vect = yearsets.sample_events(events_per_year, imp.frequency)
            ys[sector] = yearsets.impact_yearset_from_sampling_vect(imp, simulation_years, sampling_vect, correction_fac=False)
        return ys
    
    def empty_yearsets(self):
        simulation_years = np.arange(self.start_year, self.end_year+1)
        n_years = len(simulation_years)
        events_per_year = np.zeros_like(simulation_years).astype('int')
        ys = {}
        for (sector, imp) in self.sector_impacts.items():
            sampling_vect = yearsets.sample_events(events_per_year, imp.frequency)
            ys[sector] = yearsets.impact_yearset_from_sampling_vect(imp, simulation_years, sampling_vect, correction_fac=False)
        return ys



    @classmethod
    def from_snapshots(
        input_dir: Union[str, Path],
        results_dir: Union[str, Path],
        snapshot_list: List[Union[str, Path, Impact]],
        n_sim_years: int,
        seed: int = 161
    ):
        pass
    
    
    @classmethod
    def from_entities(
        input_dir: Union[str, Path],
        results_dir: Union[str, Path],
        entity_list: List[MeasureSet],
        n_sim_years: int,
        seed: int = 161
    ):
        pass


    @classmethod
    def from_impact_calc_list(
        input_dir: Union[str, Path],
        results_dir: Union[str, Path],
        impact_calc_list: List[Union[str, Path, Impact]],
        adaptation_list: List[MeasureSet],
        n_sim_years: int,
        seed: int = 161
    ):
        pass


    def run_simulations(self):
        simulation_years = np.arange(start_year, end_year+1)
        n_years = len(simulation_years)
        events_per_year = np.ones(n_years).astype('int')
        sampling_vect = sample_events(events_per_year, imp.frequency, seed=seed)
        yearset = impact_yearset_from_sampling_vect(imp, sampled_years, sampling_vect, correction_fac=False)