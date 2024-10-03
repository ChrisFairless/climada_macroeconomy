import unittest
import os
import re
import numpy as np
import shutil
from pathlib import Path
from copy import deepcopy

from macroeconomy.macroeconomy_cred import MacroEconomyCRED, MATLAB_EXECUTABLE, OCTAVE_EXECUTABLE, CRED_LOCATION


TESTDATA_DIR = Path(os.path.dirname(__file__), 'data')
TESTDATA_INPUT_TEMPLATE = Path(TESTDATA_DIR, 'ExampleModelSimulationandCalibration5Sectorsand1Regions.xlsx')
TESTDATA_INPUT = Path(TESTDATA_DIR, 'test_input_excel.xlsx')

DO_TESTS_QUICK = False   # Turn off to avoid running CRED in the tests
if DO_TESTS_QUICK:
    print('Warning: skipping all tests that actually run CRED. Edit DO_TESTS_QUICK in test_macroeconomy_cred.py to change this')


class TestMacroeconomyCRED(unittest.TestCase):

    # TODO set up a test installation with input data that's only a few rows to simulate

    def setUp(self):
        # TODO find a way to test matlab AND octave
        self.matlab_enabled = os.path.exists(MATLAB_EXECUTABLE)
        self.octave_enabled = os.path.exists(OCTAVE_EXECUTABLE)
        shutil.copy2(TESTDATA_INPUT_TEMPLATE, TESTDATA_INPUT)
        
    def test_engine_exists(self):
        if not self.matlab_enabled and not self.octave_enabled:
            raise ValueError('Could not find a valid Matlab or Octave executable to run CRED. Update the paths in macroeconomy_cred.py')

    def test_we_can_set_scenarios(self):
        cred = MacroEconomyCRED(
            scenarios=['Baseline'],
            input_excel=TESTDATA_INPUT
        )

        one_scenario_str = "casScenarioNames = {'Baseline'}"
        with open(cred.runsimulations_file, 'r') as f:
            self.assertTrue(one_scenario_str in f.read())

        cred.set_scenarios(['Baseline', 'Scenario'])
        two_scenario_str = "casScenarioNames = {'Baseline', 'Scenario'}"
        with open(cred.runsimulations_file, 'r') as f:
            self.assertTrue(two_scenario_str in f.read())


    def test_we_can_set_forwardlooking(self):
        cred = MacroEconomyCRED(
            ForwardLooking=False,
            input_excel=TESTDATA_INPUT
        )
        fw_false_str = "@# define ForwardLooking = 0"
        with open(cred.mod_file, 'r') as f:
            self.assertTrue(fw_false_str in f.read())

        cred.set_forwardlooking(True)
        fw_true_str = "@# define ForwardLooking = 1"
        with open(cred.mod_file, 'r') as f:
            self.assertTrue(fw_true_str in f.read())


    def test_we_can_set_istep_simulation(self):
        cred = MacroEconomyCRED(
            iStepSimulation=41,
            input_excel=TESTDATA_INPUT
        )
        # istep_str = r'options_\.iStepSimulation\s*=\s*41;'
        istep_str = 'options_.iStepSimulation  = 41;'
        with open(cred.mod_file, 'r') as f:
            self.assertTrue(istep_str in f.read())

        cred._rewrite_mod_var('options_.iStepSimulation', 40)
        istep_str = 'options_.iStepSimulation  = 40;'
        with open(cred.mod_file, 'r') as f:
            self.assertTrue(istep_str in f.read())


    def test_we_can_read_input(self):
        cred = MacroEconomyCRED(input_excel=TESTDATA_INPUT)
        df = cred.input_as_df(cred.scenarios[0])
        # TODO run some checks on column names and rows


    def test_we_can_run_cred_baseline(self):
        if DO_TESTS_QUICK:
            self.skipTest("DO_TESTS_QUICK is True: we won't run CRED")
        cred_baseline = MacroEconomyCRED(
            scenarios=['Baseline'],
            input_excel=TESTDATA_INPUT,
            ForwardLooking=False,
            n_sim_years=2,
            iStepSimulation=2      
        )
        cred_baseline.run()
        df = cred_baseline.output_as_df('Baseline')

    # Note: this test must run immediately after the previous one so that the 
    # baseline output is already available
    def test_we_can_run_cred_scenario(self):
        if DO_TESTS_QUICK:
            self.skipTest("DO_TESTS_QUICK is True: we won't run CRED")
        cred_scenario = MacroEconomyCRED(
            scenarios=['Scenario'],
            input_excel=TESTDATA_INPUT,
            ForwardLooking=False,
            n_sim_years=2,
            iStepSimulation=2          
        )
        cred_scenario.run()
        df = cred_scenario.output_as_df('Scenario')
        # TODO run some checks on column names and rows

    # def test_cred_octave(self):
    #     cred_baseline = MacroEconomyCRED(
    #         cred_location=CRED_LOCATION,
    #         engine="octave",
    #         executable=OCTAVE_EXECUTABLE,
    #         n_sectors=5,
    #         n_regions=1,
    #         scenarios=['Baseline'],
    #         ForwardLooking=False,
    #         iStepSimulation=2                
    #     )
    #     cred_baseline.run()

    #     cred_scenario = MacroEconomyCRED(
    #         cred_location=CRED_LOCATION,
    #         engine="octave",
    #         executable=OCTAVE_EXECUTABLE,
    #         n_sectors=5,
    #         n_regions=1,
    #         scenarios=['Scenario'],
    #         ForwardLooking=False,
    #         iStepSimulation=2                
    #     )
    #     cred_scenario.run()

    def test_we_can_make_plots(self):
        cred = MacroEconomyCRED(
            scenarios=['Baseline', 'Scenario'],
            input_excel=TESTDATA_INPUT,
            ForwardLooking=False,
            n_sim_years=2,
            iStepSimulation=2          
        )
        cred.plot_results()
