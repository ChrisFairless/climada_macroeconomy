import os
import re
import subprocess
import logging
import numpy as np
import pandas as pd
import shutil
import openpyxl
from pathlib import Path
from typing import Union, List, Dict
import matplotlib.pyplot as plt

from macroeconomy.cred_input import CREDInput
from macroeconomy.cred_output import CREDOutput

LOGGER = logging.getLogger(__name__)

# TODO allow these to be overridden by CLIMADA conf? 
CRED_LOCATION = '/Users/chrisfairless/Projects/UNU/CLIMADA_CRED_data/CRED/CRED_inputs/Thailand and Egypt/DGE_CRED_Model/Matlab/'
CRED_ENGINE = 'matlab'   # matlab or octave

# Only one of these needs to be provided (matching your choice of ENGINE) but both variables are required during testing
MATLAB_EXECUTABLE = '/Applications/MATLAB_R2023b.app/bin/matlab'
OCTAVE_EXECUTABLE = '/usr/local/bin/octave'


class MacroEconomyCRED():
    # The DGE-CRED model wrapped in python
    # with limited functionality, for now
    # 
    # This class will run a single CRED simulation
    # For full coupling with CLIMADA use the CREDController class below 
    #
    # TODO document class

    def __init__(
        self,
        input_excel: Union[str, Path] = None,
        output_excel: Union[str, Path] = None,
        n_sim_years = None,
        n_sectors = 5,
        n_regions = 1,
        scenarios = ["Baseline", "Scenario"],
        # TODO allow the user to set all the options in the model definition!
        # Subsecstart = [1, 2, 4, 5],
        # Subsecend = [1, 3, 4, 5],
        ForwardLooking = False,
        # Regions = 1,
        # ClimateVarsRegional = ["tas"],
        # ClimateVarsNational = ["SL"],
        # iStepSteadyState = 1,
        iStepSimulation = 40,
    ):
        self.cred_location = CRED_LOCATION        
        self.engine = CRED_ENGINE
        if self.engine == "matlab":
            self.executable = MATLAB_EXECUTABLE
            self.cred_command = f'''{self.executable} -nodisplay -nodesktop -r "try; cd('{self.cred_location}'); RunSimulations(); catch; end; quit;"'''
        elif self.engine == "octave":
            self.executable = OCTAVE_EXECUTABLE
            raise ValueError('CRED in python is currently only set up to work with MATLAB')
        else:
            raise ValueError("MacroEconomyCRED must have engine as either 'matlab' or 'octave'")

        self.n_sectors = n_sectors
        self.n_regions = n_regions
        self.scenarios = scenarios
        self.ForwardLooking = ForwardLooking
        self.iStepSimulation = iStepSimulation

        self.cred_input_excel = Path(self.cred_location, 'ExcelFiles', f'ModelSimulationandCalibration{n_sectors}Sectorsand{n_regions}Regions.xlsx')
        self.cred_output_excel = Path(self.cred_location, 'ExcelFiles', f'ResultsScenarios{n_sectors}Sectorsand{n_regions}Regions.xlsx')

        self.user_input_excel = input_excel if input_excel else self.cred_input_excel 
        self.user_output_excel = output_excel if output_excel else self.cred_output_excel
        
        self.runsimulations_file = Path(self.cred_location, 'RunSimulations.m')
        self.mod_file = Path(self.cred_location, 'DGE_CRED_Model.mod')
        self.check_directories_exist()

        self.n_sim_years = n_sim_years if n_sim_years else self.get_input().n_sim_years
        self.model_has_been_run = False

        # self.Subsecstart = Subsecstart,
        # self.SubsecEnd = Subsecend,
        # self.Regions = Regions,
        # self.ClimateVarsRegional = ClimateVarsRegional,
        # self.ClimateVarsNational = ClimateVarsNational,
        # self.ClimateVars = ClimateVarsRegional + ClimateVarsNational
        # self.iStepSteadyState = iStepSteadyState

    @classmethod
    def from_input(cls, input, **kwargs):
        cred = cls(
            input_excel=None,
            **kwargs
        )
        input.to_excel(cred.cred_input_excel, overwrite=True)
        return cred

    def get_input(self):
        return CREDInput(
            template_excel_path = self.user_input_excel,
            scenarios = self.scenarios
        )
    
    def get_output(self):
        if not os.path.exists(self.user_output_excel):
            if self.model_has_been_run:
                raise FileNotFoundError(f'No output file at {self.user_output_excel}. Something may have gone wrong during the model execution')
            else:
                raise FileNotFoundError(f'No output file at {self.user_output_excel}. Run the model first')
        return CREDOutput(
            input_excel_path = self.user_input_excel,
            output_excel_path = self.user_output_excel,
            scenarios = self.scenarios
        )

    
    @staticmethod
    def install_cred(install_dir):
        raise NotImplementedError()


    # ------------------------------- 
    # Methods for executing the model
    # ------------------------------- 

    def run(self):
        LOGGER.info('Executing CRED')
        self._setup()
        self._execute()
        self._teardown()
        return self.get_output()


    def _setup(self):
        self.check_directories_exist()
        self.check_model_is_valid()
        self.set_istep_simulation(self.iStepSimulation)
        self.set_forwardlooking(self.ForwardLooking)
        self.set_scenarios(self.scenarios)
        self.remove_existing_output()
        
        # Copy input into the CRED model directory
        if self.user_input_excel != self.cred_input_excel:
            self.copy_input_into_cred(source=self.user_input_excel)
        
        # Trim the Excel file in the model directory to the number of years we're running
        self._truncate_input_excel()
            
    
    def _execute(self):
        subprocess.run(self.cred_command, shell=True, check=True)
        if not os.path.exists(self.cred_output_excel):
            LOGGER.error(f"No CRED output was created. The model probably failed to finish. Errors are not printed within python. To see what went wrong try running the model again from the command line with:\n{self.cred_command}")


    def _teardown(self):
        self._truncate_output_excel()   # TODO find a way to run a shorter simulation!!
        if self.user_output_excel != self.cred_output_excel:
            self.copy_output_from_cred(destination=self.user_output_excel)
        self.model_has_been_run = True
    

    def remove_existing_output(self):
        if os.path.exists(self.cred_output_excel):
            os.remove(self.cred_output_excel)


    def _truncate_input_excel(self):
        self.truncate_cred_excel(self.cred_input_excel, self.cred_input_excel, self.scenarios, n_sim_years=self.n_sim_years)

    
    def _truncate_output_excel(self):
        self.truncate_cred_excel(self.cred_output_excel, self.cred_output_excel, self.scenarios, n_sim_years=self.n_sim_years)


    def copy_output_from_cred(self, destination):
        shutil.copy2(self.cred_output_excel, destination)
  
    def copy_input_into_cred(self, source):
        shutil.copy2(source, self.cred_input_excel)
        # A simple copy didn't work – CRED doesn't like the sheet names from the templates we're using
        # with pd.ExcelWriter(self.cred_input_excel, mode="w", engine="openpyxl") as writer:
        #     with pd.ExcelFile(source) as xl:
        #         pd.read_excel(xl, 'Content').to_excel(writer, sheet_name='Content', index=False)
        #         pd.read_excel(xl, 'Data').to_excel(writer, sheet_name='Data', index=False)
        #         pd.read_excel(xl, 'Start').to_excel(writer, sheet_name='Start', index=False)
        #         pd.read_excel(xl, 'Structural Parameters').to_excel(writer, sheet_name='Structural Parameters', index=False)
        #         pd.read_excel(xl, 'Baseline').to_excel(writer, sheet_name='Baseline', index=False)
        #         for scenario in self.scenarios:
        #             if scenario != 'Baseline':
        #                 pd.read_excel(xl, scenario).to_excel(writer, sheet_name=scenario, index=False)


    # -----------------------------------------
    # Methods for modifying CRED before running
    # -----------------------------------------

    def set_istep_simulation(self, istep: int):
        self._rewrite_mod_var('options_.iStepSimulation', istep)
    
    def set_forwardlooking(self, forwardlooking: bool):
        self._rewrite_mod_var('@# define ForwardLooking', int(forwardlooking))

    def _rewrite_mod_var(self, pattern, value):
        with open(self.mod_file, 'r') as f:
            filedata = f.read()
        pattern = re.escape(pattern)
        pattern = rf"(.*{pattern}\s*=\s*)\d+"  # Note: only used for integer replacement
        filedata = re.sub(pattern, rf'\g<1>{value}', filedata)
        with open(self.mod_file, 'w') as f:
            f.write(filedata)


    def set_scenarios(self, scenarios: List[str]):
        scenario_string = "'" + "', '".join(scenarios) + "'"

        with open(self.runsimulations_file, 'r') as f:
            lines_file = f.readlines()

        # Writing scenarios can be complex as CRED lets them span multiple lines
        # This reads the RunSimulations.m file line-by-line, editing the first line of the 
        # casSecnarioNames specification and deleting all subsequent lines until the next 
        # part of the file, which starts with 'Define sector'
        with open(self.runsimulations_file, 'w') as f:
            keep_line = True
            for l in lines_file:
                if 'casScenarioNames = {' in l:
                    s = 'casScenarioNames = {' + scenario_string + '}\n\n'
                    f.write(s)
                    keep_line = False
                elif 'Define sector' in l:
                    f.write(l)
                    keep_line = True
                elif keep_line:
                    f.write(l)


    @staticmethod
    def truncate_cred_excel(input_file, output_file, scenarios, n_sim_years):
        xl = pd.read_excel(input_file, sheet_name=scenarios)
        all_scenarios = list({'Baseline'}.union(set(scenarios)))

        for scenario in all_scenarios:
            if xl[scenario].shape[0] < n_sim_years:
                raise ValueError("Input Excel has fewer rows than the requested truncation")
            xl[scenario] = xl[scenario].iloc[0:n_sim_years, ]
        
        with pd.ExcelWriter(output_file, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
            for scenario in scenarios:
                xl[scenario].to_excel(writer, sheet_name=scenario, index=False)


    # -----------------------------------------
    # Validation and checks
    # -----------------------------------------

    def check_directories_exist(self):
        if not os.path.exists(self.cred_location):
            raise ValueError(f'CRED directory does not exist at {cred_location}')

        if not os.path.exists(self.executable):
            raise FileExistsError(f'Could not find the executable to run CRED with {self.engine} at {self.executable}. Please check your setup in macroeconomy.py')

        if not os.path.exists(self.user_input_excel):
            raise FileNotFoundError(f'Input file not found at {self.user_input_excel}')

        if not os.path.exists(os.path.dirname(self.user_output_excel)):
            raise FileNotFoundError(f'Location for output file not found at {self.user_output_excel}')


    def check_model_is_valid(self):
        sectors = CREDInput.read_sectors_from_cred_input(self.user_input_excel)
        if len(sectors) != self.n_sectors:
            raise ValueError(f"The input Excel sheet's Content page doesn't have {self.n_sectors} to match the user-supplied count of {self.n_sectors}. Sectors: {sectors}")
        # TODO more
