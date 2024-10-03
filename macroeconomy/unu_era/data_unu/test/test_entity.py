import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import numpy as np
from climada.entity import Entity, ImpactFunc, ImpactFuncSet

# Import the functions to be tested
from macroeconomy.unu_era.data_unu.entity import get_unu_entity, get_unu_exposure, get_unu_impf, drop_impf_leading_zeroes, DATA_DIR, ENTITY_FILES, ENTITY_CODES

class TestUNUProjectFunctions(unittest.TestCase):

    @patch('macroeconomy.unu_era.data_unu.entity._load_unu_entity')
    def test_get_unu_entity(self, mock_load_unu_entity):
        impf_students = ImpactFunc(
            haz_type='FL',
            id=102,
            intensity = np.array([0, 1, 2]),
            mdd = np.array([0, 0.1, 0.2]),
            paa = np.array([1, 1, 1])
        )

        # Mock the _load_unu_entity function
        mock_entity = MagicMock()
        mock_entity.impact_funcs = ImpactFuncSet([impf_students])
        mock_load_unu_entity.return_value = mock_entity

        # Test getting a specific exposure
        exposure_name = 'people - students'
        entity, category_id = get_unu_entity('thailand', 'flood', exposure_name)
        self.assertEqual(entity, mock_entity)
        self.assertEqual(category_id, ENTITY_CODES['thailand'][exposure_name])

        # Test with invalid country
        with self.assertRaises(KeyError):
            get_unu_entity('invalid_country', 'flood', exposure_name)

        # Test with invalid hazard
        with self.assertRaises(KeyError):
            get_unu_entity('thailand', 'invalid_hazard', exposure_name)

        # Test with invalid exposure name
        with self.assertRaises(KeyError):
            get_unu_entity('thailand', 'flood', 'invalid_exposure')


    @patch('macroeconomy.unu_era.data_unu.entity.get_unu_entity')
    def test_get_unu_exposure(self, mock_get_unu_entity):
        # Mock the get_unu_entity function
        mock_entity = MagicMock()
        mock_exposures = MagicMock()
        mock_entity.exposures = mock_exposures
        mock_get_unu_entity.return_value = (mock_entity, 102)

        # Test getting an exposure
        exposure = get_unu_exposure('thailand', 'people - students')
        self.assertEqual(exposure, mock_exposures)

        # Verify that get_unu_entity was called with correct arguments
        mock_get_unu_entity.assert_called_once_with('thailand', hazard_name='flood', exposure_name='people - students')


    @patch('macroeconomy.unu_era.data_unu.entity.get_unu_entity')
    @patch('macroeconomy.unu_era.data_unu.entity.drop_impf_leading_zeroes')
    def test_get_unu_impf(self, mock_drop_impf_leading_zeroes, mock_get_unu_entity):
        # Mock the get_unu_entity function
        mock_entity = MagicMock()
        mock_impact_funcs = MagicMock()
        mock_entity.impact_funcs = mock_impact_funcs
        mock_get_unu_entity.return_value = (mock_entity, 102)

        # Mock the impact function
        mock_impf = MagicMock()
        mock_impf.mdd = np.array([0, 0.1, 0.2])
        mock_impf.intensity = np.array([0, 1, 2])
        mock_impf.paa = np.array([1, 1, 1])
        mock_impact_funcs.get_func.return_value = mock_impf

        # Mock the drop_impf_leading_zeroes function
        mock_drop_impf_leading_zeroes.return_value = mock_impf

        # Test getting an impact function
        impf = get_unu_impf('thailand', 'flood', 'people - students')
        self.assertEqual(impf, mock_impf)

        # Verify that get_unu_entity was called with correct arguments
        mock_get_unu_entity.assert_called_once_with('thailand', hazard_name='flood', exposure_name='people - students')

        # Verify that drop_impf_leading_zeroes was called
        mock_drop_impf_leading_zeroes.assert_called_once_with(mock_impf)

        # Test with invalid hazard
        with self.assertRaises(ValueError):
            get_unu_impf('thailand', 'invalid_hazard', 'people - students')


    def test_drop_impf_leading_zeroes(self):
        # No change when necessary
        impf1 = ImpactFunc(
            haz_type='FL',
            id=1,
            intensity = np.array([0, 1, 2]),
            mdd = np.array([0, 0.1, 0.2]),
            paa = np.array([1, 1, 1])
        )
        impf2 = drop_impf_leading_zeroes(impf1)
        self.assertEqual(impf1.haz_type, 'FL')
        self.assertEqual(impf1.id, 1)
        np.testing.assert_array_equal(impf1.intensity, impf2.intensity)
        np.testing.assert_array_equal(impf1.mdd, impf2.mdd)
        np.testing.assert_array_equal(impf1.paa, impf2.paa)
        np.testing.assert_array_equal(impf1.calc_mdr(impf1.intensity), impf2.calc_mdr(impf2.intensity))

        # Drops leading zeroes
        impf3 = ImpactFunc(
            haz_type='FL',
            id=1,
            intensity = np.array([0, 1, 2, 3, 4]),
            mdd = np.array([0, 0, 0, 0.1, 0.2]),
            paa = np.array([1, 1, 1, 1, 1])
        )
        impf4 = drop_impf_leading_zeroes(impf3)
        self.assertEqual(impf4.haz_type, 'FL')
        self.assertEqual(impf4.id, 1)
        np.testing.assert_array_equal(impf4.intensity, np.array([2, 3, 4]))
        np.testing.assert_array_equal(impf4.mdd, np.array([0, 0.1, 0.2]))
        np.testing.assert_array_equal(impf4.paa, np.array([1, 1, 1]))
        np.testing.assert_array_equal(impf4.calc_mdr(impf4.intensity), np.array([0, 0.1, 0.2]))


if __name__ == '__main__':
    unittest.main()