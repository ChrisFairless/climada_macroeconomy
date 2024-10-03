import unittest
import os
import numpy as np
from copy import deepcopy
from datetime import date
from pathlib import Path
import shutil

from climada.engine.impact import Impact

from macroeconomy.climada_cred import ClimadaCRED
from macroeconomy.test.test_macroeconomy_cred import DO_TESTS_QUICK

TESTDATA_DIR = Path(os.path.dirname(__file__), 'data')
TESTDATA_INPUT_TEMPLATE = Path(TESTDATA_DIR, 'ExampleModelSimulationandCalibration5Sectorsand1Regions.xlsx')
TESTDATA_INPUT = Path(TESTDATA_DIR, 'test_input_excel.xlsx')

if DO_TESTS_QUICK:
    print('Warning: skipping all tests that actually run CRED. Edit DO_TESTS_QUICK in test_macroeconomy_cred.py to change this')


class TestClimadaCRED(unittest.TestCase):
    def setUp(self):
        # TODO find a way to test matlab AND octave
        impacts_array = np.array([1, 0.9])
        self.example_impacts_numpy = {
            'exo_D_1_1': impacts_array,
            'exo_D_2_1': impacts_array,
            'exo_D_3_1': impacts_array,
            'exo_D_4_1': impacts_array,
            'exo_D_5_1': impacts_array,
            'exo_DH': impacts_array
        }
        impacts_object = Impact(
            event_id=[str(i) for i in range(2)],
            event_name=[str(i) for i in range(2)],
            date=[date(year=2000+i, month=1, day=20) for i in range(2)],
            frequency=[1/2, 1/2],
            at_event=impacts_array
        )
        self.example_impacts_climada = {
            'exo_D_1_1': impacts_object,
            'exo_D_2_1': impacts_object,
            'exo_D_3_1': impacts_object,
            'exo_D_4_1': impacts_object,
            'exo_D_5_1': impacts_object,
            'exo_DH': impacts_object
        }
        shutil.copy2(TESTDATA_INPUT_TEMPLATE, TESTDATA_INPUT)

    
    def test_climada_cred_initialises(self):
        cred = ClimadaCRED(input_excel=TESTDATA_INPUT)

    def test_climada_cred_can_overwrite_impacts(self):
        # No impacts
        cred = ClimadaCRED(
            sector_annual_impacts=None,
            input_excel=TESTDATA_INPUT,
            scenarios=['Baseline', 'Scenario']
        )
        df = cred.input_as_df('Scenario')
        for key, value in self.example_impacts_numpy.items():
            np.testing.assert_allclose(df[key], np.zeros_like(df[key]))

        # Numpy impacts
        cred = ClimadaCRED(
            sector_annual_impacts=self.example_impacts_numpy,
            input_excel=TESTDATA_INPUT,
            scenarios=['Baseline', 'Scenario']
        )
        df = cred.input_as_df('Scenario')
        for key, value in self.example_impacts_numpy.items():
            np.testing.assert_allclose(df[key], value)

        # CLIMADA Impact impacts
        cred = ClimadaCRED(
            sector_annual_impacts=self.example_impacts_climada,
            input_excel=TESTDATA_INPUT,
            scenarios=['Baseline', 'Scenario']
        )
        df = cred.input_as_df('Scenario')
        for key, value in self.example_impacts_numpy.items():
            np.testing.assert_allclose(df[key], value)

    
    def test_climada_cred_hates_negative_impacts(self):
        impacts_array = np.array([-0.1, 0])
        self.example_impacts_numpy = {
            'exo_D_1_1': impacts_array,
        }
        with self.assertRaises(ValueError) as context:
            cred = ClimadaCRED(
                sector_annual_impacts=self.example_impacts_numpy,
                input_excel=TESTDATA_INPUT
            )

    def test_climada_cred_hates_impacts_greater_than_one(self):
        impacts_array = np.array([1.1, 0])
        self.example_impacts_numpy = {
            'exo_D_1_1': impacts_array,
        }
        with self.assertRaises(ValueError) as context:
            cred = ClimadaCRED(
                sector_annual_impacts=self.example_impacts_numpy,
                input_excel=TESTDATA_INPUT
            )

    def test_climada_cred_runs(self):
        if DO_TESTS_QUICK:
            self.skipTest("DO_TESTS_QUICK is True: we won't run CRED")
        cred = ClimadaCRED(
            sector_annual_impacts=self.example_impacts_numpy,
            input_excel=TESTDATA_INPUT,
            scenarios=['Baseline', 'Scenario'],
            iStepSimulation=2
        )
        cred.run()
        output_baseline = cred.output_as_df('Baseline')
        output_scenario = cred.output_as_df('Scenario')
        sector_gdp_keys = [f'Y_{i}' for i in range(1,6)]
        for key in sector_gdp_keys:
            max_diff = np.max(abs(output_scenario[key] - output_baseline[key]))
            self.assertTrue(max_diff > 0)
            