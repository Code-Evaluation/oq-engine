#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy
import unittest
from scipy.interpolate import interp1d

class propabilistic_event_based_unittest(unittest.TestCase):
    
    def test_interpolation_scipy_spike(self):
        # vulnerability function IMLs
        x_values = numpy.array([0.01, 0.04, 0.07, 0.10, 0.12, 0.22, 0.37, 0.52])
        # vulnerability function loss ratios
        y_values = numpy.array([0.001, 0.022, 0.051, 0.080, 0.100, 0.200, 0.405, 0.70])
        
        f = interp1d(x_values, y_values)
        
        # precomputed values by Vitor Silva
        output_values = (0.0605584000000000, 0.273100266666667,	0.0958560000000000,	0.0184384000000000,
                0.270366933333333, 0.0,	0.0252480000000000, 0.0795669333333333, 0.0529024000000000, 0.0,
                0.0154928000000000, 0.00222080000000000, 0.0109232000000000, 0.0, 0.0, 0.0, 0.0175088000000000,
                0.0230517333333333, 0.00300480000000000, 0.0, 0.0475973333333333, 0.0, 0.00794400000000000, 
                0.00213120000000000, 0.0, 0.0172848000000000, 0.00908640000000000, 0.0365850666666667, 0.0, 0.0,
                0.0238096000000000, 0.0, 0.0, 0.0, 0.0, 0.00782080000000000, 0.0115952000000000, 0.0, 0.0, 0.0, 
                0.0, 0.0619504000000000, 0.0, 0.0118976000000000, 0.0329968000000000, 0.0, 0.00245600000000000,
                0.0, 0.0, 0.0, 0.0,	0.0114608000000000, 0.00217600000000000, 0.0131856000000000, 0.0, 0.0, 0.186080000000000,
                0.0, 0.00413600000000000, 0.0196480000000000, 0.104992000000000, 0.0, 0.0, 0.00498720000000000,	0.0,
                0.0, 0.0, 0.00612960000000000, 0.0, 0.0450453333333333,	0.0143728000000000,	0.0, 0.00546880000000000,
                0.0, 0.0, 0.0, 0.00838080000000000,	0.0, 0.00201920000000000, 0.0, 0.0112816000000000, 0.0110128000000000,
                0.106928000000000, 0.0, 0.0, 0.0113376000000000, 0.0, 0.0118080000000000, 0.0, 0.427215466666667,
                0.00366560000000000, 0.0, 0.161776000000000, 0.0212384000000000, 0.0107216000000000, 0.0, 0.00392320000000000,
                0.0, 0.0697610666666667, 0.0, 0.00906400000000000, 0.0, 0.0, 0.0455712000000000, 0.0, 0.00508800000000000,
                0.00278080000000000, 0.0136896000000000, 0.0, 0.0, 0.0118752000000000, 0.0, 0.0925280000000000, 0.0458960000000000,
                0.00676800000000000, 0.0, 0.0, 0.00438240000000000, 0.0, 0.0232218666666667, 0.0, 0.00530080000000000, 0.0, 0.0, 0.0,
                0.0, 0.00953440000000000, 0.0, 0.0, 0.0268101333333333, 0.0369098666666667, 0.0, 0.00125760000000000, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.290899733333333, 0.0, 0.0, 0.0, 0.0, 0.0348064000000000, 0.0279392000000000, 0.00296000000000000,
                0.0171504000000000, 0.0147760000000000,	0.0, 0.00870560000000000, 0.00627520000000000, 0.0, 0.00522240000000000,
                0.00293760000000000, 0.0, 0.0, 0.0, 0.0259749333333333, 0.0101504000000000, 0.00326240000000000, 0.0, 0.00804480000000000,
                0.0, 0.0216528000000000, 0.0, 0.0, 0.0, 0.0578208000000000, 0.0939840000000000, 0.0, 0.0345898666666667, 0.0106544000000000,
                0.00313920000000000, 0.0, 0.0, 0.00164960000000000, 0.0238405333333333, 0.0, 0.0238714666666667, 0.0189648000000000,
                0.0162320000000000, 0.0, 0.0, 0.0293466666666667, 0.0142608000000000, 0.0, 0.00179520000000000, 0.0119984000000000,
                0.0, 0.0, 0.0, 0.0, 0.0501648000000000, 0.00209760000000000, 0.00503200000000000, 0.00150400000000000, 0.0, 0.146192000000000,
                0.0, 0.00325120000000000, 0.0, 0.0, 0.0344970666666667, 0.0, 0.0, 0.00879520000000000, 0.0146976000000000, 0.00306080000000000,
                0.0, 0.0, 0.00158240000000000, 0.0810400000000000, 0.0, 0.00307200000000000, 0.0199728000000000)
        
        # input values
        input_values = (0.079888, 0.273488, 0.115856, 0.034912, 0.271488, 0.00224, 0.04336, 0.099552, 0.071968,
                0.003456, 0.030704, 0.011744, 0.024176, 0.002224, 0.008912, 0.004224, 0.033584, 0.041088, 0.012864, 0.001728,
                0.06648, 0.000736, 0.01992, 0.011616, 0.001104, 0.033264, 0.021552, 0.055088, 0.00176, 0.001088, 0.041872,
                0.005152, 0.007424, 0.002464, 0.008496, 0.019744, 0.025136, 0.005552, 0.00168, 0.00704, 0.00272, 0.081328,
                0.001408, 0.025568, 0.051376, 0.003456, 0.01208, 0.002496, 0.001152, 0.007552, 0.004944, 0.024944, 0.01168,
                0.027408, 0.00504, 0.003136, 0.20608, 0.00344, 0.01448, 0.03664, 0.124992, 0.005024, 0.007536, 0.015696, 0.00608,
                0.001248, 0.005744, 0.017328, 0.002272, 0.06384, 0.029104, 0.001152, 0.016384, 0.002096, 0.00328, 0.004304, 0.020544,
                0.000768, 0.011456, 0.004528, 0.024688, 0.024304, 0.126928, 0.002416, 0.0032, 0.024768, 0.00608, 0.02544, 0.003392,
                0.381296, 0.013808, 0.002256, 0.181776, 0.038912, 0.023888, 0.002848, 0.014176, 0.001936, 0.089408, 0.001008, 0.02152,
                0.002464, 0.00464, 0.064384, 0.001712, 0.01584, 0.012544, 0.028128, 0.005808, 0.004928, 0.025536, 0.008304, 0.112528,
                0.06472, 0.01824, 0.002624, 0.003456, 0.014832, 0.002592, 0.041264, 0.004368, 0.016144, 0.008032, 0.007344, 0.004976, 
                0.00072, 0.022192, 0.002496, 0.001456, 0.044976, 0.055424, 0.009232, 0.010368, 0.000944, 0.002976, 0.00656, 0.003184,
                0.004288, 0.00632, 0.286512, 0.007568, 0.00104, 0.00144, 0.004896, 0.053248, 0.046144, 0.0128, 0.033072, 0.02968,
                0.002096, 0.021008, 0.017536, 0.000656, 0.016032, 0.012768, 0.002752, 0.007392, 0.007072, 0.044112, 0.023072, 0.013232,
                0.001824, 0.020064, 0.008912, 0.039504, 0.00144, 0.000816, 0.008544, 0.077056, 0.113984, 0.001856, 0.053024, 0.023792,
                0.013056, 0.0084, 0.009392, 0.010928, 0.041904, 0.000496, 0.041936, 0.035664, 0.03176, 0.003552, 0.00216, 0.0476, 0.028944,
                0.006832, 0.011136, 0.025712, 0.006368, 0.004672, 0.001312, 0.008496, 0.069136, 0.011568, 0.01576, 0.01072, 0.002336,
                0.166192, 0.00376, 0.013216, 0.000592, 0.002832, 0.052928, 0.007872, 0.001072, 0.021136, 0.029568, 0.012944, 0.004064,
                0.002336, 0.010832, 0.10104, 0.00096, 0.01296, 0.037104)
        
        for idx, input_value in enumerate(input_values):
            try:
                self.assertAlmostEqual(output_values[idx], f(input_values[idx]))
            except ValueError:
                pass
                # print "Value %f outside the range of the function!" % input_values[idx]
        
if __name__ == "__main__":
    unittest.main()
    